"""Exercise photo-marker persistence, live catalog prices and publication boundaries."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

import json
import unittest

import test_catalog_server as catalog_tests
from test_auth_server import Client


class ImageHotspotTests(unittest.TestCase):
    setUpClass = catalog_tests.CatalogServerTests.__dict__["setUpClass"]
    setUp = catalog_tests.CatalogServerTests.setUp
    tearDown = catalog_tests.CatalogServerTests.tearDown
    product_payload = catalog_tests.CatalogServerTests.product_payload
    create = catalog_tests.CatalogServerTests.create
    path = catalog_tests.CatalogServerTests.path

    source_id = "123456789abcdef0"

    def marker(self, product, **changes):
        return {"image": "assets/first.png", "x": .27, "y": .68,
                "product_id": product["id"], "label": "Handbag", **changes}

    def save_markers(self, markers, **changes):
        return self.admin.request("PATCH", "/api/admin/products/" + self.source_id,
                                  {"image_hotspots": markers, **changes})

    def public_source(self, detail=False):
        if detail:
            return self.public.request("GET", "/api/catalog/" + self.source_id)[1]["product"]
        return next(product for product in self.public.request("GET", "/api/catalog")[1]["products"]
                    if product["id"] == self.source_id)

    def test_accessory_footwear_sizes_are_editable(self):
        shoes = self.create(name="The Court Shoes", sizes=["36", "37", "38", "39", "40", "41", "42"])
        self.assertEqual(shoes["sizes"], ["36", "37", "38", "39", "40", "41", "42"])
        status, response, _ = self.admin.request("PATCH", "/api/admin/products/" + shoes["id"], {"sizes": ["38", "39"], "price": 59})
        self.assertEqual(status, 200, response)
        self.assertEqual(response["product"]["sizes"], ["38", "39"])
        self.assertEqual(self.save_markers([self.marker(response["product"])])[0], 200)
        self.assertEqual(self.public_source(True)["image_hotspots"][0]["product"]["price"], 59)

    def test_saved_markers_enrich_with_current_product_and_price(self):
        target = self.create(name="The Mini Handbag", price=49.95)
        marker = self.marker(target)
        status, response, _ = self.save_markers([marker])
        self.assertEqual(status, 200, response)
        self.assertEqual(response["product"]["image_hotspots"], [marker])
        for detail in (False, True):
            point = self.public_source(detail)["image_hotspots"][0]
            self.assertEqual({key: point[key] for key in marker}, marker)
            self.assertEqual(point["product"], {key: target[key] for key in
                             ("id", "name", "price", "image", "base_color", "color_hex")})
            self.assertNotIn("sku", point["product"])
        self.assertEqual(self.admin.request("PATCH", self.path(target), {"price": 39.95, "name": "The Updated Mini Handbag"})[0], 200)
        for detail in (False, True):
            point = self.public_source(detail)["image_hotspots"][0]
            self.assertEqual((point["product"]["price"], point["product"]["name"]),
                             (39.95, "The Updated Mini Handbag"))
        # Admin editing receives stable references, not stale copied catalog data.
        source = next(product for product in self.admin.request("GET", "/api/admin/products")[1]["products"]
                      if product["id"] == self.source_id)
        self.assertEqual(source["image_hotspots"], [marker])

    def test_draft_unpublished_deleted_targets_never_leak_publicly(self):
        target = self.create(name="Private draft scarf", price=327.19, published=False)
        marker = self.marker(target, label="Private label for unpublished scarf")
        self.assertEqual(self.save_markers([marker])[0], 200)
        for detail in (False, True):
            source = self.public_source(detail)
            self.assertEqual(source["image_hotspots"], [])
            self.assertNotIn("Private", json.dumps(source))
            self.assertNotIn(target["id"], json.dumps(source))
        self.assertEqual(self.admin.request("PATCH", self.path(target), {"published": True})[0], 200)
        self.assertEqual(len(self.public_source()["image_hotspots"]), 1)
        self.assertEqual(self.admin.request("PATCH", self.path(target), {"published": False})[0], 200)
        self.assertEqual(self.public_source(True)["image_hotspots"], [])
        self.assertEqual(self.admin.request("PATCH", self.path(target), {"published": True})[0], 200)
        self.assertEqual(self.admin.request("DELETE", self.path(target), {})[0], 200)
        for detail in (False, True):
            self.assertEqual(self.public_source(detail)["image_hotspots"], [])
        self.assertEqual(self.admin.request("POST", self.path(target) + "/restore", {})[0], 200)
        self.assertEqual(self.public_source()["image_hotspots"], [])

    def test_invalid_marker_data_is_rejected_atomically(self):
        target = self.create()
        good = self.marker(target)
        self.assertEqual(self.save_markers([good])[0], 200)
        for invalid in (
            None, {}, "markers", [None], [True], [dict(good, x=True)], [dict(good, y=False)],
            [dict(good, x=-.01)], [dict(good, y=1.000001)], [dict(good, x="0.5")],
            [dict(good, x=float("nan"))], [dict(good, y=float("inf"))],
            [dict(good, image="https://other.test/a.png")],
            [dict(good, image="assets/../server.py")], [dict(good, image="assets/missing.png")],
            [dict(good, image=None)], [dict(good, product_id="unknown-product")],
            [dict(good, product_id=False)], [dict(good, product_id="../other")],
            [dict(good, label="x" * 81)], [dict(good, label=False)],
            [dict(good, price=1.00)], [{key: value for key, value in good.items() if key != "x"}],
            [good] * 25,
        ):
            with self.subTest(invalid=invalid):
                status, response, _ = self.save_markers(invalid, name="Should not save")
                self.assertEqual(status, 400, response)
                saved = self.public_source()
                self.assertEqual(saved["name"], "The Existing Suit")
                self.assertEqual(len(saved["image_hotspots"]), 1)
        self.assertEqual(self.admin.request("DELETE", self.path(target), {})[0], 200)
        self.assertEqual(self.save_markers([good])[0], 400)

    def test_coordinates_labels_and_clear_are_canonical_and_persistent(self):
        target = self.create()
        raw = self.marker(target, x=.123456789, y=1, label="  Shoes  ")
        status, response, _ = self.save_markers([raw])
        self.assertEqual(status, 200, response)
        marker = response["product"]["image_hotspots"][0]
        self.assertEqual((marker["x"], marker["y"], marker["label"]), (.123457, 1.0, "Shoes"))
        self.app.initialize_database(self.catalog)
        self.assertEqual(self.public_source(True)["image_hotspots"][0]["x"], .123457)
        self.assertEqual(self.save_markers([])[0], 200)
        self.assertEqual(self.public_source()["image_hotspots"], [])

    def test_marker_capacity_applies_per_photo_and_across_the_gallery(self):
        target = self.create(name="The Multi-Photo Linked Item")
        photos = ["assets/first.png", "assets/second.png"]
        markers = [self.marker(target, image=photo, label=f"Photo {index + 1} item {point + 1}")
                   for index, photo in enumerate(photos) for point in range(24)]
        status, response, _ = self.save_markers(markers)
        self.assertEqual(status, 200, response)
        self.assertEqual(response["product"]["image_hotspots"], markers)
        self.assertEqual(len(self.public_source(True)["image_hotspots"]), 48)
        # One full photograph must not prevent labels on another, while a 25th
        # marker on that same photograph still rejects the entire edit.
        status, response, _ = self.save_markers([*markers, self.marker(target)], name="Should not save")
        self.assertEqual(status, 400, response)
        self.assertIn("one photograph", response["error"])
        self.assertEqual(self.public_source()["name"], "The Existing Suit")
        self.assertEqual(len(self.public_source()["image_hotspots"]), 48)
        for index in range(3, 13):
            path = self.root / "assets" / f"capacity-{index}.png"
            path.write_bytes((self.root / "assets/first.png").read_bytes())
            photos.append(f"assets/capacity-{index}.png")
        maximum = [self.marker(target, image=photo) for photo in photos for _ in range(24)]
        self.assertEqual(len(maximum), 288)
        self.assertEqual(self.save_markers(maximum)[0], 200)
        status, response, _ = self.save_markers([*maximum, self.marker(target, image="assets/third.png")])
        self.assertEqual(status, 400, response)
        self.assertIn("288", response["error"])
        self.assertEqual(len(self.public_source(True)["image_hotspots"]), 288)

    def test_new_products_and_duplicates_keep_marker_references(self):
        target = self.create(name="The Linked Scarf")
        raw = self.marker(target)
        raw.pop("label")
        source = self.create(name="The New Styled Look", image_hotspots=[raw])
        point = source["image_hotspots"][0]
        self.assertEqual(point["label"], "")
        self.assertEqual(point["product_id"], target["id"])
        status, duplicate, _ = self.admin.request("POST", self.path(source) + "/duplicate", {})
        self.assertEqual(status, 201, duplicate)
        self.assertEqual(duplicate["product"]["image_hotspots"], source["image_hotspots"])
        self.assertFalse(duplicate["product"]["published"])
        with self.app.connect() as connection:
            stored = json.loads(connection.execute("SELECT image_hotspots FROM products WHERE id=?", (source["id"],)).fetchone()[0])
        self.assertEqual(stored, source["image_hotspots"])

    def test_markers_require_product_edit_authorization_and_csrf(self):
        target = self.create()
        data = {"image_hotspots": [self.marker(target)]}
        path = "/api/admin/products/" + self.source_id
        self.assertEqual(self.public.request("PATCH", path, data)[0], 401)
        customer = Client(self.app)
        self.assertEqual(customer.register()[0], 201)
        self.assertEqual(customer.request("PATCH", path, data)[0], 403)
        self.assertEqual(self.admin.request("PATCH", path, data, token=False)[0], 403)
        self.assertEqual(self.public_source()["image_hotspots"], [])

    def test_markers_are_empty_for_existing_products_and_seeded_when_declared(self):
        self.assertEqual(self.public_source()["image_hotspots"], [])
        source = json.loads(self.catalog.read_text(encoding="utf-8"))
        seed = {**source["products"][0], "id": "new-seeded-look", "name": "New Seeded Look",
                "image_hotspots": [{"image": "assets/first.png", "x": .5, "y": .6,
                                    "product_id": self.source_id, "label": "Suit"}]}
        source["products"].append(seed)
        self.catalog.write_text(json.dumps(source), encoding="utf-8")
        self.app.initialize_database(self.catalog)
        result = self.public.request("GET", "/api/catalog/new-seeded-look")[1]["product"]
        self.assertEqual(result["image_hotspots"][0]["product"]["id"], self.source_id)


if __name__ == "__main__":
    unittest.main()
