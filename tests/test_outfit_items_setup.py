"""Grouped outfit setup is atomic, review-gated and preserves later shop edits."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest import mock

import test_catalog_server as catalog_tests

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("apply_outfit_items_tested", ROOT / "tools/apply-outfit-items.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class OutfitItemSetupTests(unittest.TestCase):
    setUpClass = catalog_tests.CatalogServerTests.__dict__["setUpClass"]
    tearDown = catalog_tests.CatalogServerTests.tearDown
    source_id = "123456789abcdef0"

    def setUp(self):
        catalog_tests.CatalogServerTests.setUp(self)
        self.output = self.root / "output"
        self.output.mkdir()
        (self.root / "assets/generated-items").mkdir()
        for name, width in [("suit", 5), ("bag", 6), ("other-suit", 7)]:
            (self.root / f"assets/generated-items/{name}.png").write_bytes(catalog_tests.png(width, 8))
        self.primary = self.item(self.source_id, "assets/generated-items/suit.png", primary=True)
        self.bag = self.item("piece-fixture-bag", "assets/generated-items/bag.png")
        self.parent = {"product_id": self.source_id, "name": "The Existing Suit", "image": "assets/first.png", "items": [self.primary, self.bag], "note": ""}
        self.manifest = {"parents": [self.parent], "jobs": [self.job(self.primary), self.job(self.bag)]}
        self.approve_all()
        self.write_manifest()

    def item(self, product_id, asset, primary=False):
        return {"product_id": product_id, "asset": asset, "is_primary": primary,
                "kind": "garment" if primary else "bag", "name": "The Suit" if primary else "The Separate Bag",
                "description": "A tailored matching trouser suit." if primary else "A plain structured top-handle bag.",
                "color": "Brown", "hex": "#50372d", "x": .5 if primary else .3, "y": .45 if primary else .65,
                "visual_key": product_id}

    def job(self, item, parent_id=None):
        return {"id": Path(item["asset"]).stem, "output": item["asset"], "target_product_id": item["product_id"],
                "parent_product_id": parent_id or self.source_id, "is_primary": item["is_primary"]}

    def approve_all(self):
        self.qa = {"images": [{"id": job["id"], "output": job["output"], "status": "approved",
                               "sha256": hashlib.sha256((self.root / job["output"]).read_bytes()).hexdigest()}
                              for job in self.manifest["jobs"]]}
        self.write_qa()

    def write_qa(self):
        (self.output / "outfit-items-image-qa.json").write_text(json.dumps(self.qa), encoding="utf-8")

    def write_manifest(self):
        (self.output / "outfit-items-manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def run_setup(self, **changes):
        return setup.run(root=self.root, database=self.database, **changes)

    def record(self, product_id):
        with self.app.connect() as db:
            row = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
            return dict(row) if row is not None else None

    def clone_product(self, product_id, **changes):
        values = {**self.record(self.source_id), "id": product_id, "sku": "CLONE-" + product_id, **changes}
        with self.app.connect() as db:
            db.execute(f"INSERT INTO products({','.join(values)}) VALUES({','.join('?' for _ in values)})", tuple(values.values()))
        return values

    def test_preview_is_read_only_and_apply_groups_real_item_photos(self):
        before, catalog_before = self.record(self.source_id), self.catalog.read_bytes()
        preview = self.run_setup()
        self.assertFalse(preview["applied"])
        self.assertEqual(preview["counts"]["ready"], 1)
        self.assertEqual(preview["wouldCreate"], 1)
        self.assertEqual(self.record(self.source_id), before)
        self.assertEqual(self.catalog.read_bytes(), catalog_before)
        self.assertFalse((self.output / "applied-outfit-items.json").exists())
        self.assertFalse((self.database.parent / "backups").exists())
        result = self.run_setup(apply=True)
        self.assertTrue(result["applied"])
        self.assertTrue((self.root / result["backup"]).is_file())
        source, bag = self.record(self.source_id), self.record(self.bag["product_id"])
        for field in ("id", "name", "image", "price", "stock", "sizes", "published", "color_variants", "description"):
            self.assertEqual(source[field], before[field], field)
        self.assertEqual(json.loads(source["images"]), ["assets/first.png", self.primary["asset"]])
        self.assertEqual(source["item_image"], self.primary["asset"])
        self.assertEqual(bag["image"], self.bag["asset"])
        self.assertEqual(json.loads(bag["images"]), [self.bag["asset"]])
        self.assertEqual((bag["parent_product_id"], bag["item_image"], bag["price"]), (self.source_id, self.bag["asset"], 49))
        self.assertEqual(json.loads(bag["image_hotspots"]), [])
        seed = json.loads(self.catalog.read_text(encoding="utf-8"))["products"]
        self.assertEqual(next(p for p in seed if p["id"] == self.bag["product_id"])["parent_product_id"], self.source_id)

    def test_pending_or_changed_hash_never_applies_without_all_images(self):
        self.qa["images"] = self.qa["images"][:1]
        self.write_qa()
        result = self.run_setup(apply=True)
        self.assertFalse(result["applied"])
        self.assertEqual(result["counts"]["pending"], 1)
        self.assertIsNone(self.record(self.bag["product_id"]))
        self.assertFalse((self.database.parent / "backups").exists())
        self.approve_all()
        (self.root / self.bag["asset"]).write_bytes(catalog_tests.png(9, 8))
        preview = self.run_setup()
        self.assertEqual(preview["outfits"][0]["reasons"][0]["reason"], "approval_hash_mismatch")
        self.assertFalse(self.run_setup(apply=True)["applied"])

    def test_ready_only_and_shared_items_do_not_duplicate_or_reparent(self):
        other_id = "second-outfit"
        self.clone_product(other_id, image="assets/third.png", images=json.dumps(["assets/third.png"]))
        second_primary = self.item(other_id, "assets/generated-items/other-suit.png", primary=True)
        self.manifest["parents"].append({"product_id": other_id, "name": "Another Suit", "image": "assets/third.png", "items": [second_primary, self.bag]})
        self.manifest["jobs"].append(self.job(second_primary, other_id))
        self.write_manifest()
        result = self.run_setup(apply=True, ready_only=True)
        self.assertEqual((result["counts"]["ready"], result["counts"]["pending"]), (1, 1))
        self.assertEqual(self.record(other_id)["item_image"], "")
        self.approve_all()
        repeated = self.run_setup(apply=True, ready_only=True)
        self.assertEqual((repeated["counts"]["ready"], repeated["counts"]["already_applied"]), (1, 1))
        self.assertEqual(self.record(self.bag["product_id"])["parent_product_id"], self.source_id)
        with self.app.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM products").fetchone()[0], 3)
        self.assertEqual(len(json.loads(self.record(other_id)["image_hotspots"])), 2)

    def test_repeat_preserves_owner_changes_and_recovers_missing_output_journal(self):
        self.run_setup(apply=True)
        with self.app.connect() as db:
            db.execute("UPDATE products SET price=309,item_image=?,images=?,image_hotspots=? WHERE id=?",
                       ("assets/third.png", json.dumps(["assets/first.png", "assets/third.png"]), "[]", self.source_id))
            db.execute("UPDATE products SET price=67,stock=8,description=? WHERE id=?", ("Owner copy", self.bag["product_id"]))
        (self.output / "applied-outfit-items.json").unlink()
        catalog = json.loads(self.catalog.read_text(encoding="utf-8"))
        next(p for p in catalog["products"] if p["id"] == self.source_id)["price"] = 555
        self.catalog.write_text(json.dumps(catalog), encoding="utf-8")
        source_before, bag_before = self.record(self.source_id), self.record(self.bag["product_id"])
        result = self.run_setup(apply=True)
        self.assertEqual(result["counts"]["already_applied"], 1)
        self.assertEqual((result["wouldCreate"], result["wouldUpdate"], result["backup"]), (0, 0, None))
        self.assertEqual(self.record(self.source_id), source_before)
        self.assertEqual(self.record(self.bag["product_id"]), bag_before)
        self.assertTrue((self.output / "applied-outfit-items.json").is_file())
        self.assertEqual(next(p for p in json.loads(self.catalog.read_text(encoding="utf-8"))["products"] if p["id"] == self.source_id)["price"], 555)

    def test_shared_child_uses_visible_outfit_when_first_reference_is_unpublished(self):
        other_id = "visible-outfit"
        self.clone_product(other_id, name="The Public Outfit", image="assets/third.png", images=json.dumps(["assets/third.png"]))
        with self.app.connect() as db:
            db.execute("UPDATE products SET published=0 WHERE id=?", (self.source_id,))
        second_primary = self.item(other_id, "assets/generated-items/other-suit.png", primary=True)
        self.manifest["parents"].append({"product_id": other_id, "name": "The Public Outfit", "image": "assets/third.png", "items": [second_primary, self.bag]})
        self.manifest["jobs"].append(self.job(second_primary, other_id))
        self.manifest["jobs"][1]["used_by"] = [self.source_id, other_id]
        self.write_manifest(); self.approve_all()
        self.run_setup(apply=True)
        bag = self.record(self.bag["product_id"])
        self.assertEqual((bag["published"], bag["parent_product_id"]), (1, other_id))
        self.assertEqual(self.record(self.source_id)["published"], 0)
        status, response, _ = self.public.request("GET", "/api/catalog/" + self.bag["product_id"])
        self.assertEqual(status, 200, response)
        self.assertEqual(response["product"]["parent_look"]["id"], other_id)
        # An owner can still make the shared item private; a repeat must retain that edit.
        with self.app.connect() as db:
            db.execute("UPDATE products SET published=0 WHERE id=?", (self.bag["product_id"],))
        self.run_setup(apply=True)
        self.assertEqual(self.record(self.bag["product_id"])["published"], 0)

    def test_existing_outfit_copy_keeps_custom_gallery_price_stock_and_copy(self):
        existing_id = "velora-example-espresso-bag"
        self.bag["product_id"] = existing_id
        self.manifest["jobs"][1]["target_product_id"] = existing_id
        self.clone_product(existing_id, name="Owner Bag", price=73, stock=9, description="Owner custom details",
                           images=json.dumps(["assets/first.png", "assets/second.png"]),
                           image_hotspots=json.dumps([{"image": "assets/first.png", "product_id": self.source_id, "x": .5, "y": .5, "label": "Old full outfit"},
                                                      {"image": "assets/second.png", "product_id": self.source_id, "x": .4, "y": .4, "label": "Owner marker"}]))
        with self.app.connect() as db:
            db.execute("UPDATE products SET item_image=?,images=? WHERE id=?", ("assets/third.png", json.dumps(["assets/first.png", "assets/third.png"]), self.source_id))
        self.write_manifest()
        self.run_setup(apply=True)
        bag = self.record(existing_id)
        self.assertEqual((bag["name"], bag["price"], bag["stock"], bag["description"]), ("Owner Bag", 73, 9, "Owner custom details"))
        self.assertEqual(json.loads(bag["images"]), [self.bag["asset"], "assets/second.png"])
        self.assertEqual(json.loads(bag["image_hotspots"])[0]["label"], "Owner marker")
        self.assertEqual(self.record(self.source_id)["item_image"], "assets/third.png")

    def test_independent_owner_item_cover_and_unknown_source_markers_are_preserved(self):
        existing_id = self.bag["product_id"]
        self.clone_product(existing_id, image="assets/second.png", images=json.dumps(["assets/second.png", "assets/third.png"]), price=87)
        custom = {"image": "assets/first.png", "product_id": "custom-other-item", "x": .1, "y": .2, "label": "Owner location"}
        other = {"image": "assets/second.png", "product_id": self.source_id, "x": .2, "y": .4, "label": "Another pose"}
        with self.app.connect() as db:
            db.execute("UPDATE products SET image_hotspots=? WHERE id=?", (json.dumps([custom, other]), self.source_id))
        self.run_setup(apply=True)
        self.assertEqual(self.record(existing_id)["image"], "assets/second.png")
        self.assertEqual(self.record(existing_id)["item_image"], "assets/second.png")
        self.assertEqual(self.record(existing_id)["price"], 87)
        saved = json.loads(self.record(self.source_id)["image_hotspots"])
        self.assertIn(custom, saved); self.assertIn(other, saved)

    def test_cover_changes_full_galleries_and_marker_limits_are_skipped(self):
        with self.app.connect() as db:
            db.execute("UPDATE products SET image=? WHERE id=?", ("assets/third.png", self.source_id))
        self.assertEqual(self.run_setup()["outfits"][0]["reason"], "outfit_cover_or_group_changed")
        with self.app.connect() as db:
            db.execute("UPDATE products SET image=?,images=? WHERE id=?", ("assets/first.png", json.dumps(["assets/first.png"] * 12), self.source_id))
        self.assertEqual(self.run_setup()["outfits"][0]["reason"], "outfit_gallery_full")
        points = [{"image": "assets/second.png", "product_id": self.source_id, "x": .1, "y": .2, "label": str(i)} for i in range(24)]
        with self.app.connect() as db:
            db.execute("UPDATE products SET images=?,image_hotspots=? WHERE id=?", (json.dumps(["assets/first.png"]), json.dumps(points), self.source_id))
        self.assertEqual(self.run_setup()["outfits"][0]["reason"], "custom_markers_leave_no_room")
        self.assertFalse(self.run_setup(apply=True)["applied"])
        self.assertIsNone(self.record(self.bag["product_id"]))

    def test_changed_image_during_transaction_rolls_back_products_and_journal(self):
        before = self.record(self.source_id)
        real_digest, calls = setup.digest, 0
        def changed_digest(path):
            nonlocal calls
            calls += 1
            return "0" * 64 if calls >= 5 else real_digest(path)
        with mock.patch.object(setup, "digest", side_effect=changed_digest):
            with self.assertRaisesRegex(ValueError, "changed during setup"):
                self.run_setup(apply=True)
        self.assertEqual(self.record(self.source_id), before)
        self.assertIsNone(self.record(self.bag["product_id"]))
        with self.app.connect() as db:
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (setup.JOURNAL_TABLE,)).fetchone())
        self.assertFalse((self.output / "applied-outfit-items.json").exists())

    def test_committed_database_journal_recovers_from_output_write_failure(self):
        write = setup.atomic_json
        def fail_output(path, value):
            if path.name == "applied-outfit-items.json":
                raise OSError("Fixture disk interruption")
            return write(path, value)
        with mock.patch.object(setup, "atomic_json", side_effect=fail_output):
            with self.assertRaisesRegex(OSError, "disk interruption"):
                self.run_setup(apply=True)
        self.assertIsNotNone(self.record(self.bag["product_id"]))
        with self.app.connect() as db:
            db.execute("UPDATE products SET price=91 WHERE id=?", (self.bag["product_id"],))
        repeated = self.run_setup(apply=True)
        self.assertEqual(repeated["counts"]["already_applied"], 1)
        self.assertEqual(self.record(self.bag["product_id"])["price"], 91)
        self.assertTrue((self.output / "applied-outfit-items.json").is_file())

    def test_manifest_cannot_reuse_an_outfit_as_a_child_or_item_photo(self):
        bad = copy.deepcopy(self.manifest)
        bad["parents"][0]["items"][1]["product_id"] = self.source_id
        bad["jobs"][1]["target_product_id"] = self.source_id
        with self.assertRaisesRegex(ValueError, "outfit record"):
            setup.validate_manifest(self.root, bad)
        bad = copy.deepcopy(self.manifest)
        bad["jobs"][1]["output"] = "assets/first.png"
        with self.assertRaisesRegex(ValueError, "full-outfit"):
            setup.validate_manifest(self.root, bad)
