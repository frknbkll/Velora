"""Security checks use only disposable databases, keys, sessions, and HTTP servers."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file


import concurrent.futures
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

import server
import security_core
from test_auth_server import Client, PASSWORD


class SecurityServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin_hash = server.hash_password(PASSWORD)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "js" / "vendor").mkdir(parents=True)
        (self.root / "assets").mkdir()
        (self.root / "assets" / "portrait.jpg").write_bytes(b"image")
        (self.root / "js" / "vendor" / "qrcodegen.js").write_text("/* local QR library */")
        (self.root / "js" / "vendor" / "private.js").write_text("private")
        for name in ("index.html", "login.html", "register.html", "account.html", "admin.html"):
            (self.root / name).write_text("<!doctype html><title>Velora</title>")
        self.catalog = self.root / "product-catalog.json"
        self.catalog.write_text(json.dumps({"products": [{"id": "test-product", "name": "A suit", "image": "assets/portrait.jpg", "founder": "Victoria Mendez", "collection": "THE_TAILORED_EDIT", "price": 100, "description": "A considered suit.", "published": True}]}))
        self.database = self.root / ".velora" / "test.sqlite3"
        self.app = server.make_server(port=0, database=self.database, catalog=self.catalog, root=self.root)
        self.app.RequestHandlerClass.log_message = lambda *args: None
        with self.app.connect() as connection:
            connection.execute("INSERT INTO users (name,email,password_hash,role,created_at) VALUES (?,?,?,'admin',?)", ("Store Owner", "owner@example.com", self.admin_hash, server.now_iso()))
        self.thread = threading.Thread(target=self.app.serve_forever, daemon=True)
        self.thread.start()
        self.client = Client(self.app)
        self.assertEqual(self.client.register()[0], 201)

    def tearDown(self):
        self.app.shutdown()
        self.app.server_close()
        self.thread.join(timeout=5)
        self.directory.cleanup()

    def admin(self):
        client = Client(self.app)
        self.assertEqual(client.login(email="owner@example.com")[0], 200)
        return client

    def setup_mfa(self, client=None):
        client = client or self.client
        status, result, _ = client.request("POST", "/api/security/mfa/setup", {"password": PASSWORD})
        self.assertEqual(status, 200)
        return result

    def enable_mfa(self, client=None):
        client = client or self.client
        setup = self.setup_mfa(client)
        status, result, _ = client.request("POST", "/api/security/mfa/enable", {"code": security_core.totp(setup["secret"])})
        self.assertEqual(status, 200)
        return setup["secret"], result["recoveryCodes"]

    def challenge(self, email="maya@example.com", password=PASSWORD):
        client = Client(self.app)
        status, result, headers = client.login(email=email, password=password)
        self.assertEqual(status, 200)
        self.assertTrue(result.get("requiresTwoFactor"))
        self.assertNotIn("user", result)
        self.assertNotIn("Set-Cookie", headers)
        return client, result["challenge"]

    def verify_next(self, secret, client, challenge):
        with self.app.connect() as connection:
            counter = connection.execute("SELECT mfa_last_counter FROM users WHERE email='maya@example.com'").fetchone()[0]
        stamp = max(int(time.time()), (counter + 1) * 30)
        with mock.patch.object(security_core.time, "time", return_value=stamp):
            return client.request("POST", "/api/auth/verify", {"challenge": challenge, "code": security_core.totp(secret, stamp)})

    def test_rfc6238_vectors(self):
        secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
        for stamp, expected in ((59, "94287082"), (1111111109, "07081804"), (1111111111, "14050471"), (1234567890, "89005924"), (2000000000, "69279037"), (20000000000, "65353130")):
            self.assertEqual(security_core.totp(secret, stamp, digits=8), expected)
        self.assertEqual(security_core.totp(secret, 59), "287082")
        self.assertEqual(security_core.matching_counter(secret, "287082", 60), 1)
        self.assertIsNone(security_core.matching_counter(secret, "287082", 60, after=1))

    def test_security_views_require_auth_and_admin_permissions(self):
        public = Client(self.app)
        for route in ("status", "sessions"):
            self.assertEqual(public.request("GET", "/api/security/" + route)[0], 401)
        self.assertEqual(public.request("GET", "/api/admin/security")[0], 401)
        self.assertEqual(self.client.request("GET", "/api/admin/security")[0], 403)
        status = self.client.request("GET", "/api/security/status")[1]
        self.assertFalse(status["mfaEnabled"])
        self.assertEqual(status["recoveryCodesRemaining"], 0)
        self.assertEqual(status["adminIdleTimeoutSeconds"], 1800)

    def test_enrollment_requires_password_and_csrf_and_expires(self):
        self.assertEqual(self.client.request("POST", "/api/security/mfa/setup", {"password": PASSWORD}, token=False)[0], 403)
        self.assertEqual(self.client.request("POST", "/api/security/mfa/setup", {"password": "incorrect"})[0], 400)
        setup = self.setup_mfa()
        self.assertTrue(setup["otpauthUri"].startswith("otpauth://totp/Velora"))
        with self.app.connect() as connection:
            connection.execute("UPDATE users SET mfa_pending_expires_at=? WHERE email='maya@example.com'", (int(time.time()) - 1,))
        self.assertEqual(self.client.request("POST", "/api/security/mfa/enable", {"code": security_core.totp(setup["secret"])})[0], 400)
        self.assertFalse(self.client.request("GET", "/api/security/status")[1]["mfaEnabled"])

    def test_enable_rotates_current_session_and_revokes_others(self):
        other = Client(self.app)
        self.assertEqual(other.login()[0], 200)
        old_cookie = self.client.cookie
        secret, codes = self.enable_mfa()
        self.assertNotEqual(self.client.cookie, old_cookie)
        self.assertEqual(len(codes), 10)
        self.assertEqual(len(set(codes)), 10)
        self.assertIsNone(other.request("GET", "/api/auth/me")[1]["user"])
        self.assertIsNotNone(self.client.request("GET", "/api/auth/me")[1]["user"])
        status = self.client.request("GET", "/api/security/status")[1]
        self.assertTrue(status["mfaEnabled"])
        self.assertEqual(status["recoveryCodesRemaining"], 10)
        self.assertEqual(self.client.request("POST", "/api/security/mfa/setup", {"password": PASSWORD})[0], 409)

    def test_password_alone_cannot_authorize_an_mfa_user(self):
        self.enable_mfa()
        client, _ = self.challenge()
        self.assertIsNone(client.request("GET", "/api/auth/me")[1]["user"])
        self.assertEqual(client.request("PATCH", "/api/account", {"name": "Attack"})[0], 401)
        self.assertEqual(client.request("GET", "/api/security/sessions")[0], 401)

    def test_fresh_totp_completes_signin_and_is_not_replayable(self):
        secret, _ = self.enable_mfa()
        client, challenge = self.challenge()
        result = self.verify_next(secret, client, challenge)
        self.assertEqual(result[0], 200)
        self.assertEqual(result[1]["user"]["email"], "maya@example.com")
        self.assertIn("HttpOnly", result[2]["Set-Cookie"])
        self.assertIsNotNone(client.request("GET", "/api/auth/me")[1]["user"])
        self.assertEqual(client.request("POST", "/api/auth/verify", {"challenge": challenge, "code": secret})[0], 401)
        replay, second_challenge = self.challenge()
        with self.app.connect() as connection:
            counter = connection.execute("SELECT mfa_last_counter FROM users WHERE email='maya@example.com'").fetchone()[0]
        self.assertEqual(replay.request("POST", "/api/auth/verify", {"challenge": second_challenge, "code": security_core.totp(secret, counter * 30)})[0], 401)

    def test_recovery_codes_are_one_use_and_can_be_regenerated(self):
        _, codes = self.enable_mfa()
        first, challenge = self.challenge()
        self.assertEqual(first.request("POST", "/api/auth/verify", {"challenge": challenge, "code": codes[0]})[0], 200)
        self.assertEqual(first.request("GET", "/api/security/status")[1]["recoveryCodesRemaining"], 9)
        repeat, repeat_challenge = self.challenge()
        self.assertEqual(repeat.request("POST", "/api/auth/verify", {"challenge": repeat_challenge, "code": codes[0]})[0], 401)
        self.assertEqual(first.request("POST", "/api/security/mfa/recovery-codes", {"password": "incorrect", "code": codes[1]})[0], 400)
        status, regenerated, _ = first.request("POST", "/api/security/mfa/recovery-codes", {"password": PASSWORD, "code": codes[1]})
        self.assertEqual(status, 200)
        self.assertEqual(len(regenerated["recoveryCodes"]), 10)
        self.assertFalse(set(codes) & set(regenerated["recoveryCodes"]))
        invalid, pending = self.challenge()
        self.assertEqual(invalid.request("POST", "/api/auth/verify", {"challenge": pending, "code": codes[2]})[0], 401)

    def test_disable_requires_both_factors_and_revokes_old_sessions(self):
        _, codes = self.enable_mfa()
        other, challenge = self.challenge()
        self.assertEqual(other.request("POST", "/api/auth/verify", {"challenge": challenge, "code": codes[0]})[0], 200)
        self.assertEqual(self.client.request("POST", "/api/security/mfa/disable", {"password": PASSWORD, "code": "000000"})[0], 400)
        self.assertEqual(self.client.request("POST", "/api/security/mfa/disable", {"password": PASSWORD, "code": codes[1]})[0], 200)
        self.assertFalse(self.client.request("GET", "/api/security/status")[1]["mfaEnabled"])
        self.assertIsNone(other.request("GET", "/api/auth/me")[1]["user"])
        self.assertIn("user", Client(self.app).login()[1])

    def test_challenges_expire_are_bound_to_client_and_limit_attempts(self):
        self.enable_mfa()
        expired, challenge = self.challenge()
        with self.app.connect() as connection:
            connection.execute("UPDATE mfa_challenges SET expires_at=?", (int(time.time()) - 1,))
        self.assertEqual(expired.request("POST", "/api/auth/verify", {"challenge": challenge, "code": "123456"})[0], 401)
        different, challenge = self.challenge()
        self.assertEqual(different.request("POST", "/api/auth/verify", {"challenge": challenge, "code": "123456"}, extra_headers={"User-Agent": "a different client"})[0], 401)
        limited, challenge = self.challenge()
        for _ in range(5):
            self.assertEqual(limited.request("POST", "/api/auth/verify", {"challenge": challenge, "code": "invalid"})[0], 401)
        self.assertEqual(limited.request("POST", "/api/auth/verify", {"challenge": challenge, "code": "invalid"})[0], 401)
        self.assertEqual(Client(self.app).login()[0], 429)

    def test_sessions_only_expose_owned_metadata_and_are_revocable(self):
        other = Client(self.app)
        self.assertEqual(other.login()[0], 200)
        rows = self.client.request("GET", "/api/security/sessions")[1]["sessions"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(row["current"] for row in rows), 1)
        self.assertTrue(all(set(row) == {"id", "created_at", "last_seen", "expires_at", "ip", "device", "current"} for row in rows))
        stranger = Client(self.app)
        self.assertEqual(stranger.register(email="stranger@example.com")[0], 201)
        target = next(row["id"] for row in rows if not row["current"])
        self.assertEqual(stranger.request("DELETE", "/api/security/sessions/" + target)[0], 404)
        self.assertEqual(self.client.request("DELETE", "/api/security/sessions/" + target)[0], 200)
        self.assertIsNone(other.request("GET", "/api/auth/me")[1]["user"])
        self.assertEqual(self.client.request("POST", "/api/security/sessions/revoke-others")[1]["revoked"], 0)
        current = self.client.request("GET", "/api/security/sessions")[1]["sessions"][0]["id"]
        self.assertTrue(self.client.request("DELETE", "/api/security/sessions/" + current)[1]["current"])
        self.assertIsNone(self.client.request("GET", "/api/auth/me")[1]["user"])

    def test_admin_idle_and_absolute_expiry_are_server_enforced(self):
        admin = self.admin()
        with self.app.connect() as connection:
            connection.execute("UPDATE sessions SET last_seen=? WHERE user_id=(SELECT id FROM users WHERE role='admin')", (int(time.time()) - 1801,))
        self.assertIsNone(admin.request("GET", "/api/auth/me")[1]["user"])
        self.assertEqual(admin.request("GET", "/api/admin/products")[0], 401)
        self.assertIn("Max-Age=28800", admin.login(email="owner@example.com", remember=True)[2]["Set-Cookie"])
        with self.app.connect() as connection:
            connection.execute("UPDATE sessions SET created_at=? WHERE user_id=(SELECT id FROM users WHERE role='admin')", (int(time.time()) - 28801,))
        self.assertIsNone(admin.request("GET", "/api/auth/me")[1]["user"])
        self.assertIsNotNone(self.client.request("GET", "/api/auth/me")[1]["user"])

    def test_failed_login_limits_persist_across_server_restarts(self):
        for _ in range(5):
            self.assertEqual(Client(self.app).login(email="unknown@example.com", password="wrong")[0], 401)
        self.app.shutdown(); self.app.server_close(); self.thread.join(timeout=5)
        self.app = server.make_server(port=0, database=self.database, catalog=self.catalog, root=self.root)
        self.thread = threading.Thread(target=self.app.serve_forever, daemon=True); self.thread.start()
        blocked = Client(self.app).login(email="unknown@example.com", password="wrong")
        self.assertEqual(blocked[0], 429)
        self.assertEqual(blocked[2]["Retry-After"], "900")
        self.assertIn("15 minutes", blocked[1]["error"])

    def test_parallel_password_guesses_share_an_atomic_failure_budget(self):
        barrier = threading.Barrier(8)
        def failed_verification(*args):
            barrier.wait(timeout=8)
            return False
        def attempt(_):
            return Client(self.app).login(email="burst@example.com", password="wrong")[0]
        with mock.patch.object(server, "verify_password", failed_verification):
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                statuses = list(executor.map(attempt, range(8)))
        self.assertEqual(statuses.count(401), 5)
        self.assertEqual(statuses.count(429), 3)

    def test_parallel_mfa_challenges_share_an_atomic_user_failure_budget(self):
        self.enable_mfa()
        challenges = [self.challenge()[1] for _ in range(4)]
        barrier = threading.Barrier(12)
        original = server.VeloraHandler.check_mfa_failures
        def paused_check(handler, user):
            original(handler, user)
            barrier.wait(timeout=8)
        def attempt(index):
            return Client(self.app).request("POST", "/api/auth/verify", {"challenge": challenges[index % 4], "code": "invalid"})[0]
        with mock.patch.object(server.VeloraHandler, "check_mfa_failures", paused_check):
            with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
                statuses = list(executor.map(attempt, range(12)))
        self.assertEqual(statuses.count(401), 10)
        self.assertEqual(statuses.count(429), 2)

    def test_security_events_redact_secrets_and_show_actual_counts(self):
        setup = self.setup_mfa()
        result = self.client.request("POST", "/api/security/mfa/enable", {"code": security_core.totp(setup["secret"])})[1]
        Client(self.app).login(email="masked@example.com", password="wrong")
        self.client.request("GET", "/api/admin/security")
        admin = self.admin()
        dashboard = admin.request("GET", "/api/admin/security")[1]
        self.assertEqual(dashboard["summary"]["failedLogins24h"], 1)
        self.assertGreaterEqual(dashboard["summary"]["blockedAttempts24h"], 1)
        self.assertEqual(dashboard["summary"]["totalAdmins"], 1)
        serialized = json.dumps(dashboard)
        self.assertTrue(any(event["email_hint"] == "m***@example.com" for event in dashboard["events"]))
        self.assertFalse(any(secret in serialized for secret in [PASSWORD, setup["secret"], *result["recoveryCodes"], self.client.cookie.split("=", 1)[1]]), "Security events exposed a credential")
        self.assertTrue(all(set(event) == {"id", "event_type", "severity", "actor_name", "email_hint", "ip", "detail", "created_at"} for event in dashboard["events"]))

    def test_mfa_credentials_are_derived_and_recovery_codes_are_hashed(self):
        secret, codes = self.enable_mfa()
        with self.app.connect() as connection:
            dump = "\n".join(connection.iterdump())
        self.assertFalse(secret in dump, "The authenticator secret was stored in the database")
        self.assertFalse(any(code in dump or code.replace("-", "") in dump for code in codes), "Recovery codes were stored in plaintext")
        self.assertEqual(len(self.database.with_name("security.key").read_bytes()), 32)
        self.assertEqual(self.client.request("GET", "/.velora/security.key")[0], 404)
        self.assertEqual(self.client.request("GET", "/security_core.py")[0], 404)

    def test_missing_or_mismatched_key_fails_closed(self):
        self.enable_mfa()
        self.app.shutdown(); self.app.server_close(); self.thread.join(timeout=5)
        path = self.database.with_name("security.key")
        key = path.read_bytes()
        path.unlink()
        with self.assertRaisesRegex(ValueError, "key is missing"):
            server.make_server(port=0, database=self.database, catalog=self.catalog, root=self.root)
        path.write_bytes(secrets.token_bytes(32))
        with self.assertRaisesRegex(ValueError, "does not match"):
            server.make_server(port=0, database=self.database, catalog=self.catalog, root=self.root)
        path.write_bytes(key)

    def test_enabling_mfa_invalidates_an_in_flight_password_only_login(self):
        setup = self.setup_mfa()
        verified, resume = threading.Event(), threading.Event()
        result = {}
        original = server.VeloraHandler.issue_session
        def paused_issue(handler, user, remember=False, mfa_verified=False):
            if handler.path_only == "/api/auth/login":
                verified.set(); resume.wait(timeout=8)
            return original(handler, user, remember, mfa_verified)
        def login():
            result["status"] = Client(self.app).login()[0]
        with mock.patch.object(server.VeloraHandler, "issue_session", paused_issue):
            worker = threading.Thread(target=login, daemon=True); worker.start()
            try:
                self.assertTrue(verified.wait(timeout=5))
                self.assertEqual(self.client.request("POST", "/api/security/mfa/enable", {"code": security_core.totp(setup["secret"])})[0], 200)
            finally:
                resume.set(); worker.join(timeout=8)
        self.assertEqual(result["status"], 401)
        self.assertEqual(len(self.client.request("GET", "/api/security/sessions")[1]["sessions"]), 1)

    def test_password_change_invalidates_pending_mfa_challenges(self):
        _, codes = self.enable_mfa()
        pending, challenge = self.challenge()
        response = self.client.request("PATCH", "/api/account", {"currentPassword": PASSWORD, "newPassword": "a changed strong password"})
        self.assertEqual(response[0], 200)
        self.assertEqual(pending.request("POST", "/api/auth/verify", {"challenge": challenge, "code": codes[0]})[0], 401)
        self.assertIsNotNone(self.client.request("GET", "/api/auth/me")[1]["user"])

    def test_security_mutations_validate_fields_and_require_csrf(self):
        actions = (("/api/security/mfa/setup", {"password": PASSWORD}), ("/api/security/mfa/enable", {"code": "123456"}),
                   ("/api/security/mfa/disable", {"password": PASSWORD, "code": "123456"}), ("/api/security/mfa/recovery-codes", {"password": PASSWORD, "code": "123456"}),
                   ("/api/security/sessions/revoke-others", {}))
        public = Client(self.app)
        for path, body in actions:
            self.assertEqual(public.request("POST", path, body)[0], 401)
            self.assertEqual(self.client.request("POST", path, body, token=False)[0], 403)
            self.assertEqual(self.client.request("POST", path, {**body, "role": "admin"})[0], 400)
        self.assertEqual(self.client.request("PUT", "/api/security/status")[0], 405)

    def test_response_headers_private_cache_and_exact_qr_vendor_allowlist(self):
        response = self.client.request("GET", "/account.html")
        self.assertEqual(response[2]["Cache-Control"], "no-store")
        self.assertEqual(response[2]["Cross-Origin-Opener-Policy"], "same-origin")
        self.assertEqual(response[2]["Cross-Origin-Resource-Policy"], "same-origin")
        self.assertIn("camera=()", response[2]["Permissions-Policy"])
        self.assertNotIn("Strict-Transport-Security", response[2])
        self.assertEqual(self.client.request("GET", "/js/vendor/qrcodegen.js")[0], 200)
        self.assertEqual(self.client.request("GET", "/js/vendor/private.js")[0], 404)
        self.assertEqual(self.client.request("POST", "/api/auth/login", raw="[" * 1200 + "]" * 1200)[0], 400)

    def test_security_event_retention_is_bounded(self):
        with self.app.connect() as connection:
            connection.executemany("INSERT INTO security_events (event_type,severity,actor_name,email_hint,ip,detail,created_at,occurred_at) VALUES ('test','info','','','','',?,?)", [(server.now_iso(), int(time.time()))] * 2005)
            connection.execute("INSERT INTO security_events (event_type,severity,actor_name,email_hint,ip,detail,created_at,occurred_at) VALUES ('expired','info','','','','',?,?)", (server.now_iso(), int(time.time()) - 31 * 86400))
        self.app.security_event("check", detail="A bounded retention check.")
        with self.app.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM security_events").fetchone()[0], 2000)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM security_events WHERE event_type='expired'").fetchone()[0], 0)


class ResponseDisconnectTests(unittest.TestCase):
    def test_error_response_handles_disconnected_client(self):
        for exception in (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError):
            for phase in ("headers", "body"):
                with self.subTest(exception=exception.__name__, phase=phase):
                    handler = object.__new__(server.VeloraHandler)
                    handler.command = "GET"
                    handler.server = mock.Mock(secure_cookies=False)
                    handler.send_response = mock.Mock()
                    handler.send_header = mock.Mock()
                    handler.end_headers = mock.Mock(side_effect=exception() if phase == "headers" else None)
                    handler.wfile = mock.Mock()
                    if phase == "body":
                        handler.wfile.write.side_effect = exception()
                    handler.send_json(404, {"error": "This page was not found."})


if __name__ == "__main__":
    unittest.main()
