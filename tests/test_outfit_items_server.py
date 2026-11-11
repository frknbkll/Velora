"""Outfit grouping and standalone item photos retain catalog identity and privacy."""
import json
import unittest

import test_catalog_server as catalog_tests
from test_auth_server import Client


class OutfitItemTests(unittest.TestCase):
    setUpClass = catalog_tests.CatalogServerTests.__dict__["setUpClass"]
    setUp = catalog_tests.CatalogServerTests.setUp
    tearDown = catalog_tests.CatalogServerTests.tearDown
    product_payload = catalog_tests.CatalogServerTests.product_payload
    create = catalog_tests.CatalogServerTests.create
    path = catalog_tests.CatalogServerTests.path

    source_id = "123456789abcdef0"

    def public_product(self, product_id):
        status, payload, _ = self.public.request("GET", "/api/catalog/" + product_id)
        self.assertEqual(status, 200, payload)
        return payload["product"]

    def test_existing_defaults_and_individual_item_metadata(self):
        parent_before = self.public_product(self.source_id)
        self.assertEqual((parent_before["parent_product_id"], parent_before["item_image"]), ("", ""))
        child = self.create(name="The Separate Bag", parent_product_id=self.source_id, item_image="assets/second.png")
        self.assertEqual(child["parent_product_id"], self.source_id)
        self.assertEqual(child["item_image"], "assets/second.png")
        visible = self.public_product(child["id"])
        self.assertEqual(visible["parent_look"], {key: parent_before[key] for key in ("id", "name", "image")})
        self.assertEqual(visible["price"], child["price"])
        self.assertEqual(visible["stock"], child["stock"])
        self.assertEqual(self.public_product(self.source_id), parent_before)
        catalog = self.public.request("GET", "/api/catalog")[1]["products"]
        self.assertIn(child["id"], {product["id"] for product in catalog})
        self.assertEqual(next(product for product in catalog if product["id"] == child["id"])["parent_look"], visible["parent_look"])

    def test_parent_reference_validation_is_atomic(self):
        for parent in (None, False, [], {}, "../parent", "https://other.test", "x" * 65, " ", "missing-parent"):
            with self.subTest(parent=parent):
                status, response, _ = self.admin.request("PATCH", "/api/admin/products/" + self.source_id,
                                                      {"parent_product_id": parent, "name": "Must not change"})
                self.assertEqual(status, 400, response)
                self.assertEqual(self.public_product(self.source_id)["name"], "The Existing Suit")
        deleted = self.create()
        self.assertEqual(self.admin.request("DELETE", self.path(deleted), {})[0], 200)
        self.assertEqual(self.admin.request("POST", "/api/admin/products", self.product_payload(parent_product_id=deleted["id"]))[0], 400)

    def test_self_nested_and_cyclic_grouping_are_rejected(self):
        child = self.create(parent_product_id=self.source_id)
        other = self.create(name="Another Outfit")
        self.assertEqual(self.admin.request("PATCH", self.path(child), {"parent_product_id": child["id"]})[0], 400)
        self.assertEqual(self.admin.request("POST", "/api/admin/products", self.product_payload(parent_product_id=child["id"]))[0], 400)
        self.assertEqual(self.admin.request("PATCH", "/api/admin/products/" + self.source_id, {"parent_product_id": child["id"]})[0], 400)
        self.assertEqual(self.admin.request("PATCH", "/api/admin/products/" + self.source_id, {"parent_product_id": other["id"]})[0], 400)
        self.assertEqual(self.admin.request("PATCH", self.path(child), {"parent_product_id": other["id"]})[0], 200)
        self.assertEqual(self.public_product(child["id"])["parent_look"]["id"], other["id"])
        self.assertEqual(self.admin.request("PATCH", self.path(child), {"parent_product_id": ""})[0], 200)
        self.assertNotIn("parent_look", self.public_product(child["id"]))

    def test_standalone_photo_must_exist_and_remain_in_gallery(self):
        for image in (None, True, [], "https://other.test/item.png", "assets/../server.py", "assets/missing.png", "assets/third.png"):
            with self.subTest(image=image):
                status, response, _ = self.admin.request("POST", "/api/admin/products", self.product_payload(item_image=image))
                self.assertEqual(status, 400, response)
        product = self.create(item_image="assets/second.png")
        self.assertEqual(self.admin.request("PATCH", self.path(product), {"images": ["assets/first.png"]})[0], 400)
        self.assertEqual(self.public_product(product["id"])["item_image"], "assets/second.png")
        self.assertEqual(self.admin.request("PATCH", self.path(product), {"images": ["assets/first.png"], "item_image": ""})[0], 200)
        self.assertEqual(self.public_product(product["id"])["item_image"], "")

    def test_unpublished_and_deleted_parents_are_not_exposed(self):
        private = self.create(name="Private Outfit Name", published=False)
        child = self.create(name="Public Individual Bag", parent_product_id=private["id"])
        for detail in (False, True):
            product = self.public_product(child["id"]) if detail else next(p for p in self.public.request("GET", "/api/catalog")[1]["products"] if p["id"] == child["id"])
            self.assertNotIn("parent_look", product)
            self.assertNotIn("Private Outfit Name", json.dumps(product))
        self.assertEqual(self.admin.request("PATCH", self.path(private), {"published": True})[0], 200)
        self.assertEqual(self.public_product(child["id"])["parent_look"]["name"], "Private Outfit Name")
        self.assertEqual(self.admin.request("DELETE", self.path(private), {})[0], 200)
        self.assertNotIn("parent_look", self.public_product(child["id"]))
        # An admin form reasserting the unchanged link can still edit price after its parent is trashed.
        self.assertEqual(self.admin.request("PATCH", self.path(child), {"parent_product_id": private["id"], "price": 57})[0], 200)
        self.assertEqual(self.public_product(child["id"])["price"], 57)

    def test_marker_product_contains_current_standalone_photo_only_when_present(self):
        child = self.create(parent_product_id=self.source_id, item_image="assets/second.png")
        point = {"image": "assets/first.png", "x": .3, "y": .6, "product_id": child["id"], "label": "Bag"}
        self.assertEqual(self.admin.request("PATCH", "/api/admin/products/" + self.source_id, {"image_hotspots": [point]})[0], 200)
        for product in (self.public_product(self.source_id), self.public.request("GET", "/api/catalog")[1]["products"][0]):
            self.assertEqual(product["image_hotspots"][0]["product"]["item_image"], "assets/second.png")
        self.assertEqual(self.admin.request("PATCH", self.path(child), {"item_image": "assets/first.png", "price": 88})[0], 200)
        linked = self.public_product(self.source_id)["image_hotspots"][0]["product"]
        self.assertEqual((linked["item_image"], linked["price"]), ("assets/first.png", 88))
        self.assertEqual(self.admin.request("PATCH", self.path(child), {"item_image": ""})[0], 200)
        self.assertNotIn("item_image", self.public_product(self.source_id)["image_hotspots"][0]["product"])

    def test_seed_duplicate_and_restart_preserve_item_metadata(self):
        child = self.create(parent_product_id=self.source_id, item_image="assets/second.png")
        status, response, _ = self.admin.request("POST", self.path(child) + "/duplicate", {})
        self.assertEqual(status, 201, response)
        self.assertEqual(response["product"]["parent_product_id"], self.source_id)
        self.assertEqual(response["product"]["item_image"], "assets/second.png")
        seed = json.loads(self.catalog.read_text(encoding="utf-8"))
        seed["products"].append({**seed["products"][0], "id": "seeded-item", "name": "Seeded Item", "images": ["assets/first.png", "assets/third.png"],
                                 "parent_product_id": self.source_id, "item_image": "assets/third.png"})
        self.catalog.write_text(json.dumps(seed), encoding="utf-8")
        self.app.initialize_database(self.catalog)
        self.assertEqual(self.public_product(child["id"])["item_image"], "assets/second.png")
        self.assertEqual(self.public_product("seeded-item")["item_image"], "assets/third.png")
        self.assertEqual(self.public_product("seeded-item")["parent_look"]["id"], self.source_id)

    def test_outfit_metadata_requires_admin_edit_authorization_and_csrf(self):
        changes = {"item_image": "assets/first.png", "parent_product_id": ""}
        path = "/api/admin/products/" + self.source_id
        self.assertEqual(self.public.request("PATCH", path, changes)[0], 401)
        customer = Client(self.app); self.assertEqual(customer.register()[0], 201)
        self.assertEqual(customer.request("PATCH", path, changes)[0], 403)
        self.assertEqual(self.admin.request("PATCH", path, changes, token=False)[0], 403)


if __name__ == "__main__":
    unittest.main()
