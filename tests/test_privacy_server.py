"""Consent and account erasure checks run only against disposable SQLite databases."""

import concurrent.futures
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import server
import security_core
from test_auth_server import Client, PASSWORD


class PrivacyServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = server.hash_password(PASSWORD)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "assets").mkdir()
        (self.root / "assets/portrait.jpg").write_bytes(b"image")
        catalog = self.root / "catalog.json"
        catalog.write_text(json.dumps({"products": [{
            "id": "sample", "name": "Sample suit", "image": "assets/portrait.jpg",
            "founder": "Victoria Mendez", "collection": "THE TAILORED EDIT",
            "price": 100, "description": "An illustrative suit.", "published": True,
        }]}), encoding="utf-8")
        self.app = server.make_server(port=0, database=self.root / ".velora/accounts.sqlite3", catalog=catalog, root=self.root)
        self.app.RequestHandlerClass.log_message = lambda *args: None
        with self.app.connect() as connection:
            connection.execute("INSERT INTO users (name,email,password_hash,role,created_at) VALUES (?,?,?,'admin',?)",
                               ("Owner", "owner@example.com", self.password_hash, server.now_iso()))
        self.thread = threading.Thread(target=self.app.serve_forever, daemon=True)
        self.thread.start()
        self.client = Client(self.app)

    def tearDown(self):
        self.app.shutdown()
        self.app.server_close()
        self.thread.join(timeout=5)
        self.directory.cleanup()

    def register(self, client=None, **changes):
        data = {"name": "Maya Bennett", "email": "maya@example.com", "password": PASSWORD,
                "terms": True, "ageConfirmed": True}
        data.update(changes)
        return (client or self.client).request("POST", "/api/auth/register", data)

    def delete(self, client=None, **changes):
        return (client or self.client).request("DELETE", "/api/account", {"password": PASSWORD, **changes})

    def enable_mfa(self):
        setup = self.client.request("POST", "/api/security/mfa/setup", {"password": PASSWORD})
        self.assertEqual(setup[0], 200)
        enabled = self.client.request("POST", "/api/security/mfa/enable", {"code": security_core.totp(setup[1]["secret"])})
        self.assertEqual(enabled[0], 200)
        return setup[1]["secret"], enabled[1]["recoveryCodes"]

    def test_consent_requires_explicit_boolean_and_does_not_collect_birthdate(self):
        for value in (False, None, "true", 1):
            with self.subTest(value=value):
                self.assertEqual(self.register(ageConfirmed=value)[0], 400)
        self.assertEqual(self.register(terms=False)[0], 400)
        self.assertEqual(self.register(birthdate="2000-01-01")[0], 400)
        status, result, _ = self.register()
        self.assertEqual(status, 201)
        with self.app.connect() as connection:
            consent = dict(connection.execute("SELECT * FROM user_consents WHERE user_id=?", (result["user"]["id"],)).fetchone())
            owner_consent = connection.execute("SELECT * FROM user_consents WHERE user_id=(SELECT id FROM users WHERE role='admin')").fetchone()
        self.assertEqual(consent["terms_version"], "2026-11-01")
        self.assertEqual(consent["age_minimum"], 16)
        self.assertEqual(consent["terms_accepted_at"], consent["age_confirmed_at"])
        self.assertIsNone(owner_consent, "Do not fabricate consent for existing accounts")
        self.assertEqual(set(consent), {"user_id", "terms_version", "terms_accepted_at", "age_minimum", "age_confirmed_at"})

    def test_registration_accepts_only_email_password_and_required_confirmations(self):
        payload = {"email": "minimal@example.com", "password": PASSWORD, "terms": True, "ageConfirmed": True}
        status, result, _ = self.client.request("POST", "/api/auth/register", payload)
        self.assertEqual(status, 201)
        self.assertEqual(result["user"]["name"], "Member")
        self.assertEqual(self.register(Client(self.app), email="blank@example.com", name="  ")[1]["user"]["name"], "Member")
        self.assertEqual(self.register(Client(self.app), email="invalid@example.com", name=23)[0], 400)

    def test_missing_age_confirmation_is_rejected(self):
        payload = {"email": "minimal@example.com", "password": PASSWORD, "terms": True}
        self.assertEqual(self.client.request("POST", "/api/auth/register", payload)[0], 400)

    def test_deletion_requires_session_origin_csrf_and_current_password(self):
        self.assertEqual(self.delete()[0], 401)
        self.assertEqual(self.register()[0], 201)
        self.assertEqual(self.client.request("DELETE", "/api/account", {"password": PASSWORD}, token=False)[0], 403)
        self.assertEqual(self.client.request("DELETE", "/api/account", {"password": PASSWORD}, origin=False)[0], 403)
        self.assertEqual(self.delete(password="incorrect password")[0], 400)
        self.assertEqual(self.delete(user_id=1)[0], 400)
        self.assertEqual(self.client.request("DELETE", "/api/account", {})[0], 400)
        self.assertIsNotNone(self.client.request("GET", "/api/auth/me")[1]["user"])

    def test_customer_erasure_revokes_sessions_and_anonymizes_history(self):
        user = self.register()[1]["user"]
        other = Client(self.app)
        self.assertEqual(other.login()[0], 200)
        with self.app.connect() as connection:
            connection.execute("INSERT INTO product_activity (actor_id,actor_name,action,product_id,product_name,created_at) VALUES (?,?,?,?,?,?)",
                               (user["id"], user["name"], "update", "sample", "Sample suit", server.now_iso()))
            self.app.security_event("legacy", email=user["email"], ip="192.0.2.1", connection=connection)
        status, result, headers = self.delete()
        self.assertEqual(status, 200)
        self.assertEqual(result, {"ok": True, "deleted": True, "user": None})
        self.assertIn("Max-Age=0", headers["Set-Cookie"])
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIsNone(other.request("GET", "/api/auth/me")[1]["user"])
        self.assertEqual(Client(self.app).login()[0], 401)
        with self.app.connect() as connection:
            for table in ("users", "sessions", "mfa_challenges", "mfa_recovery_codes", "user_consents"):
                field = "id" if table == "users" else "user_id"
                self.assertEqual(connection.execute(f"SELECT COUNT(*) FROM {table} WHERE {field}=?", (user["id"],)).fetchone()[0], 0)
            activity = connection.execute("SELECT actor_id,actor_name FROM product_activity").fetchone()
            self.assertIsNone(activity["actor_id"])
            self.assertEqual(activity["actor_name"], "Deleted account")
            history = connection.execute("SELECT actor_name,email_hint,ip,actor_id FROM security_events WHERE event_type NOT IN ('login_failed')").fetchall()
            self.assertTrue(history)
            self.assertTrue(all(not row["actor_name"] and not row["email_hint"] and not row["ip"] and row["actor_id"] is None for row in history))
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM products").fetchone()[0], 1)

    def test_mfa_requires_unused_factor_and_cascades_pending_credentials(self):
        self.register()
        secret, codes = self.enable_mfa()
        pending = Client(self.app)
        challenge = pending.login()[1]
        self.assertTrue(challenge["requiresTwoFactor"])
        self.assertEqual(self.delete()[0], 400)
        self.assertEqual(self.delete(code=security_core.totp(secret))[0], 400, "Enrollment code is already spent")
        self.assertEqual(self.delete(code=codes[0])[0], 200)
        self.assertEqual(pending.request("POST", "/api/auth/verify", {"challenge": challenge["challenge"], "code": codes[1]})[0], 401)
        with self.app.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mfa_challenges").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM mfa_recovery_codes").fetchone()[0], 0)

    def test_deletion_wrong_password_uses_persistent_failure_budget(self):
        self.register()
        for _ in range(5):
            self.assertEqual(self.delete(password="incorrect password")[0], 400)
        self.assertEqual(self.delete()[0], 429)
        self.assertIsNotNone(self.client.request("GET", "/api/auth/me")[1]["user"])

    def test_deletion_mfa_failure_budget_is_persistent(self):
        self.register()
        self.enable_mfa()
        for _ in range(5):
            self.assertEqual(self.delete(code="invalid")[0], 400)
        self.assertEqual(self.delete(code="invalid")[0], 429)
        with self.app.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM users WHERE role='customer'").fetchone()[0], 1)

    def test_last_administrator_cannot_delete_and_parallel_deletions_preserve_one(self):
        first = Client(self.app)
        self.assertEqual(first.login(email="owner@example.com")[0], 200)
        self.assertEqual(self.delete(first)[0], 409)
        with self.app.connect() as connection:
            connection.execute("INSERT INTO users (name,email,password_hash,role,created_at) VALUES (?,?,?,'admin',?)",
                               ("Second owner", "second@example.com", self.password_hash, server.now_iso()))
        second = Client(self.app)
        self.assertEqual(second.login(email="second@example.com")[0], 200)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(self.delete, (first, second)))
        self.assertEqual(sorted(result[0] for result in results), [200, 409])
        with self.app.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0], 1)

    def test_deletion_rechecks_credentials_after_password_verification(self):
        self.register()
        original = server.verify_password
        def changed_password(password, encoded):
            accepted = original(password, encoded)
            with self.app.connect() as connection:
                connection.execute("UPDATE users SET auth_version=auth_version+1 WHERE email='maya@example.com'")
            return accepted
        with mock.patch.object(server, "verify_password", side_effect=changed_password):
            self.assertEqual(self.delete()[0], 401)
        with self.app.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM users WHERE role='customer'").fetchone()[0], 1)

    def test_business_details_start_empty_and_only_admin_can_edit(self):
        public = self.client.request("GET", "/api/business-details")
        self.assertEqual(public[0], 200)
        self.assertEqual(public[1], {"businessDetails": dict.fromkeys(server.BUSINESS_FIELDS, "")})
        self.assertEqual(self.client.request("GET", "/api/admin/business-details")[0], 401)
        self.assertEqual(self.client.request("PATCH", "/api/admin/business-details", {"legalName": "Example"})[0], 401)
        self.register()
        self.assertEqual(self.client.request("GET", "/api/admin/business-details")[0], 403)
        self.assertEqual(self.client.request("PATCH", "/api/admin/business-details", {"legalName": "Example"})[0], 403)

    def test_business_details_require_csrf_and_validate_fields(self):
        admin = Client(self.app)
        self.assertEqual(admin.login(email="owner@example.com")[0], 200)
        self.assertEqual(admin.request("PATCH", "/api/admin/business-details", {"legalName": "Example"}, token=False)[0], 403)
        self.assertEqual(admin.request("PATCH", "/api/admin/business-details", {"legalName": "Example"}, origin=False)[0], 403)
        for changes in ({}, {"privateEmail": "private@example.com"}, {"legalName": 15}, {"country": "a" * 101},
                        {"businessAddress": "a" * 1001}, {"customerServiceEmail": "invalid"}, {"legalName": "invalid\nname"}):
            with self.subTest(changes=changes):
                self.assertEqual(admin.request("PATCH", "/api/admin/business-details", changes)[0], 400)

    def test_business_details_public_changes_persist_and_audit_omits_field_values(self):
        admin = Client(self.app)
        self.assertEqual(admin.login(email="owner@example.com")[0], 200)
        values = {"legalName": " Example Studio BV ", "country": "Netherlands", "registrationNumber": "12345678",
                  "vatNumber": "EXAMPLE-VAT", "businessAddress": "Example Street 1\nExample City",
                  "customerServiceEmail": " Support@Example.COM ", "returnAddress": "Example Return Street 2"}
        expected = {**values, "legalName": "Example Studio BV", "customerServiceEmail": "support@example.com"}
        status, result, _ = admin.request("PATCH", "/api/admin/business-details", values)
        self.assertEqual(status, 200)
        self.assertEqual(result["businessDetails"], expected)
        self.assertEqual(Client(self.app).request("GET", "/api/business-details")[1]["businessDetails"], expected)
        self.assertEqual(admin.request("GET", "/api/admin/business-details")[1]["businessDetails"], expected)
        with self.app.connect() as connection:
            self.assertEqual(json.loads(connection.execute("SELECT details FROM business_settings WHERE id=1").fetchone()[0]), expected)
            event = connection.execute("SELECT * FROM security_events WHERE event_type='business_details_updated'").fetchone()
            self.assertEqual(event["detail"], "Public business details were updated.")
            self.assertNotIn("support@example.com", event["detail"])
        self.assertEqual(admin.request("PATCH", "/api/admin/business-details", {"vatNumber": ""})[1]["businessDetails"], {**expected, "vatNumber": ""})
        self.assertEqual(self.client.request("POST", "/api/business-details", {})[0], 405)

    def test_seed_copy_migration_updates_only_matching_untouched_descriptions(self):
        update_file = self.root / "catalog-copy-updates.json"
        update_file.write_text(json.dumps([
            {"id": "sample", "previous": "An illustrative suit.", "replacement": "An illustrative outfit concept."},
            {"id": "unrelated", "previous": "An illustrative suit.", "replacement": "Must not be added."},
        ]), encoding="utf-8")
        self.app.initialize_database(self.root / "catalog.json")
        with self.app.connect() as connection:
            self.assertEqual(connection.execute("SELECT description FROM products WHERE id='sample'").fetchone()[0], "An illustrative outfit concept.")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM products").fetchone()[0], 1)
            connection.execute("UPDATE products SET description='A description edited by the owner.' WHERE id='sample'")
        self.app.initialize_database(self.root / "catalog.json")
        with self.app.connect() as connection:
            self.assertEqual(connection.execute("SELECT description FROM products WHERE id='sample'").fetchone()[0], "A description edited by the owner.")

    def test_late_security_event_after_deletion_does_not_restore_identifiers(self):
        self.register()
        with self.app.connect() as connection:
            snapshot = connection.execute("SELECT * FROM users WHERE email='maya@example.com'").fetchone()
        self.assertEqual(self.delete()[0], 200)
        self.app.security_event("late_logout", user=snapshot, email=snapshot["email"], ip="192.0.2.50", detail="A request finished after erasure.")
        with self.app.connect() as connection:
            event = connection.execute("SELECT * FROM security_events WHERE event_type='late_logout'").fetchone()
        self.assertIsNotNone(event)
        self.assertIsNone(event["actor_id"])
        self.assertEqual(event["actor_name"], "")
        self.assertEqual(event["email_hint"], "")
        self.assertEqual(event["ip"], "")

    def test_local_truetype_fonts_are_served_without_opening_other_assets(self):
        fonts = self.root / "assets/fonts"
        fonts.mkdir()
        (fonts / "example.ttf").write_bytes(b"local font fixture")
        (fonts / "private.json").write_text('{"private":true}', encoding="utf-8")
        status, content, headers = self.client.request("GET", "/assets/fonts/example.ttf")
        self.assertEqual(status, 200)
        self.assertEqual(content, b"local font fixture")
        self.assertEqual(headers["Content-Type"], "font/ttf")
        self.assertNotIn("googleapis.com", headers["Content-Security-Policy"])
        self.assertNotIn("gstatic.com", headers["Content-Security-Policy"])
        self.assertEqual(self.client.request("GET", "/assets/fonts/private.json")[0], 404)


if __name__ == "__main__":
    unittest.main()
