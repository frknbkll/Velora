"""A JPEG's filename must never substitute a different product photograph."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

from pathlib import Path
import runpy
import tempfile
import unittest

try:
    from PIL import Image
except ImportError:
    Image = None


@unittest.skipUnless(Image, "Pillow is an optional asset-tool dependency")
class ImageMasterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.assets = Path(self.temp.name) / "assets"
        self.gallery = self.assets / "gallery"
        self.gallery.mkdir(parents=True)
        self.select = runpy.run_path(str(ROOT / "py/tools/prepare-responsive-images.py"))["verified_lossless_master"]
        self.select.__globals__["ASSETS"] = self.assets

    def pair(self, color="brown", size=(120, 180)):
        original = self.gallery / "garment.jpg"
        master = original.with_suffix(".png")
        photo = Image.new("RGB", (120, 180), "brown")
        photo.save(original, quality=92)
        Image.new("RGB", size, color).save(master)
        return original, master

    def test_matching_pixels_and_geometry_use_lossless_master(self):
        original, master = self.pair()
        self.assertEqual(self.select(original), master)

    def test_same_name_different_product_or_color_keeps_original(self):
        original, _ = self.pair(color="navy")
        self.assertEqual(self.select(original), original)

    def test_different_crop_dimensions_keep_original(self):
        original, _ = self.pair(size=(180, 120))
        self.assertEqual(self.select(original), original)

    def test_missing_or_corrupt_master_keeps_original(self):
        original, master = self.pair()
        master.write_bytes(b"not a photograph")
        self.assertEqual(self.select(original), original)
        master.unlink()
        self.assertEqual(self.select(original), original)


if __name__ == "__main__":
    unittest.main()
