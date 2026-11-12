"""Owner-provisioned colleagues stay separate from public customer accounts."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

import json
import unittest

import test_catalog_server as catalog_tests
from test_auth_server import Client, PASSWORD
import colleagues
import server


class ColleagueServerTests(unittest.TestCase):
    setUpClass = catalog_tests.CatalogServerTests.__dict__["setUpClass"]
    setUp = catalog_tests.CatalogServerTests.setUp
    tearDown = catalog_tests.CatalogServerTests.tearDown

    def payload(self, **changes):
        return {"firstName": "Colleague", "lastName": "Example", "email": "colleague@velora.com", "password": PASSWORD,
                "active": True, "department": "creative", "role": "colleague", "fullControl": False,
                "grants": [{"folder": "creative", "access": "write"}], **changes}

    def create(self, **changes):
        status, result, _ = self.admin.request("POST", "/api/admin/colleagues", self.payload(**changes))
        self.assertEqual(status, 201, result)
        return result["colleague"]

    def access(self, **changes):
        return {"active": True, "department": "creative", "role": "colleague", "fullControl": False,
                "grants": [{"folder": "creative", "access": "write"}], **changes}

    def colleague_client(self, email="colleague@velora.com"):
        client = Client(self.app)
        self.assertEqual(client.login(email=email)[0], 200)
        return client

    def note(self, client, folder, text="Private sample note"):
        status, result, _ = client.request("POST", f"/api/intranet/folders/{folder}/files", {"name": "Colleague access test", "kind": "note", "text": text})
        self.assertEqual(status, 201, result)
        return result["file"]

    def test_public_email_providers_and_company_looking_signup_remain_customers(self):
        gmail = Client(self.app)
        company = Client(self.app)
        self.assertEqual(gmail.register(email="customer@gmail.com")[0], 201)
        self.assertEqual(company.register(email="public@velora.com")[0], 201)
        with self.app.connect() as connection:
            rows = connection.execute("SELECT account_type FROM users WHERE role='customer'").fetchall()
        self.assertEqual([row[0] for row in rows], ["customer", "customer"])
        for customer in (gmail, company):
            self.assertFalse(customer.request("GET", "/api/intranet/access")[1]["allowed"])
            self.assertEqual(customer.request("GET", "/api/intranet/folders")[0], 403)
            self.assertEqual(customer.request("GET", "/api/admin/colleagues")[0], 403)
        for path in ("/api/admin/colleagues", "/api/admin/folder-access"):
            self.assertEqual(self.admin.request("GET", path)[1]["colleagues"], [])
        customer_id = company.request("GET", "/api/auth/me")[1]["user"]["id"]
        self.assertEqual(self.admin.request("PATCH", f"/api/admin/folder-access/{customer_id}", {"active": True, "department": "creative", "grants": [{"folder": "creative", "access": "write"}]})[0], 404)
        self.assertEqual(company.request("PATCH", "/api/account", {"account_type": "velora"})[0], 400)
        for extra in ({"account_type": "velora"}, {"role": "admin"}, {"fullControl": True}):
            self.assertEqual(Client(self.app).register(email="fake@velora.com", **extra)[0], 400)

    def test_owner_creates_work_account_without_exposing_password_or_promoting_customer_lists(self):
        public = Client(self.app)
        self.assertEqual(public.register(email="customer@hotmail.com")[0], 201)
        colleague = self.create(email="Studio.Person@VELORA.COM")
        self.assertEqual((colleague["email"], colleague["accountType"], colleague["role"]), ("studio.person@velora.com", "velora", "colleague"))
        self.assertTrue(colleague["active"])
        self.assertFalse(colleague["fullControl"])
        self.assertNotIn(PASSWORD, json.dumps(colleague))
        self.assertNotIn("password_hash", colleague)
        with self.app.connect() as connection:
            stored = connection.execute("SELECT * FROM users WHERE id=?", (colleague["id"],)).fetchone()
            self.assertEqual((stored["role"], stored["account_type"]), ("customer", "velora"))
            self.assertNotEqual(stored["password_hash"], PASSWORD)
            self.assertTrue(server.verify_password(PASSWORD, stored["password_hash"]))
            audit = [dict(row) for row in connection.execute("SELECT * FROM security_events WHERE event_type='colleague_created'")]
            self.assertEqual(len(audit), 1)
            self.assertNotIn(PASSWORD, json.dumps(audit))
        worker = self.colleague_client("studio.person@velora.com")
        me = worker.request("GET", "/api/auth/me")[1]["user"]
        self.assertEqual(set(me), set(server.USER_FIELDS))
        self.assertEqual(worker.request("GET", "/api/admin/products")[0], 403)
        self.assertTrue(worker.request("GET", "/api/intranet/access")[1]["allowed"])
        self.assertEqual(len(self.admin.request("GET", "/api/admin/folder-access")[1]["colleagues"]), 1)
        customers = self.admin.request("GET", "/api/admin/customers")[1]["customers"]
        self.assertEqual([person["email"] for person in customers], ["customer@hotmail.com"])
        overview = self.admin.request("GET", "/api/admin/overview")[1]
        self.assertEqual(overview["totalCustomers"], 1)
        directory = self.admin.request("GET", "/api/admin/commerce")[1]["customers"]
        self.assertEqual([person["email"] for person in directory], ["customer@hotmail.com"])

    def test_work_domain_and_creation_fields_are_checked_before_any_account_is_added(self):
        invalid = ({"email": "person@gmail.com"}, {"email": "person@hotmail.com"}, {"email": "person@otherbrand.com"},
                   {"email": "person@velora.com.evil"}, {"email": "person@sub.velora.com"}, {"email": "@velora.com"},
                   {"password": "short"}, {"firstName": ""}, {"role": True}, {"fullControl": 1},
                   {"role": "owner", "fullControl": False}, {"fullControl": True}, {"department": "company"},
                   {"department": None}, {"grants": [{"folder": "made-up", "access": "write"}]},
                   {"grants": [{"folder": "creative", "access": "admin"}]}, {"grants": [{"folder": "finance", "access": "read"}]})
        for change in invalid:
            with self.subTest(change=change):
                self.assertEqual(self.admin.request("POST", "/api/admin/colleagues", self.payload(**change))[0], 400)
        self.assertEqual(self.admin.request("POST", "/api/admin/colleagues", self.payload(extra=True))[0], 400)
        self.assertEqual(self.admin.request("GET", "/api/admin/colleagues")[1]["colleagues"], [])
        with self.app.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)

    def test_existing_customer_work_address_is_not_overwritten_or_silently_converted(self):
        customer = Client(self.app)
        self.assertEqual(customer.register(email="colleague@velora.com")[0], 201)
        with self.app.connect() as connection:
            before = dict(connection.execute("SELECT * FROM users WHERE email='colleague@velora.com'").fetchone())
        self.assertEqual(self.admin.request("POST", "/api/admin/colleagues", self.payload(password="a different colleague password"))[0], 409)
        with self.app.connect() as connection:
            after = dict(connection.execute("SELECT * FROM users WHERE email='colleague@velora.com'").fetchone())
            self.assertEqual(before, after)
            self.assertIsNone(connection.execute("SELECT * FROM staff_profiles WHERE user_id=?", (before["id"],)).fetchone())
        self.assertEqual(customer.login(email="colleague@velora.com")[0], 200)
        self.assertEqual(self.admin.request("GET", "/api/admin/colleagues")[1]["colleagues"], [])

    def test_full_control_explicitly_allows_finance_hr_upload_read_and_delete(self):
        owner = self.create(email="full.owner@velora.com", department="leadership", role="owner", fullControl=True, grants=[])
        self.assertTrue(owner["fullControl"])
        client = self.colleague_client("full.owner@velora.com")
        folders = client.request("GET", "/api/intranet/folders")[1]["folders"]
        self.assertTrue(all(folder["canRead"] and folder["canWrite"] for folder in folders))
        for folder in ("finance", "people"):
            file = self.note(client, folder)
            self.assertEqual(client.request("GET", file["downloadUrl"])[0], 200)
            self.assertEqual(self.admin.request("GET", file["downloadUrl"])[0], 403)
            self.assertEqual(client.request("DELETE", f"/api/intranet/files/{file['id']}")[0], 200)
        self.assertEqual(client.request("GET", "/api/admin/colleagues")[0], 200)

    def test_ordinary_finance_colleague_requires_grant_and_cannot_open_hr(self):
        self.create(department="finance", grants=[])
        client = self.colleague_client()
        self.assertEqual(client.request("GET", "/api/intranet/folders/finance/files")[0], 403)
        result = self.admin.request("PATCH", "/api/admin/colleagues/" + str(client.request("GET", "/api/auth/me")[1]["user"]["id"]),
                                    self.access(department="finance", grants=[{"folder": "finance", "access": "write"}]))
        self.assertEqual(result[0], 200, result[1])
        self.assertEqual(client.request("GET", "/api/intranet/folders/finance/files")[0], 200)
        self.assertEqual(client.request("GET", "/api/intranet/folders/people/files")[0], 403)
        self.note(client, "finance")

    def test_managers_warehouse_customers_and_unsigned_users_cannot_manage_colleagues(self):
        manager = self.create(email="manager@velora.com", role="manager", grants=[])
        self.create(email="warehouse@velora.com", role="warehouse", grants=[])
        manager_client, warehouse = self.colleague_client("manager@velora.com"), self.colleague_client("warehouse@velora.com")
        customer = Client(self.app)
        self.assertEqual(customer.register()[0], 201)
        for client, expected in ((self.public, 401), (customer, 403), (manager_client, 403), (warehouse, 403)):
            with self.subTest(expected=expected):
                self.assertEqual(client.request("GET", "/api/admin/colleagues")[0], expected)
                self.assertEqual(client.request("POST", "/api/admin/colleagues", self.payload())[0], expected)
                self.assertEqual(client.request("PATCH", f"/api/admin/colleagues/{manager['id']}", self.access())[0], expected)
                self.assertEqual(client.request("GET", "/api/admin/folder-access")[0], expected)

    def test_role_downgrade_and_disable_revoke_sessions_and_full_folder_access(self):
        worker = self.create(role="owner", fullControl=True, department="leadership", grants=[])
        client = self.colleague_client()
        file = self.note(client, "finance", text="A restricted department record")
        self.assertEqual(self.admin.request("PATCH", f"/api/admin/colleagues/{worker['id']}", self.access(role="manager", department="leadership", grants=[]))[0], 200)
        self.assertEqual(client.request("GET", file["downloadUrl"])[0], 401)
        self.assertEqual(client.request("GET", "/api/admin/colleagues")[0], 401)
        self.assertEqual(client.login(email="colleague@velora.com")[0], 200)
        self.assertEqual(client.request("GET", file["downloadUrl"])[0], 403)
        self.assertEqual(client.request("GET", "/api/admin/colleagues")[0], 403)
        self.assertEqual(client.request("GET", "/api/admin/products")[0], 200)
        disabled = self.access(active=False, role="manager", department="leadership", grants=[])
        self.assertEqual(self.admin.request("PATCH", f"/api/admin/colleagues/{worker['id']}", disabled)[0], 200)
        self.assertEqual(client.request("GET", "/api/admin/products")[0], 401)
        self.assertEqual(client.login(email="colleague@velora.com")[0], 401)
        self.assertEqual(self.admin.request("PATCH", f"/api/admin/colleagues/{worker['id']}", self.access(role="manager", department="leadership", grants=[]))[0], 200)
        self.assertEqual(client.login(email="colleague@velora.com")[0], 200)

    def test_self_lockout_and_last_enabled_owner_deletion_are_blocked(self):
        owner = self.create(role="owner", fullControl=True, department="leadership", grants=[])
        client = self.colleague_client()
        self.assertEqual(client.request("PATCH", f"/api/admin/colleagues/{owner['id']}", self.access(active=False, role="owner", fullControl=True, department="leadership", grants=[]))[0], 409)
        self.assertEqual(client.request("PATCH", f"/api/admin/colleagues/{owner['id']}", self.access(role="manager", grants=[]))[0], 409)
        with self.app.connect() as connection:
            original = connection.execute("SELECT id FROM users WHERE email='admin@example.test'").fetchone()[0]
            state = json.loads(connection.execute("SELECT data FROM commerce_state").fetchone()[0])
            state["staff"][str(original)] = "manager"
            connection.execute("UPDATE commerce_state SET data=?", (json.dumps(state),))
        self.assertEqual(client.request("DELETE", "/api/account", {"password": PASSWORD})[0], 409)
        self.assertEqual(client.request("GET", "/api/admin/colleagues")[0], 200)

    def test_mutations_require_origin_and_csrf_and_invalid_patch_is_atomic(self):
        self.assertEqual(self.admin.request("POST", "/api/admin/colleagues", self.payload(), token=False)[0], 403)
        self.assertEqual(self.admin.request("POST", "/api/admin/colleagues", self.payload(), origin=False)[0], 403)
        worker = self.create()
        path = f"/api/admin/colleagues/{worker['id']}"
        self.assertEqual(self.admin.request("PATCH", path, self.access(active=False), token=False)[0], 403)
        self.assertEqual(self.admin.request("PATCH", path, self.access(active=False), origin=False)[0], 403)
        with self.app.connect() as connection:
            before = dict(connection.execute("SELECT * FROM users WHERE id=?", (worker["id"],)).fetchone())
            profile = dict(connection.execute("SELECT * FROM staff_profiles WHERE user_id=?", (worker["id"],)).fetchone())
            grants = [tuple(row) for row in connection.execute("SELECT * FROM folder_grants WHERE user_id=?", (worker["id"],))]
        self.assertEqual(self.admin.request("PATCH", path, self.access(department="people", grants=[{"folder": "finance", "access": "write"}]))[0], 400)
        self.assertEqual(self.admin.request("PATCH", path, self.access(role="manager", fullControl=True))[0], 400)
        with self.app.connect() as connection:
            self.assertEqual(dict(connection.execute("SELECT * FROM users WHERE id=?", (worker["id"],)).fetchone()), before)
            self.assertEqual(dict(connection.execute("SELECT * FROM staff_profiles WHERE user_id=?", (worker["id"],)).fetchone()), profile)
            self.assertEqual([tuple(row) for row in connection.execute("SELECT * FROM folder_grants WHERE user_id=?", (worker["id"],))], grants)

    def test_migration_requires_existing_owner_assigned_profile_not_just_a_work_email(self):
        for email in ("assigned@velora.com", "unassigned@velora.com", "assigned@gmail.com"):
            self.assertEqual(Client(self.app).register(email=email)[0], 201)
        with self.app.connect() as connection:
            for email in ("assigned@velora.com", "assigned@gmail.com"):
                key = connection.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()[0]
                connection.execute("INSERT INTO staff_profiles(user_id,active,department,updated_at) VALUES(?,1,'creative',?)", (key, server.now_iso()))
            connection.execute("DELETE FROM security_config WHERE name='velora_colleagues_v1'")
        colleagues.initialize(self.app)
        colleagues.initialize(self.app)
        result = self.admin.request("GET", "/api/admin/colleagues")[1]["colleagues"]
        self.assertEqual([row["email"] for row in result], ["assigned@velora.com"])
        with self.app.connect() as connection:
            types = {row["email"]: row["account_type"] for row in connection.execute("SELECT email,account_type FROM users WHERE role='customer'")}
        self.assertEqual(types, {"assigned@velora.com": "velora", "unassigned@velora.com": "customer", "assigned@gmail.com": "customer"})


if __name__ == "__main__":
    unittest.main()
