"""Add the approved, editable accessory examples and markers without replacing shop data.

Preview: python py/tools/add-accessory-examples.py
Apply after restarting the updated server: python py/tools/add-accessory-examples.py --apply
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

PHOTO = "assets/gallery/new-arrivals/espresso-tailored-suit.jpg"
OUTFIT = "552959ebc1ce3e02"
EXAMPLES = [
    {"id": "velora-example-espresso-bag", "name": "The Espresso Top-Handle Bag", "price": 49.0,
     "base_color": "Espresso", "color_hex": "#4e342e", "sizes": ["One size"],
     "description": "An espresso top-handle bag with a structured shape and gold-tone clasp, shown with the Espresso Tailored Suit. This editable accessory example uses the full styling photograph; the bag is the linked item. Material, measurements and availability are not confirmed."},
    {"id": "velora-example-nude-court-shoes", "name": "The Nude Pointed Court Shoes", "price": 59.0,
     "base_color": "Nude", "color_hex": "#d1ac94", "sizes": ["36", "37", "38", "39", "40", "41", "42"],
     "description": "Nude pointed-toe court shoes styled with the Espresso Tailored Suit. This editable accessory example uses the full styling photograph; the shoes are the linked item. EU sizes and price are illustrative. Material, fit and availability require confirmation."},
    {"id": "velora-example-taupe-scarf", "name": "The Taupe Draped Scarf", "price": 19.0,
     "base_color": "Taupe", "color_hex": "#9e8173", "sizes": ["One size"],
     "description": "A taupe scarf with a softly wrapped, draped finish, styled with the Espresso Tailored Suit. This editable accessory example uses the full styling photograph; the scarf is the linked item. Fabric, dimensions and availability are not confirmed."},
]
MARKERS = [
    {"image": PHOTO, "x": .288, "y": .634, "product_id": EXAMPLES[0]["id"], "label": "Bag"},
    {"image": PHOTO, "x": .233, "y": .966, "product_id": EXAMPLES[1]["id"], "label": "Shoes"},
    {"image": PHOTO, "x": .516, "y": .151, "product_id": EXAMPLES[2]["id"], "label": "Scarf"},
    {"image": PHOTO, "x": .467, "y": .451, "product_id": OUTFIT, "label": "Tailored suit"},
]


def product_values(item, stamp):
    return {**item, "image": PHOTO, "images": json.dumps([PHOTO]), "founder": "Velora Studio",
            "collection": "THE POLISHED EDIT", "published": 1, "updated_at": stamp, "created_at": stamp,
            "color_key": item["id"], "legacy_key": "", "color_variants": "[]", "stock": None,
            "sizes": json.dumps(item["sizes"]), "sku": "VL-EXAMPLE-" + item["id"].removeprefix("velora-example-").upper(),
            "material": "", "fabric_weight": "", "origin": "", "fit": "",
            "image_hotspots": json.dumps(MARKERS)}


def apply(database):
    if not database.is_file():
        raise SystemExit("Start the updated Velora server before applying accessory examples.")
    if not (ROOT / PHOTO).is_file():
        raise SystemExit("The styling photograph is missing.")
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    created, linked, adjusted = [], [], []
    with closing(sqlite3.connect(database)) as db, db:
        if "image_hotspots" not in {row[1] for row in db.execute("PRAGMA table_info(products)")}:
            raise SystemExit("Restart the updated Velora server to enable photo markers, then run this command again.")
        if not db.execute("SELECT 1 FROM products WHERE id=? AND published=1 AND deleted_at IS NULL", (OUTFIT,)).fetchone():
            raise SystemExit("The source Espresso Tailored Suit must be published first.")
        backup_directory = database.parent / "backups"
        backup_directory.mkdir(exist_ok=True)
        backup = backup_directory / ("before-photo-shopping-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".sqlite3")
        with closing(sqlite3.connect(backup)) as destination:
            db.backup(destination)
        db.execute("BEGIN IMMEDIATE")
        for item in EXAMPLES:
            existing = db.execute("SELECT color_key,name FROM products WHERE id=?", (item["id"],)).fetchone()
            if existing:
                # Reusing a styling photo must not give its bag the suit's preset colors.
                if not existing[0]:
                    db.execute("UPDATE products SET color_key=?,updated_at=? WHERE id=?", (item["id"], stamp, item["id"]))
                    db.execute("INSERT INTO product_activity(actor_id,actor_name,action,product_id,product_name,created_at) VALUES(NULL,?,?,?,?,?)",
                               ("Velora setup", "update", item["id"], existing[1], stamp))
                    adjusted.append(item["id"])
                continue
            values = product_values(item, stamp)
            db.execute(f"INSERT INTO products ({','.join(values)}) VALUES ({','.join('?' for _ in values)})", tuple(values.values()))
            db.execute("INSERT INTO product_activity(actor_id,actor_name,action,product_id,product_name,created_at) VALUES(NULL,?,?,?,?,?)",
                       ("Velora setup", "create", item["id"], item["name"], stamp))
            created.append(item["id"])
        # Append only missing references; keep any placements and prices the owner edited.
        row = db.execute("SELECT name,image_hotspots FROM products WHERE id=?", (OUTFIT,)).fetchone()
        points = json.loads(row[1])
        for marker in MARKERS:
            if not any(point.get("image") == PHOTO and point.get("product_id") == marker["product_id"] for point in points):
                if len(points) >= 24:
                    raise SystemExit("The styling photo already has the maximum number of markers. No changes applied.")
                points.append(marker); linked.append(marker["product_id"])
        if linked:
            db.execute("UPDATE products SET image_hotspots=?,updated_at=? WHERE id=?", (json.dumps(points), stamp, OUTFIT))
            db.execute("INSERT INTO product_activity(actor_id,actor_name,action,product_id,product_name,created_at) VALUES(NULL,?,?,?,?,?)",
                       ("Velora setup", "update", OUTFIT, row[0], stamp))
    return {"created": created, "markersAdded": linked, "colorSourcesAdjusted": adjusted, "backup": str(backup.relative_to(ROOT))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps({"examples": [{"name": p["name"], "priceEUR": p["price"]} for p in EXAMPLES],
                          "stylingProduct": OUTFIT, "markers": len(MARKERS), "apply": "Run with --apply after restarting the updated server."}, indent=2))
        return
    result = apply(ROOT / ".velora/velora.sqlite3")
    catalog_path = ROOT / "json/catalog/product-catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    products = catalog["products"]
    for item in EXAMPLES:
        if not any(product["id"] == item["id"] for product in products):
            products.append({**item, "image": PHOTO, "images": [PHOTO], "founder": "Velora Studio", "collection": "THE POLISHED EDIT",
                             "published": True, "image_hotspots": MARKERS, "color_key": item["id"]})
        example = next(product for product in products if product["id"] == item["id"])
        if not example.get("color_key"):
            example["color_key"] = item["id"]
    source = next((product for product in products if product["id"] == OUTFIT), None)
    if source:
        points = source.setdefault("image_hotspots", [])
        for marker in MARKERS:
            if not any(point.get("image") == PHOTO and point.get("product_id") == marker["product_id"] for point in points):
                points.append(marker)
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
