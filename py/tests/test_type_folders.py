"""Typed source folders preserve page URLs and their authorization boundaries."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]

import json
import tempfile
import threading
import unittest
from unittest import mock

import server
from test_auth_server import Client


class TypeFolderServerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        for folder in ("html", "css", "js/vendor/three", "json/catalog", "json/config", "json/maps", "py/app", "assets"):
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        for page in ("index.html", "product.html", "account.html", "admin.html", "intranet.html", "login.html", "404.html"):
            (self.root / "html" / page).write_text("<!doctype html><html><head><title>Fixture</title></head><body>" + page + " fixture</body></html>", encoding="utf-8")
        (self.root / "css/styles.css").write_text("body { color: black; }", encoding="utf-8")
        (self.root / "js/script.js").write_text("/* Public script fixture. */", encoding="utf-8")
        (self.root / "js/vendor/three/three.module.js").write_text("/* Approved vendor fixture. */", encoding="utf-8")
        (self.root / "js/vendor/three/unlisted.js").write_text("/* Private unlisted fixture. */", encoding="utf-8")
        (self.root / "json/config/site-config.json").write_text(json.dumps({"publicUrl": "https://velora.org"}), encoding="utf-8")
        (self.root / "json/maps/world-land.json").write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
        (self.root / "py/app/server.py").write_text("private backend fixture", encoding="utf-8")
        (self.root / "assets/portrait.jpg").write_bytes(b"image fixture")
        (self.root / "json/catalog/product-catalog.json").write_text(json.dumps({"products": [{
            "id": "typed-product", "name": "Typed Folder Suit", "image": "assets/portrait.jpg", "founder": "Fixture",
            "collection": "THE TAILORED EDIT", "price": 125, "description": "A disposable product fixture.", "published": True,
        }]}), encoding="utf-8")
        self.app = server.make_server(port=0, root=self.root)
        self.app.RequestHandlerClass.log_message = lambda *args: None
        self.thread = threading.Thread(target=self.app.serve_forever, daemon=True)
        self.thread.start()
        self.client = Client(self.app)

    def tearDown(self):
        self.app.shutdown()
        self.app.server_close()
        self.thread.join(timeout=5)
        self.directory.cleanup()

    def test_default_catalog_config_and_public_source_routes_use_typed_folders(self):
        self.assertEqual(self.app.public_url, "https://velora.org")
        status, data, _ = self.client.request("GET", "/api/catalog")
        self.assertEqual(status, 200)
        self.assertEqual([p["id"] for p in data["products"]], ["typed-product"])
        for route in ("/", "/index.html", "/css/styles.css", "/js/script.js"):
            with self.subTest(route=route):
                status, _, headers = self.client.request("GET", route)
                self.assertEqual(status, 200)
                self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
        for legacy, typed in (("/styles.css?v=2", "/css/styles.css?v=2"), ("/script.js?v=3", "/js/script.js?v=3")):
            status, body, headers = self.client.request("GET", legacy)
            self.assertEqual((status, body, headers["Location"]), (308, b"", typed))

    def test_private_source_folders_are_not_public_or_protected_page_aliases(self):
        for route in ("/html/index.html", "/html/admin.html", "/%68tml/admin.html", "/py/app/server.py",
                      "/json/config/site-config.json", "/json/catalog/product-catalog.json", "/json/maps/world-land-source.json"):
            for method in ("GET", "HEAD"):
                with self.subTest(route=route, method=method):
                    self.assertEqual(self.client.request(method, route)[0], 404)
        for page in ("account.html", "admin.html", "intranet.html"):
            status, body, headers = self.client.request("GET", "/" + page)
            self.assertEqual(status, 302)
            self.assertEqual(body, b"")
            self.assertEqual(headers["Location"], "/login.html?next=" + page)

    def test_only_explicit_vendor_modules_and_the_public_map_are_served(self):
        for route in ("/js/vendor/three/three.module.js", "/json/maps/world-land.json"):
            self.assertEqual(self.client.request("GET", route)[0], 200)
        status, _, headers = self.client.request("GET", "/assets/vendor/three/three.module.js")
        self.assertEqual((status, headers["Location"]), (308, "/js/vendor/three/three.module.js"))
        for route in ("/js/vendor/three/unlisted.js", "/assets/vendor/three/unlisted.js", "/json/vendor/three-source.json"):
            self.assertEqual(self.client.request("GET", route)[0], 404)

    def test_sitemap_and_product_metadata_find_typed_html(self):
        status, sitemap, _ = self.client.request("GET", "/sitemap.xml")
        self.assertEqual(status, 200)
        self.assertIn(b"https://velora.org/product.html?id=typed-product", sitemap)
        self.assertNotIn(b"/html/", sitemap)
        status, html, _ = self.client.request("GET", "/product.html?id=typed-product")
        self.assertEqual(status, 200)
        self.assertIn(b"Typed Folder Suit", html)

    def test_source_links_cannot_alias_an_unprotected_name_to_private_html(self):
        alias = self.root / "html/public.html"
        alias.write_text("public placeholder", encoding="utf-8")
        original = Path.resolve

        def resolve(path, *args, **kwargs):
            if path == alias:
                return self.root / "html/admin.html"
            return original(path, *args, **kwargs)

        with mock.patch.object(Path, "resolve", resolve):
            self.assertEqual(self.client.request("GET", "/public.html")[0], 404)


if __name__ == "__main__":
    unittest.main()
