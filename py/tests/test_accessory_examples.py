"""Approved example setup must be repeatable and preserve edited shop data."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

import json
from pathlib import Path
import runpy
import unittest

import test_image_hotspots_server as hotspot_tests


class AccessoryExampleSetupTests(unittest.TestCase):
    setUpClass = hotspot_tests.ImageHotspotTests.__dict__["setUpClass"]
    setUp = hotspot_tests.ImageHotspotTests.setUp
    tearDown = hotspot_tests.ImageHotspotTests.tearDown

    def test_repeat_setup_preserves_prices_and_marker_positions(self):
        code = runpy.run_path(str(ROOT / "py/tools/add-accessory-examples.py"))
        apply = code["apply"]
        scope = apply.__globals__
        scope["ROOT"] = self.root
        scope["PHOTO"] = "assets/first.png"
        scope["OUTFIT"] = hotspot_tests.ImageHotspotTests.source_id
        scope["MARKERS"] = [{**marker, "image": "assets/first.png", "product_id": hotspot_tests.ImageHotspotTests.source_id if marker["product_id"] == code["OUTFIT"] else marker["product_id"]}
                            for marker in code["MARKERS"]]
        result = apply(self.database)
        self.assertEqual(len(result["created"]), 3)
        self.assertEqual(len(result["markersAdded"]), 4)
        self.assertTrue((self.root / result["backup"]).is_file())
        bag_id = scope["EXAMPLES"][0]["id"]
        with self.app.connect() as db:
            db.execute("UPDATE products SET price=67 WHERE id=?", (bag_id,))
            points = json.loads(db.execute("SELECT image_hotspots FROM products WHERE id=?", (scope["OUTFIT"],)).fetchone()[0])
            points[0]["x"] = .42
            db.execute("UPDATE products SET image_hotspots=? WHERE id=?", (json.dumps(points), scope["OUTFIT"]))
        repeated = apply(self.database)
        self.assertEqual(repeated["created"], [])
        self.assertEqual(repeated["markersAdded"], [])
        with self.app.connect() as db:
            self.assertEqual(db.execute("SELECT price,color_key FROM products WHERE id=?", (bag_id,)).fetchone()[0], 67)
            self.assertEqual(db.execute("SELECT color_key FROM products WHERE id=?", (bag_id,)).fetchone()[0], bag_id)
            saved = json.loads(db.execute("SELECT image_hotspots FROM products WHERE id=?", (scope["OUTFIT"],)).fetchone()[0])
            self.assertEqual(saved[0]["x"], .42)
