"""Adversarial request and authorization checks against disposable Velora data."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file


import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

import server
import security_core
from test_auth_server import Client, PASSWORD
from test_catalog_server import png


class HardeningServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = server.hash_password(PASSWORD)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "assets").mkdir()
        (self.root / "assets/portrait.jpg").write_bytes(b"portrait fixture")
        for name in ("index.html", "login.html", "register.html", "account.html", "admin.html", "intranet.html", "404.html"):
            (self.root / name).write_text("<!doctype html><title>Page fixture</title>", encoding="utf-8")
        self.catalog = self.root / "product-catalog.json"
        self.catalog.write_text(json.dumps({"products": [{
            "id": "example", "name": "An outfit", "image": "assets/portrait.jpg",
            "founder": "A designer", "collection": "THE TAILORED EDIT", "price": 100,
            "description": "An illustrative outfit.", "published": True,
        }]}), encoding="utf-8")
        self.app = server.make_server(port=0, database=self.root / ".velora/accounts.sqlite3", catalog=self.catalog, root=self.root)
        self.app.RequestHandlerClass.log_message = lambda *args: None
        with self.app.connect() as db:
            db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,'admin',?)",
                       ("Test owner", "owner@example.test", self.password_hash, server.now_iso()))
        self.thread = threading.Thread(target=self.app.serve_forever, daemon=True)
        self.thread.start()
        self.client = Client(self.app)

    def tearDown(self):
        self.app.shutdown()
        self.app.server_close()
        self.thread.join(timeout=5)
        self.directory.cleanup()

    def admin(self):
        client = Client(self.app)
        self.assertEqual(client.login(email="owner@example.test")[0], 200)
        return client

    def customer(self):
        client = Client(self.app)
        self.assertEqual(client.register()[0], 201)
        return client

    def raw(self, method="POST", path="/api/auth/login", headers=(), body=b"{}"):
        host = f"127.0.0.1:{self.app.server_port}"
        lines = [f"{method} {path} HTTP/1.1", f"Host: {host}", *headers]
        with socket.create_connection(("127.0.0.1", self.app.server_port), timeout=3) as connection:
            connection.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("latin-1") + body)
            response = http.client.HTTPResponse(connection)
            response.begin()
            content = response.read()
            return response.status, content, dict(response.getheaders())

    def origin(self):
        return f"Origin: http://127.0.0.1:{self.app.server_port}"

    def assert_security_headers(self, headers):
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        self.assertNotIn("Python", headers.get("Server", ""))

    def test_private_pages_are_authorized_before_html_is_served(self):
        for page in ("account.html", "admin.html", "intranet.html"):
            for method in ("GET", "HEAD"):
                status, content, headers = self.client.request(method, "/" + page)
                self.assertEqual(status, 302)
                self.assertEqual(headers["Location"], "/login.html?next=" + page)
                self.assertEqual(content, b"")
                self.assert_security_headers(headers)
        customer = self.customer()
        self.assertEqual(customer.request("GET", "/account.html")[0], 200)
        self.assertEqual(customer.request("GET", "/admin.html")[0], 403)
        self.assertEqual(customer.request("GET", "/intranet.html")[0], 403)
        self.assertEqual(customer.request("GET", "/%61dmin.html")[0], 403)
        if os.name == "nt":
            self.assertEqual(customer.request("GET", "/ADMIN.HTML")[0], 403)
        admin = self.admin()
        self.assertEqual(admin.request("GET", "/admin.html")[0], 200)
        status, _, headers = admin.request("GET", "/intranet.html")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(admin.request("POST", "/api/auth/logout")[0], 200)
        self.assertEqual(admin.request("GET", "/admin.html")[0], 302)

    def test_missing_static_pages_use_the_html_404_but_api_errors_remain_json(self):
        status, page, headers = self.client.request("GET", "/missing-page.html")
        self.assertEqual(status, 404)
        self.assertIn(b"Page fixture", page)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertEqual(headers["Cache-Control"], "no-store")

        status, page, _ = self.client.request("HEAD", "/missing-page.html")
        self.assertEqual(status, 404)
        self.assertEqual(page, b"")

        status, payload, headers = self.client.request("GET", "/api/missing")
        self.assertEqual(status, 404)
        self.assertEqual(payload, {"error": "This page was not found."})
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")

    def test_vendor_module_allowlist_serves_required_scripts_without_exposing_other_files(self):
        allowed = (
            "js/vendor/qrcodegen.js",
            "js/vendor/three/three.module.js",
            "js/vendor/three/three.core.js",
            "js/vendor/three/addons/controls/OrbitControls.js",
            "js/vendor/three/addons/exporters/GLTFExporter.js",
        )
        blocked = (
            "js/vendor/unlisted.js",
            "js/vendor/three/addons/controls/Unlisted.js",
            "js/vendor/three/source.json",
        )
        script = b"export const fixture = true;\n"
        for relative in (*allowed, *blocked):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(script)
        for relative in allowed:
            with self.subTest(path=relative):
                status, content, headers = self.client.request("GET", "/" + relative + "?v=fixture")
                self.assertEqual(status, 200)
                self.assertEqual(content, script)
                self.assertIn(headers["Content-Type"].split(";", 1)[0], {"text/javascript", "application/javascript"})
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
                status, content, headers = self.client.request("HEAD", "/" + relative)
                self.assertEqual(status, 200)
                self.assertEqual(content, b"")
                self.assertEqual(int(headers["Content-Length"]), len(script))
        for relative in blocked:
            with self.subTest(path=relative):
                status, content, headers = self.client.request("GET", "/" + relative)
                self.assertEqual(status, 404)
                self.assertIn(b"Page fixture", content)
                self.assertNotIn(script, content)
                self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
                self.assert_security_headers(headers)

    def test_all_admin_read_endpoints_deny_anonymous_and_customer_requests(self):
        customer = self.customer()
        for path in ("overview", "products", "customers", "activity", "security", "business-details"):
            with self.subTest(path=path):
                self.assertEqual(self.client.request("GET", "/api/admin/" + path)[0], 401)
                self.assertEqual(customer.request("GET", "/api/admin/" + path)[0], 403)

    def test_mutations_need_admin_session_csrf_and_origin(self):
        customer, admin = self.customer(), self.admin()
        actions = (("POST", "/api/admin/products"), ("PATCH", "/api/admin/products/example"),
                   ("DELETE", "/api/admin/products/example"), ("POST", "/api/admin/products/example/duplicate"),
                   ("POST", "/api/admin/uploads"), ("PATCH", "/api/admin/business-details"))
        for method, path in actions:
            with self.subTest(path=path, method=method):
                self.assertEqual(self.client.request(method, path, {})[0], 401)
                self.assertEqual(customer.request(method, path, {})[0], 403)
                self.assertEqual(admin.request(method, path, {}, token=False)[0], 403)
                self.assertEqual(admin.request(method, path, {}, extra_headers={"Origin": "https://untrusted.example"})[0], 403)

    def test_cors_is_same_origin_and_preflights_do_not_grant_access(self):
        status, _, headers = self.client.request("GET", "/api/catalog", extra_headers={"Origin": "https://untrusted.example"})
        self.assertEqual(status, 200)
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        status, _, headers = self.client.request("OPTIONS", "/api/admin/products", extra_headers={
            "Origin": "https://untrusted.example", "Access-Control-Request-Method": "PATCH"})
        self.assertEqual(status, 405)
        self.assert_security_headers(headers)

    def test_ambiguous_framing_and_duplicate_origins_are_rejected(self):
        base = [self.origin(), "Content-Type: application/json"]
        for extra in (("Content-Length: 2", "Content-Length: 2"),
                      ("Content-Length: +2",), ("Content-Length: 0_2",),
                      ("Content-Length: 2", "Transfer-Encoding: identity")):
            self.assertEqual(self.raw(headers=(*base, *extra))[0], 400)
        self.assertEqual(self.raw(headers=(*base, "Content-Length: 2", "Origin: https://untrusted.example"))[0], 403)
        self.assertEqual(self.raw(headers=(*base, "Content-Length: 2", "Content-Type: text/plain"))[0], 415)
        self.assertEqual(self.raw(method="GET", path="/api/catalog", headers=("Content-Length: 2",))[0], 400)

    def test_duplicate_cookies_and_csrf_headers_fail_closed(self):
        customer = self.customer()
        self.assertEqual(self.raw(method="GET", path="/api/auth/me", headers=("Cookie: " + customer.cookie, "Cookie: " + customer.cookie), body=b"")[0], 400)
        headers = (self.origin(), "Content-Type: application/json", "Content-Length: 2", "Cookie: " + customer.cookie,
                   "X-CSRF-Token: " + customer.csrf, "X-CSRF-Token: " + customer.csrf)
        self.assertEqual(self.raw(path="/api/auth/logout", headers=headers)[0], 403)

    def test_duplicate_json_and_invalid_unicode_are_form_errors(self):
        for body in ('{"email":"a@example.test","email":"b@example.test"}',
                     '{"name":"\\ud800"}', '{"\\udfff":"value"}'):
            self.assertEqual(self.client.request("POST", "/api/auth/register", raw=body)[0], 400)
        self.assertEqual(self.raw(headers=(self.origin(), "Content-Type: application/json", "Content-Length: 3"), body=b'{\xff}')[0], 400)
        self.assertEqual(self.raw(headers=(self.origin(), "Content-Type: application/json; charset=utf-16", "Content-Length: 2"))[0], 415)

    def test_unknown_methods_and_unexpected_failures_use_safe_error_responses(self):
        status, content, headers = self.raw(method="TRACE", path="/", body=b"")
        self.assertEqual(status, 501)
        self.assert_security_headers(headers)
        self.assertNotIn(b"TRACE", content)
        with mock.patch.object(server.VeloraHandler, "handle_api", side_effect=RuntimeError("private diagnostic fixture")):
            status, content, headers = self.client.request("GET", "/api/catalog")
        self.assertEqual(status, 500)
        self.assert_security_headers(headers)
        self.assertNotIn("private diagnostic", json.dumps(content))
        self.assertNotIn("Traceback", json.dumps(content))

    def test_invalid_request_targets_and_oversized_headers_are_rejected(self):
        for path in ("https://untrusted.example/api/catalog", "/api/catalog#unexpected-fragment"):
            self.assertEqual(self.raw(method="GET", path=path, body=b"")[0], 400)
        self.assertEqual(self.raw(method="GET", path="/" + "x" * 4096, body=b"")[0], 414)
        self.assertEqual(self.raw(method="GET", path="/", headers=("X-Large: " + "x" * 33000,), body=b"")[0], 431)

    def test_request_budgets_and_rate_key_memory_are_bounded(self):
        original = self.app.rate_limit
        def small_limit(key, limit, window):
            return original(key, 2 if key[0] == "api-request" else limit, window)
        with mock.patch.object(self.app, "rate_limit", side_effect=small_limit):
            self.assertEqual(self.client.request("GET", "/api/health")[0], 200)
            self.assertEqual(self.client.request("GET", "/api/health")[0], 200)
            blocked = self.client.request("GET", "/api/health")
            self.assertEqual(blocked[0], 429)
            self.assertEqual(blocked[2]["Retry-After"], "60")
        self.app.rate_events.clear()
        with mock.patch.object(server, "MAX_RATE_KEYS", 4):
            for index in range(4):
                self.app.rate_limit(("unique", index), 2, 60)
            with self.assertRaises(server.APIError):
                self.app.rate_limit(("unique", 5), 2, 60)
            self.assertEqual(len(self.app.rate_events), 4)
            with mock.patch.object(server.time, "monotonic", return_value=time.monotonic() + 4000):
                self.app.rate_limit(("new", 6), 2, 60)
            self.assertEqual(len(self.app.rate_events), 1)

    def test_request_worker_exhaustion_returns_retryable_error(self):
        self.app.request_workers = threading.BoundedSemaphore(1)
        started, release = threading.Event(), threading.Event()
        original = server.VeloraHandler.handle
        def held(handler):
            started.set()
            release.wait(4)
            original(handler)
        first = socket.create_connection(("127.0.0.1", self.app.server_port), timeout=3)
        try:
            with mock.patch.object(server.VeloraHandler, "handle", held):
                first.sendall(f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{self.app.server_port}\r\n\r\n".encode())
                self.assertTrue(started.wait(2))
                status, data, headers = self.raw(method="GET", path="/", body=b"")
                self.assertEqual(status, 503)
                self.assertEqual(headers["Retry-After"], "1")
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assert_security_headers(headers)
                self.assertEqual(json.loads(data), {"error": "Please try again soon."})
                release.set()
                response = http.client.HTTPResponse(first)
                response.begin()
                self.assertEqual(response.status, 200)
                response.read()
            deadline = time.monotonic() + 2
            while not self.app.request_workers.acquire(blocking=False):
                self.assertLess(time.monotonic(), deadline)
                time.sleep(.01)
            self.app.request_workers.release()
            self.assertEqual(self.client.request("GET", "/")[0], 200)
        finally:
            release.set()
            first.close()

    def revoke(self, client, *, downgrade=False):
        digest = hashlib.sha256(client.cookie.split("=", 1)[1].encode()).hexdigest()
        with self.app.connect() as db:
            if downgrade:
                db.execute("UPDATE users SET role='customer' WHERE email='owner@example.test'")
            else:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (digest,))

    def test_revocation_and_role_change_during_validation_prevent_catalog_writes(self):
        original = server.VeloraHandler.validate_product_fields
        for downgrade in (False, True):
            with self.app.connect() as db:
                db.execute("UPDATE users SET role='admin' WHERE email='owner@example.test'")
            admin = self.admin()
            def validate(handler, payload, creating=False):
                values = original(handler, payload, creating)
                self.revoke(admin, downgrade=downgrade)
                return values
            with mock.patch.object(server.VeloraHandler, "validate_product_fields", validate):
                status = admin.request("PATCH", "/api/admin/products/example", {"price": 999})[0]
            self.assertEqual(status, 403 if downgrade else 401)
            with self.app.connect() as db:
                self.assertEqual(db.execute("SELECT price FROM products WHERE id='example'").fetchone()[0], 100)

    def test_revocation_during_create_trash_and_upload_prevents_side_effects(self):
        original_validate = server.VeloraHandler.validate_product_fields
        admin = self.admin()
        def validate(handler, payload, creating=False):
            values = original_validate(handler, payload, creating)
            self.revoke(admin)
            return values
        payload = {"name": "Another outfit", "images": ["assets/portrait.jpg"], "founder": "A designer",
                   "collection": "THE TAILORED EDIT", "price": 200, "description": "Another concept."}
        with mock.patch.object(server.VeloraHandler, "validate_product_fields", validate):
            self.assertEqual(admin.request("POST", "/api/admin/products", payload)[0], 401)
        admin = self.admin()
        original_action = server.VeloraHandler.product_action
        def action(handler, *args):
            self.revoke(admin)
            return original_action(handler, *args)
        with mock.patch.object(server.VeloraHandler, "product_action", action):
            self.assertEqual(admin.request("DELETE", "/api/admin/products/example", {})[0], 401)
        admin = self.admin()
        original_extension = server.image_extension
        def extension(data):
            self.revoke(admin)
            return original_extension(data)
        with mock.patch.object(server, "image_extension", extension):
            self.assertEqual(admin.request("POST", "/api/admin/uploads", {"name": "example.png", "data": "data:image/png;base64," + base64.b64encode(png()).decode()})[0], 401)
        with self.app.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM products").fetchone()[0], 1)
            self.assertIsNone(db.execute("SELECT deleted_at FROM products WHERE id='example'").fetchone()[0])
        self.assertFalse((self.root / "assets/uploads").exists())

    def test_fresh_write_check_rejects_admin_timeouts(self):
        admin = self.admin()
        original = server.VeloraHandler.validate_product_fields
        def validate(handler, payload, creating=False):
            values = original(handler, payload, creating)
            with self.app.connect() as db:
                db.execute("UPDATE sessions SET last_seen=? WHERE user_id=(SELECT id FROM users WHERE email='owner@example.test')", (int(time.time()) - security_core.ADMIN_IDLE_SECONDS,))
            return values
        with mock.patch.object(server.VeloraHandler, "validate_product_fields", validate):
            self.assertEqual(admin.request("PATCH", "/api/admin/products/example", {"price": 999})[0], 401)

    def test_configured_database_is_private_even_with_a_public_asset_extension(self):
        app = server.make_server(port=0, database=self.root / "assets/private.jpg", catalog=self.catalog, root=self.root)
        thread = threading.Thread(target=app.serve_forever, daemon=True)
        thread.start()
        try:
            client = Client(app)
            for path in ("/assets/private.jpg", "/assets/private.jpg-wal", "/assets/private.jpg-shm", "/assets/security.key"):
                self.assertEqual(client.request("GET", path)[0], 404)
        finally:
            app.shutdown()
            app.server_close()
            thread.join(timeout=5)

    def test_sqlite_security_flags_disable_unsafe_features(self):
        with self.app.connect() as db:
            self.assertEqual(db.execute("PRAGMA trusted_schema").fetchone()[0], 0)
            self.assertEqual(db.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(db.execute("PRAGMA secure_delete").fetchone()[0], 1)
            self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0], "delete")
            self.assertEqual(db.getlimit(server.sqlite3.SQLITE_LIMIT_ATTACHED), 0)
            if hasattr(db, "getconfig"):
                self.assertTrue(db.getconfig(server.sqlite3.SQLITE_DBCONFIG_DEFENSIVE))
                self.assertFalse(db.getconfig(server.sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION))
            with self.assertRaises(server.sqlite3.DatabaseError):
                db.execute("SELECT load_extension('does-not-exist')")
        if os.name != "nt":
            self.assertEqual(self.app.database.stat().st_mode & 0o777, 0o600)
            self.assertEqual(self.app.database.parent.stat().st_mode & 0o777, 0o700)

    def test_new_password_policy_and_existing_hash_compatibility(self):
        with self.assertRaises(server.APIError):
            server.validate_password("a" * 14)
        self.assertEqual(server.validate_password("a" * 15), "a" * 15)
        self.assertEqual(server.validate_password("a" * 128), "a" * 128)
        legacy = server.hash_password("a" * 12)
        self.assertTrue(server.verify_password("a" * 12, legacy))
        self.assertFalse(server.verify_password("other value", legacy))
        self.assertFalse(server.verify_password("a" * 12, "pbkdf2_sha256$999999999$" + "a" * 48 + "$" + "a" * 64))
        self.assertFalse(server.verify_password("a" * 12, "pbkdf2_sha256$600000$broken$" + "a" * 64))
        self.assertNotEqual(server.hash_password(PASSWORD), self.password_hash)

    def test_health_check_discloses_only_service_and_security_revision(self):
        status, result, headers = self.client.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(result, {"service": "velora", "securityRevision": "2026-11-01.2"})
        self.assert_security_headers(headers)
        self.assertEqual(self.client.request("HEAD", "/api/health")[1], b"")
        self.assertEqual(self.client.request("POST", "/api/health", {})[0], 405)


if __name__ == "__main__":
    unittest.main()
