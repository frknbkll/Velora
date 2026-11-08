"""Starter imports preserve private access, existing files and intentional deletions."""
import csv
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import server
from test_auth_server import Client, PASSWORD

spec = importlib.util.spec_from_file_location("department_seed", ROOT / "tools/seed-department-documents.py")
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)


class DepartmentDocumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = server.hash_password(PASSWORD)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.database = root / ".velora/test.sqlite3"
        catalog = root / "product-catalog.json"
        catalog.write_text(json.dumps({"products": []}), encoding="utf-8")
        self.app = server.make_server(port=0, database=self.database, catalog=catalog, root=root)
        self.app.RequestHandlerClass.log_message = lambda *args: None
        with self.app.connect() as connection:
            self.owner_id = connection.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,'admin',?)", ("Sample Owner", "owner@example.test", self.password_hash, server.now_iso())).lastrowid
            self.staff_id = connection.execute("INSERT INTO users(name,email,password_hash,role,created_at,account_type) VALUES(?,?,?,'customer',?,'velora')", ("Sample Finance", "staff@velora.com", self.password_hash, server.now_iso())).lastrowid
            self.other_id = connection.execute("INSERT INTO users(name,email,password_hash,role,created_at,account_type) VALUES(?,?,?,'customer',?,'velora')", ("Sample HR", "other@velora.com", self.password_hash, server.now_iso())).lastrowid
        self.thread = threading.Thread(target=self.app.serve_forever, daemon=True)
        self.thread.start()
        self.owner, self.staff, self.other = Client(self.app), Client(self.app), Client(self.app)
        for client, email in ((self.owner, "owner@example.test"), (self.staff, "staff@velora.com"), (self.other, "other@velora.com")):
            self.assertEqual(client.login(email=email)[0], 200)

    def tearDown(self):
        self.app.shutdown()
        self.app.server_close()
        self.thread.join(timeout=5)
        self.temporary.cleanup()

    def configure(self, user_id, department, access="read"):
        status, payload, _ = self.owner.request("PATCH", f"/api/admin/folder-access/{user_id}", {
            "active": True, "department": department, "grants": [{"folder": department, "access": access}],
        })
        self.assertEqual(status, 200, payload)

    def test_country_library_is_complete_and_repeat_import_preserves_existing_files(self):
        self.configure(self.staff_id, "creative", "write")
        existing = self.staff.request("POST", "/api/intranet/folders/creative/files", {
            "name": "Existing working note", "kind": "note", "text": "Keep this original resource unchanged.",
        })[1]["file"]
        with self.app.connect() as connection:
            profiles = [tuple(row) for row in connection.execute("SELECT * FROM staff_profiles")]
            grants = [tuple(row) for row in connection.execute("SELECT * FROM folder_grants")]
            roles = [tuple(row) for row in connection.execute("SELECT id,role FROM users")]
        result = seed.seed_documents(self.database)
        self.assertEqual(result["added"], 63)
        self.assertEqual(set(result["departments"].values()), {7})
        self.assertEqual(len(result["departments"]), 9)
        again = seed.seed_documents(self.database)
        self.assertEqual((again["added"], again["alreadyPresent"]), (0, 63))
        with self.app.connect() as connection:
            self.assertEqual(profiles, [tuple(row) for row in connection.execute("SELECT * FROM staff_profiles")])
            self.assertEqual(grants, [tuple(row) for row in connection.execute("SELECT * FROM folder_grants")])
            self.assertEqual(roles, [tuple(row) for row in connection.execute("SELECT id,role FROM users")])
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM shared_files").fetchone()[0], 64)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM shared_files WHERE kind='note'").fetchone()[0], 55)
            rows = connection.execute("SELECT * FROM shared_files WHERE name LIKE 'Sample - %'").fetchall()
            for row in rows:
                data = (self.app.shared_folder_root / row["storage_name"]).read_bytes()
                if row["kind"] == "note":
                    self.assertIn(b"DRAFT EXAMPLE", data)
                    self.assertIn(b"Unassigned", data)
                else:
                    tracker = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
                    self.assertEqual({item["Country"] for item in tracker}, {value[0] for value in seed.COUNTRIES.values()})
                    self.assertEqual(len(tracker), 6)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM security_events WHERE event_type='folder_library_seeded'").fetchone()[0], 1)
        status, data, _ = self.staff.request("GET", existing["downloadUrl"])
        self.assertEqual(status, 200)
        self.assertEqual(data, b"Keep this original resource unchanged.")

    def test_seeded_finance_and_hr_files_keep_department_access_checks(self):
        seed.seed_documents(self.database)
        self.configure(self.staff_id, "finance")
        self.configure(self.other_id, "people")
        status, finance, _ = self.staff.request("GET", "/api/intranet/folders/finance/files")
        self.assertEqual(status, 200)
        self.assertEqual(len(finance["files"]), 7)
        status, hr, _ = self.other.request("GET", "/api/intranet/folders/people/files")
        self.assertEqual(status, 200)
        self.assertEqual(len(hr["files"]), 7)
        for file in finance["files"]:
            self.assertEqual(self.staff.request("GET", file["downloadUrl"])[0], 200)
            self.assertEqual(self.other.request("GET", file["downloadUrl"])[0], 403)
            self.assertEqual(self.owner.request("GET", file["downloadUrl"])[0], 403)
            self.assertEqual(Client(self.app).request("GET", file["downloadUrl"])[0], 401)
        for file in hr["files"]:
            self.assertEqual(self.staff.request("GET", file["downloadUrl"])[0], 403)
        self.assertEqual(self.staff.request("GET", "/api/intranet/folders/leadership/files")[0], 403)

    def test_repeat_import_does_not_restore_a_deliberately_deleted_example(self):
        seed.seed_documents(self.database)
        self.configure(self.staff_id, "design", "write")
        file = self.staff.request("GET", "/api/intranet/folders/design/files")[1]["files"][0]
        self.assertEqual(self.staff.request("DELETE", f"/api/intranet/files/{file['id']}")[0], 200)
        result = seed.seed_documents(self.database)
        self.assertEqual((result["added"], result["alreadyPresent"], result["previouslyRemoved"]), (0, 62, 1))
        self.assertEqual(len(self.staff.request("GET", "/api/intranet/folders/design/files")[1]["files"]), 6)


if __name__ == "__main__":
    unittest.main()
