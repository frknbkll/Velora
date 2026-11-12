"""Exercise catalog administration against disposable HTTP servers and image files."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file


import base64
import json
from pathlib import Path
import sqlite3
import struct
import sys
import tempfile
import threading
import unittest
import zlib
from unittest.mock import patch

import server
from test_auth_server import Client, PASSWORD


def png(width=2, height=2):
    def chunk(kind, data):
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))
    pixels = b"".join(b"\0" + b"\xa6\x4e\x37" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))


class CatalogServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = server.hash_password(PASSWORD)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.database = self.root / ".velora" / "test.sqlite3"
        (self.root / "assets").mkdir()
        (self.root / "assets" / "first.png").write_bytes(png())
        (self.root / "assets" / "second.png").write_bytes(png(3, 2))
        (self.root / "assets" / "third.png").write_bytes(png(4, 2))
        self.catalog = self.root / "product-catalog.json"
        self.catalog.write_text(json.dumps({"products": [{
            "id": "123456789abcdef0", "name": "The Existing Suit", "image": "assets/first.png",
            "founder": "Victoria Mendez", "collection": "THE TAILORED EDIT", "price": 240,
            "description": "A considered suit.", "published": True,
        }]}), encoding="utf-8")
        self.app = server.make_server(port=0, database=self.database, catalog=self.catalog, root=self.root)
        self.app.RequestHandlerClass.log_message = lambda *args: None
        with self.app.connect() as connection:
            connection.execute("INSERT INTO users (name,email,password_hash,role,created_at) VALUES (?, ?, ?, 'admin', ?)", (
                "Test Administrator", "admin@example.test", self.password_hash, server.now_iso(),
            ))
        self.thread = threading.Thread(target=self.app.serve_forever, daemon=True)
        self.thread.start()
        self.admin = Client(self.app)
        self.assertEqual(self.admin.login(email="admin@example.test")[0], 200)
        self.public = Client(self.app)

    def tearDown(self):
        self.app.shutdown()
        self.app.server_close()
        self.thread.join(timeout=5)
        self.directory.cleanup()

    def product_payload(self, **updates):
        return {
            "name": "A New Linen Set", "images": ["assets/first.png", "assets/second.png"],
            "founder": "Beyza Keskinci", "collection": "THE EVERYDAY EDIT", "price": 129.99,
            "description": "An airy coordinated linen set.", "published": True,
            "stock": 4, "sizes": ["S", "M", "L"], "base_color": "Terracotta", "color_hex": "#A64E37",
            **updates,
        }

    def create(self, **updates):
        response = self.admin.request("POST", "/api/admin/products", self.product_payload(**updates))
        self.assertEqual(response[0], 201, response[1])
        return response[1]["product"]

    def path(self, product):
        return "/api/admin/products/" + product["id"]

    def test_create_edit_and_cover_order_reach_public_catalog(self):
        product = self.create(sku="summer-001")
        self.assertEqual(product["sku"], "SUMMER-001")
        self.assertEqual(product["image"], "assets/first.png")
        self.assertEqual(product["images"], ["assets/first.png", "assets/second.png"])
        self.assertEqual(product["color_key"], "")
        self.assertEqual(product["legacy_key"], "")
        self.assertEqual(product["color_hex"], "#a64e37")
        self.assertEqual(product["stock"], 4)
        self.assertEqual(product["sizes"], ["S", "M", "L"])
        self.assertIsNone(product["deleted_at"])
        self.assertTrue(product["created_at"])
        status, payload, _ = self.admin.request("PATCH", self.path(product), {
            "name": "A Revised Linen Set", "images": ["assets/second.png", "assets/first.png"],
            "founder": "Luna Moretti", "collection": "THE SOFT EDIT", "sku": "summer-002",
            "stock": 0, "sizes": ["XS", "XL"], "price": 149.95,
        })
        self.assertEqual(status, 200, payload)
        edited = payload["product"]
        self.assertEqual(edited["name"], "A Revised Linen Set")
        self.assertEqual(edited["image"], "assets/second.png")
        self.assertEqual(edited["color_key"], "")
        self.assertEqual(edited["stock"], 0)
        listed = self.public.request("GET", "/api/catalog")[1]["products"]
        self.assertEqual(next(item for item in listed if item["id"] == product["id"]), edited)

    def test_public_product_detail_only_returns_published_products(self):
        status, response, _ = self.public.request("GET", "/api/catalog/123456789abcdef0")
        self.assertEqual(status, 200, response)
        self.assertEqual(response["product"]["name"], "The Existing Suit")

        draft = self.create(published=False)
        self.assertEqual(self.public.request("GET", f"/api/catalog/{draft['id']}")[0], 404)
        self.assertEqual(self.public.request("GET", "/api/catalog/does-not-exist")[0], 404)
        self.assertEqual(self.public.request("GET", "/api/catalog/123456789abcdef0/extra")[0], 404)

    def test_color_variants_can_be_added_and_edited(self):
        product = self.create()
        path = self.path(product) + "/colors"
        status, payload, _ = self.admin.request("POST", path, {
            "name": "Midnight", "hex": "#252321", "image": "assets/third.png",
        })
        self.assertEqual(status, 201, payload)
        updated = payload["product"]
        self.assertEqual(updated["id"], product["id"])
        self.assertEqual(updated["color_variants"], [{
            "name": "Midnight", "hex": "#252321", "image": "assets/third.png",
        }])
        self.assertEqual(self.admin.request("POST", path, {
            "name": "midnight", "hex": "#000000", "image": "assets/second.png",
        })[0], 409)
        self.assertEqual(self.admin.request("POST", path, {
            "name": "Sand", "hex": "#c9b8a1", "image": "assets/first.png",
        })[0], 409)
        public = next(item for item in self.public.request("GET", "/api/catalog")[1]["products"] if item["id"] == product["id"])
        self.assertEqual(public["color_variants"], updated["color_variants"])
        removed = self.admin.request("PATCH", self.path(product), {"color_variants": []})[1]["product"]
        self.assertEqual(removed["color_variants"], [])

    def test_optional_product_details_round_trip_and_can_be_cleared(self):
        details = {
            "material": "97% cotton, 3% elastane", "fabric_weight": "180 g/m²",
            "origin": "Portugal", "fit": "Relaxed fit.\nCompare with the product measurements.",
        }
        product = self.create(**{field: f"  {value}  " for field, value in details.items()})
        for field, value in details.items():
            self.assertEqual(product[field], value)
        # A partial edit and database initialization must preserve entered facts.
        self.assertEqual(self.admin.request("PATCH", self.path(product), {"price": 135})[0], 200)
        self.app.initialize_database(self.catalog)
        public = next(item for item in self.public.request("GET", "/api/catalog")[1]["products"] if item["id"] == product["id"])
        copied = self.admin.request("POST", self.path(product) + "/duplicate", {})[1]["product"]
        for field, value in details.items():
            self.assertEqual(public[field], value)
            self.assertEqual(copied[field], value)
        status, payload, _ = self.admin.request("PATCH", self.path(product), dict.fromkeys(details, "  "))
        self.assertEqual(status, 200, payload)
        for field in details:
            self.assertEqual(payload["product"][field], "")
        unspecified = self.create()
        for field in details:
            self.assertEqual(unspecified[field], "")

    def test_optional_product_details_reject_invalid_values_without_mutating(self):
        product = self.create(material="Saved composition")
        for field, limit in (("material", 500), ("fabric_weight", 120), ("origin", 160), ("fit", 500)):
            for value in (None, 42, [], {}, "x" * (limit + 1), "bad\x00text"):
                with self.subTest(field=field, value=value):
                    self.assertEqual(self.admin.request("PATCH", self.path(product), {field: value})[0], 400)
            unchanged = next(item for item in self.admin.request("GET", "/api/admin/products")[1]["products"] if item["id"] == product["id"])
            self.assertEqual(unchanged[field], product[field])
            status, payload, _ = self.admin.request("PATCH", self.path(product), {field: "x" * limit})
            self.assertEqual(status, 200, payload)
            self.assertEqual(payload["product"][field], "x" * limit)
        public = next(item for item in self.public.request("GET", "/api/catalog")[1]["products"] if item["id"] == product["id"])
        self.assertEqual(public["material"], "x" * 500)

    def test_seed_defaults_remain_untracked_and_colors_stay_stable(self):
        existing = self.admin.request("GET", "/api/admin/products")[1]["products"][0]
        self.assertEqual(existing["images"], ["assets/first.png"])
        self.assertEqual(existing["color_key"], "assets/first.png")
        self.assertEqual(existing["legacy_key"], "The Existing Suit:assets/first.png")
        self.assertIsNone(existing["stock"])
        self.assertEqual(existing["sizes"], ["XS", "S", "M", "L"])
        for field in ("material", "fabric_weight", "origin", "fit"):
            self.assertEqual(existing[field], "")
        updated = self.admin.request("PATCH", self.path(existing), {"images": ["assets/second.png"]})[1]["product"]
        self.assertEqual(updated["color_key"], "assets/first.png")
        self.assertEqual(updated["image"], "assets/second.png")

    def test_duplicate_is_draft_with_unique_id_and_sku(self):
        source = self.create(sku="SOURCE-1")
        status, payload, _ = self.admin.request("POST", self.path(source) + "/duplicate", {})
        self.assertEqual(status, 201)
        copied = payload["product"]
        self.assertNotEqual(copied["id"], source["id"])
        self.assertNotEqual(copied["sku"], source["sku"])
        self.assertIs(copied["published"], False)
        self.assertEqual(copied["images"], source["images"])
        self.assertEqual(copied["sizes"], source["sizes"])
        self.assertEqual(copied["stock"], source["stock"])
        self.assertEqual(copied["name"], source["name"] + " (copy)")
        self.assertEqual(copied["legacy_key"], "")
        self.assertNotIn(copied["id"], [item["id"] for item in self.public.request("GET", "/api/catalog")[1]["products"]])
        original = self.admin.request("GET", "/api/admin/products")[1]["products"][0]
        legacy_copy = self.admin.request("POST", self.path(original) + "/duplicate", {})[1]["product"]
        self.assertTrue(original["legacy_key"])
        self.assertEqual(legacy_copy["legacy_key"], "")
        self.assertEqual(legacy_copy["color_key"], original["color_key"])

    def test_trash_restore_and_restart_preserve_tombstones_and_edits(self):
        product = self.admin.request("GET", "/api/admin/products")[1]["products"][0]
        path = self.path(product)
        self.assertEqual(self.admin.request("PATCH", path, {"price": 321.45, "stock": 3})[0], 200)
        status, payload, _ = self.admin.request("DELETE", path, {})
        self.assertEqual(status, 200)
        self.assertIsNotNone(payload["product"]["deleted_at"])
        self.assertIs(payload["product"]["published"], False)
        self.assertEqual(self.public.request("GET", "/api/catalog")[1]["products"], [])
        self.assertEqual(self.admin.request("PATCH", path, {"price": 55})[0], 409)
        self.assertEqual(self.admin.request("POST", path + "/duplicate", {})[0], 409)
        self.app.initialize_database(self.catalog)
        after = self.admin.request("GET", "/api/admin/products")[1]["products"][0]
        self.assertIsNotNone(after["deleted_at"])
        self.assertEqual(after["price"], 321.45)
        self.assertEqual(after["stock"], 3)
        restored = self.admin.request("POST", path + "/restore", {})[1]["product"]
        self.assertIsNone(restored["deleted_at"])
        self.assertIs(restored["published"], False)
        self.assertEqual(restored["price"], 321.45)
        self.assertEqual(self.admin.request("POST", path + "/restore", {})[0], 409)
        self.assertEqual(self.admin.request("PATCH", path, {"published": True})[0], 200)
        self.assertEqual(len(self.public.request("GET", "/api/catalog")[1]["products"]), 1)

    def test_inventory_metrics_and_transactional_activity(self):
        product = self.create()
        self.admin.request("PATCH", self.path(product), {"stock": 0})
        duplicate = self.admin.request("POST", self.path(product) + "/duplicate", {})[1]["product"]
        self.admin.request("DELETE", self.path(product), {})
        self.admin.request("POST", self.path(product) + "/restore", {})
        overview = self.admin.request("GET", "/api/admin/overview")[1]
        self.assertEqual(overview["totalProducts"], 3)
        self.assertEqual(overview["draftProducts"], 2)
        self.assertEqual(overview["lowStockProducts"], 0)
        self.assertEqual(overview["outOfStockProducts"], 2)
        events = self.admin.request("GET", "/api/admin/activity")[1]["events"]
        self.assertEqual([item["action"] for item in reversed(events)], ["create", "update", "duplicate", "trash", "restore"])
        self.assertTrue(all(item["actor_name"] == "Test Administrator" for item in events))
        self.assertEqual(events[2]["product_id"], duplicate["id"])
        self.admin.request("DELETE", self.path(product), {})
        overview = self.admin.request("GET", "/api/admin/overview")[1]
        self.assertEqual(overview["totalProducts"], 2)
        self.assertEqual(overview["trashedProducts"], 1)

    def test_unique_sku_is_case_insensitive_and_reserved_while_trashed(self):
        product = self.create(sku="LINEN-001")
        self.assertEqual(self.admin.request("POST", "/api/admin/products", self.product_payload(sku="linen-001"))[0], 409)
        self.admin.request("DELETE", self.path(product), {})
        self.assertEqual(self.admin.request("POST", "/api/admin/products", self.product_payload(sku="linen-001"))[0], 409)
        fresh = self.create()
        self.assertTrue(fresh["sku"].startswith("VL-"))

    def test_upload_png_can_be_assigned_and_served(self):
        raw = png(4, 3)
        status, payload, _ = self.admin.request("POST", "/api/admin/uploads", {
            "name": "my-product.png", "data": "data:image/png;base64," + base64.b64encode(raw).decode(),
        })
        self.assertEqual(status, 201, payload)
        self.assertRegex(payload["image"], r"^assets/uploads/[a-f0-9]{32}\.png$")
        self.assertEqual((self.root / payload["image"]).read_bytes(), raw)
        self.assertEqual(self.public.request("GET", "/" + payload["image"])[1], raw)
        product = self.create(images=[payload["image"]])
        self.assertEqual(product["image"], payload["image"])
        self.admin.request("DELETE", self.path(product), {})
        self.assertTrue((self.root / payload["image"]).is_file(), "Shared media must not be physically deleted with a product")

    def test_upload_validation_and_size_limits(self):
        cases = [
            {"name": "evil.svg", "data": "data:image/svg+xml;base64," + base64.b64encode(b"<svg/>").decode()},
            {"name": "fake.png", "data": "data:image/png;base64," + base64.b64encode(b"not an image").decode()},
            {"name": "wrong.jpg", "data": "data:image/jpeg;base64," + base64.b64encode(png()).decode()},
            {"name": "invalid.png", "data": "data:image/png;base64,notvalid="},
            {"name": "", "data": "data:image/png;base64," + base64.b64encode(png()).decode()},
            {"name": "image.png", "data": "data:image/png;base64," + base64.b64encode(png()).decode(), "path": "outside"},
        ]
        for data in cases:
            with self.subTest(name=data.get("name")):
                self.assertEqual(self.admin.request("POST", "/api/admin/uploads", data)[0], 400)
        oversized = b"x" * (server.MAX_UPLOAD_BYTES + 1)
        self.assertEqual(self.admin.request("POST", "/api/admin/uploads", {
            "name": "large.png", "data": "data:image/png;base64," + base64.b64encode(oversized).decode(),
        })[0], 413)
        self.assertFalse((self.root / "assets" / "uploads").exists())

    def test_ai_description_generation_sends_only_selected_product_details_and_cover(self):
        response_body = json.dumps({"choices": [{"message": {"content": "A polished, modern jacket with a clean silhouette and considered detailing."}}]}).encode()

        class AIResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _limit):
                return response_body

        requests = []

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return AIResponse()

        with patch.dict(server.os.environ, {"VELORA_OPENAI_API_KEY": "test-key", "VELORA_OPENAI_MODEL": "gpt-4o-mini"}), \
                patch.object(server, "urlopen", side_effect=fake_urlopen):
            status, payload, _ = self.admin.request("POST", "/api/admin/product-description", {
                "name": "The Test Jacket", "collection": "THE EVERYDAY EDIT",
                "base_color": "Terracotta", "image": "assets/first.png",
            })
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["description"], "A polished, modern jacket with a clean silhouette and considered detailing.")
        self.assertEqual(payload["model"], "gpt-4o-mini")
        self.assertEqual(len(requests), 1)
        request, timeout = requests[0]
        self.assertEqual(timeout, 12)
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(request.full_url, "https://api.openai.com/v1/chat/completions")
        sent = json.loads(request.data)
        self.assertEqual(sent["model"], "gpt-4o-mini")
        text = sent["messages"][1]["content"][0]["text"]
        self.assertEqual(json.loads(text), {
            "product_name": "The Test Jacket", "category": "Everyday", "primary_color": "Terracotta",
        })
        image = sent["messages"][1]["content"][1]["image_url"]["url"]
        self.assertEqual(image, "data:image/png;base64," + base64.b64encode(png()).decode("ascii"))

    def test_ai_description_requires_configuration_and_valid_product_details(self):
        payload = {
            "name": "The Test Jacket", "collection": "THE EVERYDAY EDIT",
            "base_color": "Terracotta", "image": "assets/first.png",
        }
        with patch.dict(server.os.environ, {"VELORA_OPENAI_API_KEY": ""}), patch.object(server, "urlopen") as call:
            status, response, _ = self.admin.request("POST", "/api/admin/product-description", payload)
        self.assertEqual(status, 503)
        self.assertIn("VELORA_OPENAI_API_KEY", response["error"])
        call.assert_not_called()

    def test_ai_product_draft_uses_only_uploaded_image_and_validates_generated_fields(self):
        ai_draft = {
            "name": "The Midnight Tailored Set",
            "description": "A polished, coordinated set with a clean silhouette and refined lines.",
            "collection": "THE TAILORED EDIT",
            "base_color": "Midnight",
            "color_hex": "#252321",
            "price": 84.95,
            "sizes": ["S", "M", "L"],
            "extra_color": "Burgundy",
            "extra_color_hex": "#702d3b",
            "material": "Fabric composition requires review.",
            "fabric_weight": "Fabric weight requires review.",
            "origin": "Manufacturing origin requires review.",
            "fit": "Suggested relaxed fit; review against garment measurements.",
            "object_label": "Suit",
        }

        class AIResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _limit):
                return json.dumps({"choices": [{"message": {"content": json.dumps(ai_draft)}}]}).encode()

        requests = []

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return AIResponse()

        with patch.dict(server.os.environ, {"VELORA_OPENAI_API_KEY": "test-key", "VELORA_OPENAI_MODEL": "gpt-4o-mini"}), \
                patch.object(server, "urlopen", side_effect=fake_urlopen):
            status, payload, _ = self.admin.request("POST", "/api/admin/product-draft", {"image": "assets/first.png"})
        self.assertEqual(status, 200, payload)
        self.assertEqual(len(requests), 1)
        request, timeout = requests[0]
        self.assertEqual(timeout, 12)
        self.assertEqual(request.full_url, "https://api.openai.com/v1/chat/completions")
        sent = json.loads(request.data)
        self.assertEqual(sent["response_format"], {"type": "json_object"})
        self.assertEqual(sent["messages"][1]["content"][0]["image_url"]["url"],
                         "data:image/png;base64," + base64.b64encode(png()).decode("ascii"))
        self.assertIn("Do not output stock, designer, SKU", sent["messages"][0]["content"])
        for field in ("material", "fabric_weight", "origin", "fit", "object_label"):
            self.assertIn(field + " (", sent["messages"][0]["content"])
        self.assertEqual(payload["draft"], {
            **ai_draft, "founder": "Velora Studio", "stock": 10, "sku": "", "published": False,
        })

        with patch.dict(server.os.environ, {"VELORA_OPENAI_API_KEY": ""}), patch.object(server, "urlopen") as call:
            status, response, _ = self.admin.request("POST", "/api/admin/product-draft", {"image": "assets/first.png"})
        self.assertEqual(status, 503)
        self.assertIn("VELORA_OPENAI_API_KEY", response["error"])
        call.assert_not_called()

        with patch.dict(server.os.environ, {"VELORA_OPENAI_API_KEY": "test-key"}), \
                patch.object(server, "urlopen", side_effect=fake_urlopen):
            status, _, _ = self.admin.request("POST", "/api/admin/product-draft", {"image": "assets/../server.py"})
        self.assertEqual(status, 400)

        invalid_draft = {**ai_draft, "sizes": [["not-a-size"]]}

        class InvalidResponse(AIResponse):
            def read(self, _limit):
                return json.dumps({"choices": [{"message": {"content": json.dumps(invalid_draft)}}]}).encode()

        with patch.dict(server.os.environ, {"VELORA_OPENAI_API_KEY": "test-key"}), \
                patch.object(server, "urlopen", return_value=InvalidResponse()):
            status, _, _ = self.admin.request("POST", "/api/admin/product-draft", {"image": "assets/first.png"})
        self.assertEqual(status, 502)

        # The current draft contract requires all five detail/object fields;
        # reject legacy responses that omit a required detail field.
        for field in ("material", "fabric_weight", "origin", "fit", "object_label"):
            invalid_draft = {key: value for key, value in ai_draft.items() if key != field}
            with self.subTest(missing_draft_field=field), \
                    patch.dict(server.os.environ, {"VELORA_OPENAI_API_KEY": "test-key"}), \
                    patch.object(server, "urlopen", return_value=InvalidResponse()):
                status, _, _ = self.admin.request("POST", "/api/admin/product-draft", {"image": "assets/first.png"})
                self.assertEqual(status, 502)

        invalid_payloads = [
            {**payload, "collection": "UNKNOWN"},
            {**payload, "image": "assets/../server.py"},
            {**payload, "name": " "},
            {**payload, "extra": "not allowed"},
        ]
        with patch.dict(server.os.environ, {"VELORA_OPENAI_API_KEY": "test-key"}), patch.object(server, "urlopen") as call:
            for invalid in invalid_payloads:
                with self.subTest(payload=invalid):
                    self.assertEqual(self.admin.request("POST", "/api/admin/product-description", invalid)[0], 400)
        call.assert_not_called()

    def test_validation_rejects_bad_identity_inventory_images_and_immutable_fields(self):
        invalid = [
            {"name": " "}, {"name": "x" * 161}, {"founder": " "}, {"founder": "x" * 81},
            {"collection": "UNKNOWN"}, {"stock": -1}, {"stock": True}, {"stock": 1.2}, {"stock": 1000000},
            {"sizes": []}, {"sizes": ["S", "S"]}, {"sizes": ["Unknown"]}, {"sizes": [1]},
            {"images": []}, {"images": ["assets/first.png"] * 13}, {"images": ["assets/first.png"] * 2},
            {"images": ["assets/../server.py"]}, {"images": ["assets/missing.png"]},
            {"images": ["https://example.com/image.jpg"]}, {"images": ["assets/first.png?x=1"]},
            {"images": ["assets/%2e%2e/server.py"]}, {"images": [None]}, {"images": ["assets\\first.png"]},
            {"sku": "bad sku"}, {"sku": "x" * 65}, {"base_color": " "}, {"color_hex": "#abc"},
            {"image": "assets/first.png"}, {"color_key": "assets/second.png"}, {"legacy_key": "changed"}, {"deleted_at": None},
        ]
        existing = self.admin.request("GET", "/api/admin/products")[1]["products"][0]
        for data in invalid:
            with self.subTest(data=data):
                self.assertEqual(self.admin.request("PATCH", self.path(existing), data)[0], 400)
        self.assertEqual(self.admin.request("POST", "/api/admin/products", {"name": "Incomplete"})[0], 400)
        self.assertEqual(self.admin.request("DELETE", self.path(existing), {"name": "extra"})[0], 400)

    def test_customer_anonymous_origin_and_csrf_guards_cover_all_new_mutations(self):
        customer = Client(self.app)
        customer.register()
        product = self.create()
        mutations = [("POST", "/api/admin/products", self.product_payload()),
                     ("PATCH", self.path(product), {"stock": 2}),
                     ("DELETE", self.path(product), {}),
                     ("POST", self.path(product) + "/restore", {}),
                     ("POST", self.path(product) + "/duplicate", {}),
                     ("POST", self.path(product) + "/colors", {"name": "Green", "hex": "#009900", "image": "assets/third.png"}),
                     ("POST", "/api/admin/product-description", {"name": "Test", "collection": "THE EVERYDAY EDIT", "base_color": "Sand", "image": "assets/first.png"}),
                     ("POST", "/api/admin/product-draft", {"image": "assets/first.png"}),
                     ("POST", "/api/admin/uploads", {"name": "test.png", "data": "invalid"})]
        for method, path, body in mutations:
            with self.subTest(method=method, path=path):
                self.assertEqual(self.public.request(method, path, body)[0], 401)
                self.assertEqual(customer.request(method, path, body)[0], 403)
                self.assertEqual(self.admin.request(method, path, body, token=False)[0], 403)
                self.assertEqual(self.admin.request(method, path, body, origin=False)[0], 403)
        self.assertEqual(self.public.request("GET", "/api/admin/activity")[0], 401)
        self.assertEqual(customer.request("GET", "/api/admin/activity")[0], 403)

    def test_legacy_migration_preserves_customer_session_and_price_and_is_idempotent(self):
        legacy = self.root / "legacy.sqlite3"
        with sqlite3.connect(legacy) as connection:
            connection.executescript("""
                CREATE TABLE users (id INTEGER PRIMARY KEY,name TEXT,email TEXT,password_hash TEXT,role TEXT,created_at TEXT);
                CREATE TABLE sessions (token_hash TEXT PRIMARY KEY,user_id INTEGER,csrf_token TEXT,expires_at INTEGER);
                CREATE TABLE products (id TEXT PRIMARY KEY,name TEXT,image TEXT,founder TEXT,collection TEXT,price REAL,description TEXT,published INTEGER,updated_at TEXT);
                INSERT INTO users VALUES (99,'Existing Owner','owner@example.test','unchanged hash','admin','2026-01-01T00:00:00Z');
                INSERT INTO sessions VALUES ('unchanged token hash',99,'unchanged CSRF',4102444800);
                INSERT INTO products VALUES ('123456789abcdef0','Edited before migration','assets/first.png','Victoria Mendez','THE TAILORED EDIT',345.67,'An edited description.',0,'2026-01-02T00:00:00Z');
            """)
        connection.close()
        migrated = server.make_server(port=0, database=legacy, catalog=self.catalog, root=self.root)
        try:
            migrated.initialize_database(self.catalog)
            with migrated.connect() as connection:
                row = connection.execute("SELECT * FROM products").fetchone()
                self.assertEqual(row["name"], "Edited before migration")
                self.assertEqual(row["price"], 345.67)
                self.assertEqual(row["published"], 0)
                self.assertEqual(json.loads(row["images"]), ["assets/first.png"])
                self.assertEqual(row["color_key"], "assets/first.png")
                self.assertEqual(json.loads(row["color_variants"]), [])
                self.assertEqual(row["legacy_key"], "The Existing Suit:assets/first.png")
                self.assertIsNone(row["stock"])
                self.assertEqual(row["created_at"], "2026-01-02T00:00:00Z")
                for field in ("material", "fabric_weight", "origin", "fit"):
                    self.assertEqual(row[field], "")
                self.assertEqual(connection.execute("SELECT password_hash FROM users WHERE id=99").fetchone()[0], "unchanged hash")
                self.assertEqual(connection.execute("SELECT csrf_token FROM sessions WHERE user_id=99").fetchone()[0], "unchanged CSRF")
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM products").fetchone()[0], 1)
        finally:
            migrated.server_close()

    def test_new_product_color_key_stays_empty_after_restart(self):
        product = self.create()
        self.app.initialize_database(self.catalog)
        items = self.admin.request("GET", "/api/admin/products")[1]["products"]
        self.assertEqual(next(item for item in items if item["id"] == product["id"])["color_key"], "")


if __name__ == "__main__":
    unittest.main()
