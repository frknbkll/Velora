"""Department access and private-file boundaries against disposable HTTP servers."""

import base64
import json
import sqlite3
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import server
from test_auth_server import Client, PASSWORD
from test_catalog_server import png


class SharedFoldersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = server.hash_password(PASSWORD)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.database = self.root / ".velora" / "accounts.sqlite3"
        (self.root / "assets" / "responsive").mkdir(parents=True)
        (self.root / "assets" / "outfit.png").write_bytes(png())
        (self.root / "assets" / "responsive" / "outfit-480.webp").write_bytes(b"duplicate fixture")
        for name in ("index.html", "login.html", "account.html", "admin.html", "intranet.html"):
            (self.root / name).write_text("<!doctype html><title>Page fixture</title>", encoding="utf-8")
        self.catalog = self.root / "product-catalog.json"
        self.catalog.write_text(json.dumps({"products": [{
            "id": "example", "name": "An outfit", "image": "assets/outfit.png",
            "founder": "A designer", "collection": "THE TAILORED EDIT", "price": 100,
            "description": "An illustrative outfit.", "published": True,
        }]}), encoding="utf-8")
        self.app = server.make_server(port=0, database=self.database, catalog=self.catalog, root=self.root)
        self.app.RequestHandlerClass.log_message = lambda *args: None
        self.owner_id = self.add_account("owner@example.test", "admin")
        self.staff_id = self.add_account("staff@velora.com")
        self.other_id = self.add_account("other@velora.com")
        self.thread = threading.Thread(target=self.app.serve_forever, daemon=True)
        self.thread.start()
        self.owner = self.sign_in("owner@example.test")
        self.staff = self.sign_in("staff@velora.com")
        self.other = self.sign_in("other@velora.com")
        self.anonymous = Client(self.app)

    def tearDown(self):
        self.app.shutdown()
        self.app.server_close()
        self.thread.join(timeout=5)
        self.directory.cleanup()

    def add_account(self, email, role="customer"):
        with self.app.connect() as db:
            result = db.execute("INSERT INTO users(name,email,password_hash,role,created_at,account_type) VALUES(?,?,?,?,?,?)",
                                (email.split("@")[0].title(), email, self.password_hash, role, server.now_iso(), "velora" if email.endswith("@velora.com") else "customer"))
            return result.lastrowid

    def sign_in(self, email):
        client = Client(self.app)
        self.assertEqual(client.login(email=email)[0], 200)
        return client

    def configure(self, user_id, department="creative", grants=(), active=True):
        payload = {"active": active, "department": department,
                   "grants": [{"folder": folder, "access": access} for folder, access in grants]}
        result = self.owner.request("PATCH", f"/api/admin/folder-access/{user_id}", payload)
        self.assertEqual(result[0], 200, result[1])
        return result[1]["colleague"]

    def list_files(self, client, folder="creative"):
        status, payload, _ = client.request("GET", f"/api/intranet/folders/{folder}/files")
        self.assertEqual(status, 200, payload)
        return payload["files"]

    def note(self, client, folder="creative", name="Planning notes", text="Department-only planning information"):
        status, payload, _ = client.request("POST", f"/api/intranet/folders/{folder}/files",
                                            {"name": name, "kind": "note", "text": text})
        self.assertIn(status, (200, 201), payload)
        return payload["file"]

    def upload(self, client, name="Campaign.png", content=None, mime="image/png", folder="creative"):
        data = base64.b64encode(content if content is not None else png()).decode()
        return client.request("POST", f"/api/intranet/folders/{folder}/files",
                              {"name": name, "data": f"data:{mime};base64,{data}"})

    def test_staff_enablement_does_not_promote_customer_or_open_admin(self):
        self.assertEqual(self.anonymous.request("GET", "/api/intranet/access")[0], 401)
        for path in ("/api/intranet/folders", "/api/admin/folder-access"):
            self.assertEqual(self.anonymous.request("GET", path)[0], 401)
            self.assertEqual(self.staff.request("GET", path)[0], 403)
        self.assertFalse(self.staff.request("GET", "/api/intranet/access")[1]["allowed"])
        self.assertEqual(self.staff.request("GET", "/intranet.html")[0], 403)
        colleague = self.configure(self.staff_id, grants=(("creative", "read"),))
        self.assertTrue(colleague["active"])
        self.assertTrue(self.staff.request("GET", "/api/intranet/access")[1]["allowed"])
        self.assertEqual(self.staff.request("GET", "/intranet.html")[0], 200)
        self.assertEqual(self.staff.request("GET", "/admin.html")[0], 403)
        self.assertEqual(self.staff.request("GET", "/api/admin/folder-access")[0], 403)
        self.assertEqual(self.staff.request("GET", "/api/auth/me")[1]["user"]["role"], "customer")

    def test_sensitive_folders_need_matching_department_and_explicit_grant_even_for_admin(self):
        self.configure(self.staff_id, department="finance")
        self.configure(self.other_id, department="people", grants=(("people", "write"),))
        self.assertEqual(self.staff.request("GET", "/api/intranet/folders/finance/files")[0], 403)
        self.assertEqual(self.owner.request("GET", "/api/intranet/folders/finance/files")[0], 403)
        self.assertEqual(self.owner.request("GET", "/api/intranet/folders/people/files")[0], 403)
        self.configure(self.staff_id, department="finance", grants=(("finance", "write"),))
        finance_note = self.note(self.staff, "finance", "Forecast", "Confidential forecast")
        self.assertEqual(self.other.request("GET", finance_note["downloadUrl"])[0], 403)
        self.assertEqual(self.owner.request("GET", finance_note["downloadUrl"])[0], 403)
        hr_note = self.note(self.other, "people", "HR policy", "Confidential personnel policy")
        self.assertEqual(self.staff.request("GET", hr_note["downloadUrl"])[0], 403)
        status, payload, _ = self.staff.request("GET", "/api/intranet/folders")
        self.assertEqual(status, 200)
        folders = {folder["id"]: folder for folder in payload["folders"]}
        self.assertTrue(folders["finance"]["canRead"])
        self.assertFalse(folders["people"]["canRead"])
        self.assertIn(folders["people"].get("fileCount"), (0, None))
        self.assertNotIn("Confidential personnel policy", json.dumps(payload))

    def test_read_and_write_grants_control_each_operation_and_private_urls(self):
        self.configure(self.staff_id, grants=(("creative", "write"),))
        self.configure(self.other_id, department="design", grants=(("creative", "read"),))
        status, payload, _ = self.upload(self.staff)
        self.assertIn(status, (200, 201), payload)
        file = payload["file"]
        self.assertEqual(file["source"], "private")
        self.assertEqual(self.list_files(self.other)[0]["id"], file["id"])
        self.assertFalse(self.list_files(self.other)[0]["canDelete"])
        for action in ("downloadUrl", "previewUrl"):
            status, content, headers = self.other.request("GET", file[action])
            self.assertEqual(status, 200)
            self.assertEqual(content, png())
            self.assertIn("no-store", headers["Cache-Control"].split(", "))
            self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
            self.assertEqual(self.anonymous.request("GET", file[action])[0], 401)
            self.assertEqual(self.owner.request("GET", file[action])[0], 403)
        download_headers = self.other.request("GET", file["downloadUrl"])[2]
        self.assertIn("attachment", download_headers["Content-Disposition"])
        self.assertEqual(self.upload(self.other)[0], 403)
        self.assertEqual(self.other.request("POST", "/api/intranet/folders/creative/files", {
            "name": "Forbidden note", "kind": "note", "text": "Should not be saved"})[0], 403)
        self.assertEqual(self.other.request("DELETE", f"/api/intranet/files/{file['id']}")[0], 403)
        self.assertEqual(self.staff.request("DELETE", f"/api/intranet/files/{file['id']}")[0], 200)
        self.assertEqual(self.list_files(self.other), [])
        self.assertEqual(self.staff.request("GET", file["downloadUrl"])[0], 404)

    def test_revocation_affects_existing_sessions_and_direct_file_requests_immediately(self):
        self.configure(self.staff_id, department="finance", grants=(("finance", "write"),))
        file = self.note(self.staff, "finance")
        self.assertEqual(self.staff.request("GET", file["downloadUrl"])[0], 200)
        self.configure(self.staff_id, department="finance")
        self.assertEqual(self.staff.request("GET", "/api/intranet/folders/finance/files")[0], 403)
        self.assertEqual(self.staff.request("GET", file["downloadUrl"])[0], 403)
        self.assertEqual(self.staff.request("DELETE", f"/api/intranet/files/{file['id']}")[0], 403)
        self.configure(self.staff_id, department="finance", grants=(("finance", "read"),))
        self.assertEqual(self.staff.request("GET", file["downloadUrl"])[0], 200)
        self.configure(self.staff_id, department="finance", active=False)
        self.assertFalse(self.staff.request("GET", "/api/intranet/access")[1]["allowed"])
        self.assertEqual(self.staff.request("GET", "/intranet.html")[0], 403)
        self.assertEqual(self.staff.request("GET", "/api/intranet/folders")[0], 403)
        self.assertEqual(self.staff.request("GET", file["downloadUrl"])[0], 403)

    def test_permission_validation_is_atomic_and_rejects_sensitive_cross_department_grants(self):
        self.configure(self.staff_id, grants=(("creative", "read"),))
        original = self.owner.request("GET", "/api/admin/folder-access")[1]
        original_staff = next(item for item in original["colleagues"] if item["id"] == self.staff_id)
        base = {"active": True, "department": "creative", "grants": [{"folder": "creative", "access": "read"}]}
        invalid = [
            {**base, "active": "true"}, {**base, "active": 1}, {**base, "department": None},
            {**base, "department": "company"}, {**base, "department": "unknown"},
            {**base, "role": "admin"}, {**base, "grants": [{"folder": "finance", "access": "read"}]},
            {**base, "grants": [{"folder": "people", "access": "write"}]},
            {**base, "grants": [{"folder": "unknown", "access": "read"}]},
            {**base, "grants": [{"folder": "creative", "access": "owner"}]},
            {**base, "grants": base["grants"] * 2}, {**base, "grants": [{"folder": "creative", "access": "read", "user": self.owner_id}]},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                self.assertEqual(self.owner.request("PATCH", f"/api/admin/folder-access/{self.staff_id}", payload)[0], 400)
        current = self.owner.request("GET", "/api/admin/folder-access")[1]
        self.assertEqual(next(item for item in current["colleagues"] if item["id"] == self.staff_id), original_staff)
        self.assertEqual(self.owner.request("PATCH", "/api/admin/folder-access/999999", base)[0], 404)

    def test_only_owner_can_change_or_enumerate_colleague_permissions_and_csrf_is_required(self):
        payload = {"active": True, "department": "finance", "grants": [{"folder": "finance", "access": "read"}]}
        route = f"/api/admin/folder-access/{self.staff_id}"
        self.assertEqual(self.owner.request("PATCH", route, payload, token=False)[0], 403)
        self.assertEqual(self.owner.request("PATCH", route, payload, origin=False)[0], 403)
        self.assertEqual(self.staff.request("PATCH", route, payload)[0], 403)
        for role in ("manager", "warehouse"):
            email = role + "@example.test"
            identity = self.add_account(email, "admin")
            with self.app.connect() as db:
                state = json.loads(db.execute("SELECT data FROM commerce_state WHERE id=1").fetchone()[0])
                state["staff"][str(identity)] = role
                db.execute("UPDATE commerce_state SET data=? WHERE id=1", (json.dumps(state),))
            limited = self.sign_in(email)
            self.assertEqual(limited.request("GET", "/api/admin/folder-access")[0], 403)
            self.assertEqual(limited.request("PATCH", route, payload)[0], 403)
        self.assertFalse(self.staff.request("GET", "/api/intranet/access")[1]["allowed"])

    def test_public_company_library_is_read_only_and_private_company_files_still_require_staff(self):
        self.configure(self.staff_id)
        self.assertEqual(self.owner.request("GET", "/intranet.html")[0], 200)
        files = self.list_files(self.staff, "company")
        website_files = [file for file in files if file["source"] == "website"]
        self.assertTrue(any(file["kind"] == "image" for file in website_files))
        self.assertTrue(any(file["mime"].startswith("application/json") for file in website_files))
        self.assertFalse(any("responsive" in file["name"] for file in website_files))
        self.assertTrue(all(file["canDelete"] is False for file in website_files))
        public_image = next(file for file in website_files if file["kind"] == "image")
        self.assertEqual(self.staff.request("GET", public_image["downloadUrl"])[0], 200)
        self.assertEqual(self.staff.request("DELETE", f"/api/intranet/files/{public_image['id']}")[0], 403)
        self.assertEqual(self.upload(self.staff, folder="company")[0], 403)
        self.configure(self.staff_id, grants=(("company", "write"),))
        file = self.note(self.staff, "company", "Company handbook")
        self.assertEqual(file["source"], "private")
        self.assertEqual(self.other.request("GET", file["downloadUrl"])[0], 403)
        self.configure(self.other_id, department="design")
        self.assertEqual(self.other.request("GET", file["downloadUrl"])[0], 200)
        self.assertEqual(self.anonymous.request("GET", "/assets/outfit.png")[0], 200)

    def test_upload_rejects_active_content_malformed_data_and_unsafe_names(self):
        self.configure(self.staff_id, grants=(("creative", "write"),))
        invalid = [
            ("payload.html", b"<html><script>alert(1)</script></html>", "text/html"),
            ("payload.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', "image/svg+xml"),
            ("fake.png", b"<script>alert(1)</script>", "image/png"),
            ("truncated.png", png()[:-12], "image/png"),
            ("oversized.png", png(16001, 1), "image/png"),
            ("../secret.png", png(), "image/png"), ("..\\secret.png", png(), "image/png"),
            ("hidden\r\nheader.png", png(), "image/png"), ("program.exe", b"MZ executable", "application/octet-stream"),
        ]
        for name, content, mime in invalid:
            with self.subTest(name=name):
                self.assertIn(self.upload(self.staff, name, content, mime)[0], (400, 415))
        malformed = self.staff.request("POST", "/api/intranet/folders/creative/files", {
            "name": "bad.png", "data": "data:image/png;base64,not-valid-base64!"})
        self.assertEqual(malformed[0], 400)
        self.assertEqual(self.staff.request("POST", "/api/intranet/folders/creative/files", {
            "name": "Long note", "kind": "note", "text": "a" * 20_001})[0], 400)
        self.assertEqual(self.staff.request("POST", "/api/intranet/folders/creative/files", {
            "name": "Padded note", "kind": "note", "text": " " * 20_000 + "a"})[0], 400)
        self.assertEqual(self.list_files(self.staff), [])

    def test_failed_deletion_transaction_keeps_the_file_accessible(self):
        self.configure(self.staff_id, grants=(("creative", "write"),))
        file = self.note(self.staff, text="Retain on failed deletion")
        original_audit = server.VeloraHandler.audit

        def fail_delete_audit(handler, event_type, **kwargs):
            if event_type == "folder_file_deleted":
                raise sqlite3.OperationalError("Fixture audit failure")
            return original_audit(handler, event_type, **kwargs)

        with mock.patch.object(server.VeloraHandler, "audit", fail_delete_audit):
            self.assertEqual(self.staff.request("DELETE", f"/api/intranet/files/{file['id']}")[0], 500)
        self.assertEqual(len(self.list_files(self.staff)), 1)
        status, content, _ = self.staff.request("GET", file["downloadUrl"])
        self.assertEqual(status, 200)
        self.assertIn(b"Retain on failed deletion", content)

    def test_file_mutations_need_csrf_and_documents_are_download_only(self):
        self.configure(self.staff_id, grants=(("creative", "write"),))
        note_payload = {"name": "Protected note", "kind": "note", "text": "Internal text"}
        self.assertEqual(self.staff.request("POST", "/api/intranet/folders/creative/files", note_payload, token=False)[0], 403)
        status, payload, _ = self.upload(self.staff, "Policy.txt", b"Policy fixture", "text/plain")
        self.assertIn(status, (200, 201), payload)
        file = payload["file"]
        self.assertNotIn("previewUrl", file)
        status, content, headers = self.staff.request("GET", file["downloadUrl"])
        self.assertEqual(status, 200)
        self.assertEqual(content, b"Policy fixture")
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertIn(self.staff.request("GET", f"/api/intranet/files/{file['id']}/preview")[0], (400, 404, 415))
        self.assertEqual(self.staff.request("DELETE", f"/api/intranet/files/{file['id']}", token=False)[0], 403)
        self.assertEqual(len(self.list_files(self.staff)), 1)

    def test_upload_size_limit_prevents_persisting_large_files(self):
        self.configure(self.staff_id, grants=(("creative", "write"),))
        status, _, _ = self.upload(self.staff, "Oversized.txt", b"a" * (8 * 1024 * 1024 + 1), "text/plain")
        self.assertIn(status, (400, 413))
        self.assertEqual(self.list_files(self.staff), [])

    def test_private_storage_never_has_a_direct_public_download_path(self):
        self.configure(self.staff_id, grants=(("creative", "write"),))
        file = self.note(self.staff, text="Private storage sentinel")
        storage = self.database.parent / "shared-folders"
        saved = [path for path in storage.rglob("*") if path.is_file()]
        self.assertEqual(len(saved), 1)
        self.assertNotIn(file["name"], saved[0].name)
        for path in ("/" + saved[0].relative_to(self.root).as_posix(),
                     "/assets/../" + saved[0].relative_to(self.root).as_posix(),
                     "/api/intranet/files/../../" + saved[0].name):
            with self.subTest(path=path):
                status, content, _ = self.anonymous.request("GET", path)
                self.assertNotEqual(status, 200)
                self.assertNotIn(b"Private storage sentinel", content if isinstance(content, bytes) else json.dumps(content).encode())

    def test_department_files_survive_account_deletion_but_staff_permissions_do_not(self):
        self.configure(self.staff_id, grants=(("creative", "write"),))
        self.configure(self.other_id, grants=(("creative", "read"),))
        file = self.note(self.staff, text="Keep this department record")
        self.assertEqual(self.staff.request("DELETE", "/api/account", {"password": PASSWORD})[0], 200)
        with self.app.connect() as db:
            self.assertIsNone(db.execute("SELECT 1 FROM staff_profiles WHERE user_id=?", (self.staff_id,)).fetchone())
            self.assertIsNone(db.execute("SELECT 1 FROM folder_grants WHERE user_id=?", (self.staff_id,)).fetchone())
            self.assertIsNone(db.execute("SELECT created_by FROM shared_files WHERE id=?", (file["id"],)).fetchone()[0])
        status, content, _ = self.other.request("GET", file["downloadUrl"])
        self.assertEqual(status, 200)
        self.assertIn(b"Keep this department record", content)
        self.assertEqual(self.staff.request("GET", file["downloadUrl"])[0], 401)


if __name__ == "__main__":
    unittest.main()
