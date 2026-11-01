"""Exercise account authorization and catalog persistence against a real HTTP server."""

import hashlib
import http.client
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import server


PASSWORD = "a comfortably long password"


class Client:
    def __init__(self, app):
        self.app = app
        self.cookie = ""
        self.csrf = ""

    def request(self, method, path, data=None, *, token=True, origin=True, extra_headers=None, raw=None):
        headers = {}
        if self.cookie:
            headers["Cookie"] = self.cookie
        if method not in {"GET", "HEAD"}:
            headers["Content-Type"] = "application/json"
            if origin:
                headers["Origin"] = f"http://127.0.0.1:{self.app.server_port}"
            if token and self.csrf:
                headers["X-CSRF-Token"] = self.csrf
        headers.update(extra_headers or {})
        body = raw if raw is not None else json.dumps(data if data is not None else {}) if method not in {"GET", "HEAD"} else None
        connection = http.client.HTTPConnection("127.0.0.1", self.app.server_port, timeout=10)
        connection.request(method, path, body, headers)
        response = connection.getresponse()
        content = response.read()
        response_headers = dict(response.getheaders())
        if "Set-Cookie" in response_headers:
            self.cookie = response_headers["Set-Cookie"].split(";", 1)[0]
        payload = json.loads(content) if content and response_headers.get("Content-Type", "").startswith("application/json") else content
        if isinstance(payload, dict) and payload.get("csrfToken"):
            self.csrf = payload["csrfToken"]
        status = response.status
        connection.close()
        return status, payload, response_headers

    def register(self, **changes):
        data = {"name": "Maya Bennett", "email": "maya@example.com", "password": PASSWORD, "terms": True, "ageConfirmed": True}
        data.update(changes)
        return self.request("POST", "/api/auth/register", data)

    def login(self, email="maya@example.com", password=PASSWORD, **changes):
        return self.request("POST", "/api/auth/login", {"email": email, "password": password, **changes})


class AccountServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin_hash = server.hash_password(PASSWORD)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.database = self.root / ".velora" / "test.sqlite3"
        (self.root / "index.html").write_text("<!doctype html><title>Velora</title>", encoding="utf-8")
        (self.root / "server.py").write_text("private backend source", encoding="utf-8")
        (self.root / "assets").mkdir()
        (self.root / "assets" / "portrait.jpg").write_bytes(b"image")
        self.catalog = self.root / "product-catalog.json"
        self.catalog.write_text(json.dumps({"products": [{
            "id": "d23c06a0c60a8147", "name": "The Ivory Suit", "image": "assets/portrait.jpg",
            "founder": "Victoria Mendez", "collection": "THE TAILORED EDIT", "price": 240,
            "description": "A considered ivory suit.", "published": True,
        }]}), encoding="utf-8")
        self.app = server.make_server(port=0, database=self.database, catalog=self.catalog, root=self.root)
        self.app.RequestHandlerClass.log_message = lambda *args: None
        with self.app.connect() as connection:
            connection.execute("INSERT INTO users (name,email,password_hash,role,created_at) VALUES (?, ?, ?, 'admin', ?)", (
                "Store Owner", "owner@example.com", self.admin_hash, server.now_iso(),
            ))
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
        self.assertEqual(client.login(email="owner@example.com")[0], 200)
        return client

    def test_register_login_and_logout_with_cookie_sessions(self):
        self.assertEqual(self.client.request("GET", "/api/auth/me")[1], {"user": None, "csrfToken": None})
        status, data, headers = self.client.register(email="  MAYA@Example.COM  ")
        self.assertEqual(status, 201)
        self.assertEqual(data["user"]["email"], "maya@example.com")
        self.assertEqual(data["user"]["role"], "customer")
        self.assertEqual(set(data["user"]), set(server.USER_FIELDS))
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Lax", headers["Set-Cookie"])
        self.assertNotIn("Max-Age", headers["Set-Cookie"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(self.client.request("GET", "/api/auth/me")[1]["user"]["name"], "Maya Bennett")
        self.assertEqual(self.client.request("POST", "/api/auth/logout")[0], 200)
        self.assertIsNone(self.client.request("GET", "/api/auth/me")[1]["user"])
        self.assertEqual(self.client.login(password="incorrect password")[0], 401)
        self.assertEqual(self.client.login()[0], 200)

    def test_registration_validation_and_no_browser_admin_promotion(self):
        for changes in ({"password": "short"}, {"terms": False}, {"ageConfirmed": False}, {"name": "x" * 81}, {"email": "invalid"}, {"role": "admin"}):
            with self.subTest(changes=changes):
                self.assertEqual(self.client.register(**changes)[0], 400)
        self.assertEqual(self.client.register()[0], 201)
        self.assertEqual(Client(self.app).register(email="MAYA@EXAMPLE.COM")[0], 409)
        self.assertEqual(self.client.request("PATCH", "/api/account", {"role": "admin"})[0], 400)

    def test_anonymous_and_customer_cannot_access_admin_data(self):
        for path in ("overview", "products", "customers"):
            self.assertEqual(self.client.request("GET", f"/api/admin/{path}")[0], 401)
        self.client.register()
        for path in ("overview", "products", "customers"):
            self.assertEqual(self.client.request("GET", f"/api/admin/{path}")[0], 403)
        self.assertEqual(self.client.request("PATCH", "/api/admin/products/d23c06a0c60a8147", {"price": 100})[0], 403)

    def test_admin_catalog_changes_are_persistent_and_visibility_is_public(self):
        self.client.register()
        admin = self.admin()
        overview = admin.request("GET", "/api/admin/overview")[1]
        self.assertEqual(overview["totalProducts"], 1)
        self.assertEqual(overview["totalCustomers"], 1)
        self.assertEqual(len(overview["recentCustomers"]), 1)
        self.assertEqual(admin.request("GET", "/api/admin/customers")[1]["customers"][0]["role"], "customer")
        status, data, _ = admin.request("PATCH", "/api/admin/products/d23c06a0c60a8147", {
            "price": 199.95, "description": "A new description.", "published": False,
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["product"]["price"], 199.95)
        self.assertIs(data["product"]["published"], False)
        self.assertEqual(self.client.request("GET", "/api/catalog")[1]["products"], [])
        self.assertEqual(admin.request("GET", "/api/admin/products")[1]["products"][0]["description"], "A new description.")
        self.assertEqual(admin.request("GET", "/api/admin/overview")[1]["draftProducts"], 1)
        with self.app.connect() as connection:
            self.assertEqual(connection.execute("SELECT price FROM products").fetchone()[0], 199.95)
        self.assertEqual(admin.request("PATCH", "/api/admin/products/d23c06a0c60a8147", {"published": True})[0], 200)
        self.assertEqual(self.client.request("GET", "/api/catalog")[1]["products"][0]["price"], 199.95)

    def test_origin_and_csrf_are_required_for_mutations(self):
        self.assertEqual(self.client.register()[0], 201)
        self.assertEqual(self.client.request("PATCH", "/api/account", {"name": "New Name"}, token=False)[0], 403)
        self.assertEqual(self.client.request("POST", "/api/auth/logout", origin=False)[0], 403)
        self.assertEqual(self.client.request("POST", "/api/auth/logout", extra_headers={"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.client.request("POST", "/api/auth/logout", extra_headers={"Sec-Fetch-Site": "cross-site"})[0], 403)
        self.assertEqual(self.client.request("POST", "/api/auth/logout", extra_headers={"X-CSRF-Token": "wrong"})[0], 403)
        admin = self.admin()
        self.assertEqual(admin.request("PATCH", "/api/admin/products/d23c06a0c60a8147", {"price": 99}, token=False)[0], 403)
        self.assertEqual(self.client.request("GET", "/api/auth/me")[0], 200)

    def test_profile_and_password_change_invalidates_other_sessions(self):
        self.client.register()
        other = Client(self.app)
        other.login()
        self.assertEqual(self.client.request("PATCH", "/api/account", {"name": "Maya Updated"})[1]["user"]["name"], "Maya Updated")
        changes = {"currentPassword": "wrong", "newPassword": "a new long password"}
        self.assertEqual(self.client.request("PATCH", "/api/account", changes)[0], 400)
        changes["currentPassword"] = PASSWORD
        self.assertEqual(self.client.request("PATCH", "/api/account", changes)[0], 200)
        self.assertIsNone(other.request("GET", "/api/auth/me")[1]["user"])
        self.assertIsNotNone(self.client.request("GET", "/api/auth/me")[1]["user"])
        self.assertEqual(Client(self.app).login()[0], 401)
        self.assertEqual(Client(self.app).login(password=changes["newPassword"])[0], 200)

    def test_password_and_session_tokens_are_not_stored_as_plain_text(self):
        self.client.register()
        token = self.client.cookie.split("=", 1)[1]
        with self.app.connect() as connection:
            user = connection.execute("SELECT * FROM users WHERE email = 'maya@example.com'").fetchone()
            session = connection.execute("SELECT * FROM sessions WHERE user_id = ?", (user["id"],)).fetchone()
        self.assertNotIn(PASSWORD, user["password_hash"])
        self.assertTrue(server.verify_password(PASSWORD, user["password_hash"]))
        self.assertNotEqual(session["token_hash"], token)
        self.assertEqual(session["token_hash"], hashlib.sha256(token.encode()).hexdigest())

    def test_password_change_prevents_in_flight_old_password_login(self):
        self.client.register()
        login_client = Client(self.app)
        verified = threading.Event()
        resume = threading.Event()
        result = {}
        original_issue = server.VeloraHandler.issue_session

        def paused_issue(handler, user, remember=False):
            if handler.path_only == "/api/auth/login":
                verified.set()
                if not resume.wait(10):
                    raise RuntimeError("The concurrent password-change check timed out")
            return original_issue(handler, user, remember)

        def login():
            result["response"] = login_client.login()

        with mock.patch.object(server.VeloraHandler, "issue_session", paused_issue):
            pending = threading.Thread(target=login, daemon=True)
            pending.start()
            try:
                self.assertTrue(verified.wait(5), "Login did not reach the verified-password barrier")
                self.assertEqual(self.client.request("PATCH", "/api/account", {
                    "currentPassword": PASSWORD, "newPassword": "a freshly changed password",
                })[0], 200)
            finally:
                resume.set()
                pending.join(timeout=10)
        self.assertFalse(pending.is_alive())
        self.assertEqual(result["response"][0], 401)
        self.assertIsNone(login_client.request("GET", "/api/auth/me")[1]["user"])
        with self.app.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 1)

    def test_stale_password_change_cannot_overwrite_newer_password(self):
        self.client.register()
        concurrent_client = Client(self.app)
        # Model concurrent requests from two tabs using the same retained session.
        concurrent_client.cookie, concurrent_client.csrf = self.client.cookie, self.client.csrf
        verified = threading.Event()
        resume = threading.Event()
        result = {}
        original_verify = server.verify_password

        def paused_verify(password, encoded):
            accepted = original_verify(password, encoded)
            if accepted and not verified.is_set():
                verified.set()
                if not resume.wait(10):
                    raise RuntimeError("The concurrent password-change check timed out")
            return accepted

        def stale_change():
            result["response"] = concurrent_client.request("PATCH", "/api/account", {
                "currentPassword": PASSWORD, "newPassword": "a stale concurrent password",
            })

        with mock.patch.object(server, "verify_password", paused_verify):
            pending = threading.Thread(target=stale_change, daemon=True)
            pending.start()
            try:
                self.assertTrue(verified.wait(5), "Password change did not reach the verification barrier")
                self.assertEqual(self.client.request("PATCH", "/api/account", {
                    "currentPassword": PASSWORD, "newPassword": "the most recent password",
                })[0], 200)
            finally:
                resume.set()
                pending.join(timeout=10)
        self.assertFalse(pending.is_alive())
        self.assertEqual(result["response"][0], 401)
        self.assertEqual(Client(self.app).login(password="the most recent password")[0], 200)
        self.assertEqual(Client(self.app).login(password="a stale concurrent password")[0], 401)

    def test_remember_and_expired_sessions(self):
        self.client.register()
        response = self.client.login(remember=True)
        self.assertIn("Max-Age=2592000", response[2]["Set-Cookie"])
        with self.app.connect() as connection:
            connection.execute("UPDATE sessions SET expires_at = ?", (int(time.time()) - 1,))
        self.assertIsNone(self.client.request("GET", "/api/auth/me")[1]["user"])
        self.assertEqual(self.client.request("PATCH", "/api/account", {"name": "New Name"})[0], 401)

    def test_product_validation_rejects_invalid_data_and_immutable_fields(self):
        admin = self.admin()
        for data in ({"price": -1}, {"price": 0}, {"price": True}, {"price": "120"}, {"price": 1.005},
                     {"price": 100000.01}, {"description": " "}, {"description": "x" * 2001},
                     {"published": "false"}, {"color_key": "changed"}, {"image": "https://evil.example/x.png"}, {}):
            with self.subTest(data=data):
                self.assertEqual(admin.request("PATCH", "/api/admin/products/d23c06a0c60a8147", data)[0], 400)
        self.assertEqual(admin.request("PATCH", "/api/admin/products/doesnotexist", {"price": 25})[0], 404)

    def test_rate_limit_prevents_repeated_password_guessing(self):
        for _ in range(5):
            self.assertEqual(self.client.login(email="missing@example.com")[0], 401)
        self.assertEqual(self.client.login(email="missing@example.com")[0], 429)

    def test_private_files_traversal_and_untrusted_hosts_are_rejected(self):
        for path in ("/server.py", "/.velora/test.sqlite3", "/product-catalog.json", "/tests/test_auth_server.py",
                     "/tmp/test.js", "/../server.py", "/%2e%2e/server.py", "/assets/../../server.py", "/assets/%5c..%5cserver.py", "/assets/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.request("GET", path)[0], 404)
        self.assertEqual(self.client.request("GET", "/", extra_headers={"Host": "evil.example"})[0], 400)
        self.assertEqual(self.client.request("GET", "/assets/portrait.jpg")[0], 200)
        self.assertEqual(self.client.request("GET", "/")[0], 200)

    def test_malformed_large_and_wrong_content_type_bodies_are_rejected(self):
        self.assertEqual(self.client.request("POST", "/api/auth/login", raw="{")[0], 400)
        self.assertEqual(self.client.request("POST", "/api/auth/login", raw="[]")[0], 400)
        self.assertEqual(self.client.request("POST", "/api/auth/login", raw='{"x":NaN}')[0], 400)
        self.assertEqual(self.client.request("POST", "/api/auth/login", raw=" " * 20_000)[0], 413)
        self.assertEqual(self.client.request("POST", "/api/auth/login", extra_headers={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.client.request("POST", "/api/auth/register", origin=False)[0], 403)
        self.assertEqual(self.client.request("HEAD", "/")[1], b"")
        self.assertEqual(self.client.request("DELETE", "/api/auth/me")[0], 405)


if __name__ == "__main__":
    unittest.main()
