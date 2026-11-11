"""Metadata/discovery checks using disposable accounts and catalog records."""
from html.parser import HTMLParser
import json
from pathlib import Path
import unittest
import threading
from xml.etree import ElementTree as ET

import test_catalog_server as catalog_tests
import seo
import server
from test_auth_server import Client


class Head(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.meta = {}
        self.links = {}
        self.titles = []
        self.in_title = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self.in_title = True
            self.titles.append("")
        elif tag == "meta":
            key = attrs.get("name") or attrs.get("property")
            self.meta.setdefault(key, []).append(attrs.get("content"))
        elif tag == "link":
            self.links.setdefault(attrs.get("rel"), []).append(attrs.get("href"))

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.titles[-1] += data


class SeoServerTests(unittest.TestCase):
    setUpClass = catalog_tests.CatalogServerTests.__dict__["setUpClass"]
    tearDown = catalog_tests.CatalogServerTests.tearDown

    def setUp(self):
        catalog_tests.CatalogServerTests.setUp(self)
        self.app.public_url = "https://velora.org"
        for page in seo.PAGES:
            (self.root / page).write_text('<!doctype html><html><head><title>Old title</title><meta name="description" content="Old description"></head><body>Fixture</body></html>', encoding="utf-8")
        (self.root / "site.webmanifest").write_text(json.dumps({"name": "Velora", "icons": []}), encoding="utf-8")

    def head(self, path):
        status, body, headers = self.public.request("GET", path)
        return status, Head(body.decode()), headers, body

    def locations(self):
        status, body, headers = self.public.request("GET", "/sitemap.xml")
        self.assertEqual(status, 200)
        self.assertIn("application/xml", headers["Content-Type"])
        return [item.text for item in ET.fromstring(body).findall("{*}url/{*}loc")]

    def test_public_metadata_is_complete_and_local_preview_is_noindex(self):
        status, head, headers, _ = self.head("/?utm_source=anything")
        self.assertEqual(status, 200)
        self.assertEqual(head.links["canonical"], ["https://velora.org/"])
        self.assertEqual(head.meta["og:url"], ["https://velora.org/"])
        self.assertEqual(head.meta["og:image"], ["https://velora.org/assets/brand/og-velora.png"])
        self.assertEqual(head.meta["og:image:width"], ["1200"])
        self.assertEqual(head.meta["og:image:height"], ["630"])
        self.assertEqual(head.meta["twitter:card"], ["summary_large_image"])
        self.assertEqual(len(head.titles), 1)
        self.assertEqual(len(head.meta["description"]), 1)
        self.assertEqual(head.meta["robots"], ["noindex, nofollow"])
        self.assertEqual(headers["X-Robots-Tag"], "noindex, nofollow")

    def test_product_metadata_is_server_rendered_canonical_and_safely_escaped(self):
        name = 'A "special" <script>piece</script> & look'
        self.assertEqual(self.admin.request("PATCH", "/api/admin/products/123456789abcdef0", {"name": name, "description": "A clear product description."})[0], 200)
        status, head, headers, body = self.head("/product.html?id=123456789abcdef0&color=Blue&size=M&utm_source=test")
        self.assertEqual(status, 200)
        self.assertEqual(head.titles, [name + " | Velora"])
        self.assertEqual(head.meta["og:title"], [name + " | Velora"])
        self.assertEqual(head.meta["og:description"], ["A clear product description."])
        self.assertEqual(head.meta["og:image"], ["https://velora.org/assets/first.png"])
        self.assertEqual(head.links["canonical"], ["https://velora.org/product.html?id=123456789abcdef0"])
        self.assertNotIn(b"<script>piece</script>", body)
        status, _, response_headers = self.public.request("HEAD", "/product.html?id=123456789abcdef0&color=Blue&size=M&utm_source=test")
        self.assertEqual(status, 200)
        self.assertEqual(int(response_headers["Content-Length"]), len(body))

    def test_drafts_deleted_unknown_and_duplicate_product_ids_are_not_exposed(self):
        for patch in ({"published": False}, {"published": True}):
            self.assertEqual(self.admin.request("PATCH", "/api/admin/products/123456789abcdef0", patch)[0], 200)
            if not patch["published"]:
                status, head, _, body = self.head("/product.html?id=123456789abcdef0")
                self.assertEqual(status, 404)
                self.assertNotIn("canonical", head.links)
                self.assertNotIn(b"The Existing Suit", body)
        for path in ("/product.html?id=unknown", "/product.html?id=123456789abcdef0&id=unknown"):
            status, head, headers, _ = self.head(path)
            self.assertEqual(status, 404)
            self.assertEqual(head.meta["robots"], ["noindex, nofollow"])
            self.assertEqual(headers["X-Robots-Tag"], "noindex, nofollow")
        self.assertEqual(self.admin.request("DELETE", "/api/admin/products/123456789abcdef0")[0], 200)
        self.assertEqual(self.head("/product.html?id=123456789abcdef0")[0], 404)

    def test_sitemap_follows_current_publication_and_excludes_private_utility_urls(self):
        initial = self.locations()
        product = "https://velora.org/product.html?id=123456789abcdef0"
        self.assertIn(product, initial)
        for page in seo.UTILITY_PAGES:
            self.assertNotIn("https://velora.org/" + page, initial)
        self.assertNotIn("https://velora.org/product.html", initial)
        self.assertEqual(len(initial), len(set(initial)))
        self.assertTrue(all(url.startswith("https://velora.org/") for url in initial))
        self.assertEqual(self.admin.request("PATCH", "/api/admin/products/123456789abcdef0", {"published": False})[0], 200)
        self.assertNotIn(product, self.locations())
        self.assertEqual(self.admin.request("PATCH", "/api/admin/products/123456789abcdef0", {"published": True})[0], 200)
        self.assertIn(product, self.locations())
        self.assertEqual(self.admin.request("DELETE", "/api/admin/products/123456789abcdef0")[0], 200)
        self.assertNotIn(product, self.locations())

    def test_robots_is_closed_on_localhost_and_open_only_for_confirmed_https_origin(self):
        status, body, headers = self.public.request("GET", "/robots.txt")
        self.assertEqual(status, 200)
        self.assertIn(b"Disallow: /\n", body)
        self.assertNotIn(b"Sitemap:", body)
        self.assertEqual(self.public.request("GET", "/", extra_headers={"Host": "velora.org"})[0], 400)
        secure_app = server.make_server(port=0, root=self.root, catalog=self.catalog,
            database=self.root / ".velora/secure-test.sqlite3", public_url="https://velora.org", secure_cookies=True)
        secure_app.RequestHandlerClass.log_message = lambda *args: None
        serving = threading.Thread(target=secure_app.serve_forever, daemon=True)
        serving.start()
        public = Client(secure_app)
        try:
            status, body, _ = public.request("GET", "/robots.txt", extra_headers={"Host": "velora.org"})
            self.assertEqual(status, 200)
            self.assertIn(b"Allow: /\n", body)
            self.assertIn(b"Sitemap: https://velora.org/sitemap.xml", body)
            self.assertIn(b"Allow: /api/catalog\n", body)
            self.assertNotIn(b"Disallow: /\n", body)
            status, body, headers = public.request("GET", "/", extra_headers={"Host": "velora.org"})
            self.assertEqual(status, 200)
            self.assertNotIn("X-Robots-Tag", headers)
            self.assertTrue(Head(body.decode()).meta["robots"][0].startswith("index,"))
            self.assertEqual(public.request("GET", "/", extra_headers={"Host": "evil.example"})[0], 400)
            self.assertEqual(public.request("GET", "/robots.txt")[1], b"User-agent: *\nDisallow: /\n")
        finally:
            secure_app.shutdown()
            secure_app.server_close()
            serving.join(timeout=5)

    def test_private_pages_remain_authorized_and_noindex_without_canonicals(self):
        for page in seo.PRIVATE_PAGES:
            status, body, headers = self.public.request("GET", "/" + page)
            self.assertEqual(status, 302)
            self.assertEqual(body, b"")
            self.assertEqual(headers["X-Robots-Tag"], "noindex, nofollow")
        status, body, headers = self.admin.request("GET", "/admin.html")
        self.assertEqual(status, 200)
        self.assertEqual(Head(body.decode()).meta["robots"], ["noindex, nofollow"])
        self.assertNotIn("canonical", Head(body.decode()).links)
        self.assertEqual(self.public.request("GET", "/site-config.json")[0], 404)

    def test_missing_domain_never_falls_back_to_request_host(self):
        self.app.public_url = ""
        self.assertEqual(self.locations(), [])
        _, head, _, _ = self.head("/")
        self.assertNotIn("canonical", head.links)
        self.assertEqual(head.meta["robots"], ["noindex, nofollow"])
        for value in ("http://velora.org", "https://velora.org/path", "https://user:pass@velora.org", "https://velora.org?x=1", "https://velora.org#x", "https://velora.org:8443"):
            with self.assertRaises(ValueError):
                seo.validate_public_url(value)
        self.assertEqual(seo.validate_public_url("https://VELORA.org/"), "https://velora.org")

    def test_manifest_favicon_and_head_routes(self):
        status, body, headers = self.public.request("GET", "/site.webmanifest")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["name"], "Velora")
        self.assertIn("application/manifest+json", headers["Content-Type"])
        status, body, headers = self.public.request("HEAD", "/site.webmanifest")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertGreater(int(headers["Content-Length"]), 0)
        status, _, headers = self.public.request("GET", "/favicon.ico")
        self.assertEqual(status, 308)
        self.assertEqual(headers["Location"], "/assets/brand/favicon.ico")


if __name__ == "__main__":
    unittest.main()
