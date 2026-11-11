"""Protect owner edits and photo repairs when applying reviewed object labels."""
import json
from contextlib import closing
from pathlib import Path
import runpy
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
run = runpy.run_path(str(ROOT / "tools/apply-object-labels.py"))["run"]


class ObjectLabelSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "assets").mkdir()
        (self.root / "assets/cover.png").write_bytes(b"fixture")
        (self.root / "assets/item.png").write_bytes(b"fixture")
        (self.root / "output").mkdir()
        (self.root / ".velora").mkdir()
        self.database = self.root / ".velora/velora.sqlite3"
        self.plan = self.root / "output/object-label-photo-plan.json"
        self.catalog = self.root / "product-catalog.json"
        self.owner_marker = self.marker("assets/cover.png", "Owner's existing label")
        product = {"id": "item", "name": "Owner's item", "image": "assets/cover.png", "images": ["assets/cover.png", "assets/item.png"],
                   "item_image": "assets/item.png", "image_hotspots": [self.owner_marker], "published": True, "deleted_at": None, "price": 83}
        self.catalog.write_text(json.dumps({"products": [{**product, "price": 77}]}), encoding="utf-8")
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("CREATE TABLE products(id TEXT PRIMARY KEY,name TEXT,image TEXT,images TEXT,item_image TEXT,image_hotspots TEXT,published INTEGER,deleted_at TEXT,price REAL,updated_at TEXT)")
            db.execute("CREATE TABLE product_activity(actor_id INTEGER,actor_name TEXT,action TEXT,product_id TEXT,product_name TEXT,created_at TEXT)")
            db.execute("INSERT INTO products VALUES(?,?,?,?,?,?,?,?,?,?)", (product["id"], product["name"], product["image"], json.dumps(product["images"]),
                       product["item_image"], json.dumps(product["image_hotspots"]), 1, None, 83, "before"))
        self.write_plan([{"id": "item", "photo": "assets/item.png", "points": [self.marker("assets/item.png", "Bag")]}])

    def marker(self, photo, label):
        return {"image": photo, "x": .5, "y": .6, "product_id": "item", "label": label}

    def write_plan(self, products, missing=None):
        self.plan.write_text(json.dumps({"reviewed": True, "products": products, "missing_assets": missing or []}), encoding="utf-8")

    def saved(self):
        with closing(sqlite3.connect(self.database)) as db, db:
            db.row_factory = sqlite3.Row
            return dict(db.execute("SELECT * FROM products WHERE id='item'").fetchone())

    def test_apply_preserves_custom_labels_prices_and_is_idempotent(self):
        before = self.saved()
        preview = run(root=self.root)
        self.assertEqual(preview["addedLabels"], 1)
        self.assertEqual(self.saved(), before)
        report = run(root=self.root, apply=True)
        self.assertTrue((self.root / report["backup"]).is_file())
        labels = json.loads(self.saved()["image_hotspots"])
        self.assertEqual(labels, [self.owner_marker, self.marker("assets/item.png", "Bag")])
        self.assertEqual(self.saved()["price"], 83)
        seed = json.loads(self.catalog.read_text())["products"][0]
        self.assertEqual(seed["price"], 77)
        self.assertEqual(seed["image_hotspots"], labels)
        second = run(root=self.root, apply=True)
        self.assertEqual((second["changedProducts"], second["addedLabels"]), (0, 0))

    def test_owner_label_added_after_review_is_retained(self):
        custom = self.marker("assets/item.png", "Owner's new placement")
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("UPDATE products SET image_hotspots=?", (json.dumps([self.owner_marker, custom]),))
        report = run(root=self.root, apply=True)
        self.assertEqual(report["changedProducts"], 0)
        self.assertEqual(json.loads(self.saved()["image_hotspots"])[1], custom)

    def test_invalid_target_does_not_partially_save_valid_photo(self):
        bad = {**self.marker("assets/cover.png", "Bad target"), "product_id": "missing"}
        self.write_plan([{"id": "item", "photo": "assets/item.png", "points": [self.marker("assets/item.png", "Bag")]},
                         {"id": "item", "photo": "assets/cover.png", "points": [bad]}])
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("UPDATE products SET image_hotspots='[]'")
        before = self.saved()
        with self.assertRaises(ValueError):
            run(root=self.root, apply=True)
        self.assertEqual(self.saved(), before)

    def test_missing_gallery_photo_is_removed_without_removing_working_cover(self):
        missing = "assets/missing.png"
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("UPDATE products SET images=?,item_image=?", (json.dumps(["assets/cover.png", missing]), missing))
        self.write_plan([], [{"id": "item", "photo": missing}])
        report = run(root=self.root, apply=True)
        saved = self.saved()
        self.assertEqual(json.loads(saved["images"]), ["assets/cover.png"])
        self.assertEqual(saved["image"], "assets/cover.png")
        self.assertEqual(saved["item_image"], "")
        self.assertEqual(len(report["repairedMissingPhotos"]), 1)

    def test_reviewed_correction_is_guarded_and_idempotent(self):
        copied = self.marker("assets/cover.png", "Wrong copied label")
        before = [self.owner_marker, copied]
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("UPDATE products SET image_hotspots=?", (json.dumps(before),))
        plan = {"reviewed": True, "products": [], "corrections": [
            {"id": "item", "photo": "assets/cover.png", "before": before, "after": [self.owner_marker], "reason": "Remove a copied label"}]}
        self.plan.write_text(json.dumps(plan), encoding="utf-8")
        report = run(root=self.root, apply=True)
        self.assertEqual(report["removedCopiedLabels"], 1)
        self.assertEqual(json.loads(self.saved()["image_hotspots"]), [self.owner_marker])
        self.assertEqual(run(root=self.root, apply=True)["changedProducts"], 0)
        newer = self.marker("assets/cover.png", "New owner placement")
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("UPDATE products SET image_hotspots=?", (json.dumps([self.owner_marker, newer]),))
        with self.assertRaises(ValueError):
            run(root=self.root, apply=True)
        self.assertEqual(json.loads(self.saved()["image_hotspots"]), [self.owner_marker, newer])


if __name__ == "__main__":
    unittest.main()
