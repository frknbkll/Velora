"""Add photo-specific labels and apply guarded, visually reviewed corrections.

Defaults to a dry run. --apply backs up the private database, applies product
metadata in one transaction, and synchronizes the corresponding seed fields.
"""
from __future__ import annotations

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
import runpy
import sqlite3

helpers = runpy.run_path(str(Path(__file__).with_name("apply-outfit-items.py")))
asset_path, atomic_json, utc_now = (helpers[key] for key in ("asset_path", "atomic_json", "utc_now"))
TOTAL_LIMIT, PHOTO_LIMIT = 288, 24
EDITABLE = ("image_hotspots", "images", "item_image")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_products(db):
    rows = {}
    for record in db.execute("SELECT id,name,image,images,item_image,image_hotspots,published,deleted_at FROM products"):
        row = dict(record)
        for key in ("images", "image_hotspots"):
            row[key] = json.loads(row[key])
        rows[row["id"]] = row
    return rows


def build_changes(root, plan, rows):
    if plan.get("reviewed") is not True:
        raise ValueError("Review the photo-label plan before applying it.")
    changes, skipped, added, repaired, corrected, removed = {}, [], 0, [], [], 0

    def editable(identifier):
        row = rows.get(identifier)
        if row is None or row.get("deleted_at") or not row.get("published"):
            raise ValueError(f"A planned product is no longer published: {identifier}")
        return changes.setdefault(identifier, {key: json.loads(json.dumps(row.get(key, ""))) for key in EDITABLE})

    for repair in plan.get("missing_assets", []):
        identifier, photo = repair["id"], repair["photo"]
        if asset_path(root, photo).is_file():
            skipped.append({"id": identifier, "photo": photo, "reason": "file_now_exists"})
            continue
        row = rows.get(identifier)
        if row is None or row.get("deleted_at"):
            raise ValueError("A gallery-repair product is missing or trashed.")
        if row["image"] == photo:
            raise ValueError("A missing cover needs a replacement, not removal.")
        if photo not in row["images"] and row.get("item_image") != photo:
            continue
        values = editable(identifier)
        values["images"] = [image for image in values["images"] if image != photo]
        if row["image"] not in values["images"]:
            values["images"].insert(0, row["image"])
        if values["item_image"] == photo:
            values["item_image"] = ""
        repaired.append({"id": identifier, "removed_missing_photo": photo})

    for correction in plan.get("corrections", []):
        identifier, photo = correction["id"], correction["photo"]
        if not asset_path(root, photo).is_file():
            raise ValueError("A correction's reviewed photograph is missing.")
        values = editable(identifier)
        actual = [point for point in values["image_hotspots"] if point["image"] == photo]
        expected, replacement = correction["before"], correction["after"]
        if actual == replacement:
            continue
        if actual != expected:
            raise ValueError(f"Photo labels changed after correction review: {identifier}, {photo}")
        if not isinstance(replacement, list) or not 1 <= len(replacement) <= PHOTO_LIMIT:
            raise ValueError("A corrected photo must retain one to 24 labels.")
        for point in replacement:
            if set(point) != {"image", "x", "y", "product_id", "label"} or point["image"] != photo:
                raise ValueError("A corrected label must use its exact reviewed photograph.")
            if any(isinstance(point[k], bool) or not isinstance(point[k], (float, int)) or not 0 <= point[k] <= 1 for k in ("x", "y")):
                raise ValueError("Corrected labels must remain inside the image.")
            if not isinstance(point["label"], str) or not 1 <= len(point["label"].strip()) <= 80:
                raise ValueError("Use a short corrected object label.")
            target = rows.get(point["product_id"])
            if not target or not target.get("published") or target.get("deleted_at"):
                raise ValueError("Corrected labels must link a published product.")
        values["image_hotspots"] = [point for point in values["image_hotspots"] if point["image"] != photo] + replacement
        if len(values["image_hotspots"]) > TOTAL_LIMIT:
            raise ValueError("The corrected product exceeds its photo-label limit.")
        corrected.append({"id": identifier, "photo": photo, "reason": correction.get("reason", "Reviewed object-label correction")})
        removed += max(0, len(actual) - len(replacement))

    seen = set()
    for entry in plan.get("products", []):
        identifier, photo = entry["id"], entry["photo"]
        if (identifier, photo) in seen:
            raise ValueError("The plan repeats a product photograph.")
        seen.add((identifier, photo))
        if not asset_path(root, photo).is_file():
            raise ValueError(f"A reviewed photograph is missing: {photo}")
        values = editable(identifier)
        if any(point["image"] == photo for point in values["image_hotspots"]):
            skipped.append({"id": identifier, "photo": photo, "reason": "existing_labels_preserved"})
            continue
        points = entry["points"]
        if not isinstance(points, list) or not 1 <= len(points) <= PHOTO_LIMIT:
            raise ValueError("Each reviewed photograph needs one to 24 object labels.")
        for point in points:
            if set(point) != {"image", "x", "y", "product_id", "label"} or point["image"] != photo:
                raise ValueError("A label must use the exact reviewed photo and canonical fields.")
            if any(isinstance(point[k], bool) or not isinstance(point[k], (float, int)) or not 0 <= point[k] <= 1 for k in ("x", "y")):
                raise ValueError("Place labels inside the photograph.")
            if not isinstance(point["label"], str) or not 1 <= len(point["label"].strip()) <= 80:
                raise ValueError("Use an object label between one and 80 characters.")
            target = rows.get(point["product_id"])
            if not target or not target.get("published") or target.get("deleted_at"):
                raise ValueError("Link each object to a currently published product.")
        values["image_hotspots"].extend(points)
        added += len(points)
        if len(values["image_hotspots"]) > TOTAL_LIMIT:
            raise ValueError("This product exceeds the total photo-label limit.")
    changes = {identifier: {key: value for key, value in values.items() if value != rows[identifier].get(key, "")}
               for identifier, values in changes.items()}
    return {"changes": {key: value for key, value in changes.items() if value}, "skipped": skipped,
            "addedLabels": added, "repairedMissingPhotos": repaired, "correctedPhotos": corrected, "removedCopiedLabels": removed}


def sync_seed(catalog, rows_before, changes):
    conflicts, missing = [], []
    seed = {row["id"]: row for row in catalog["products"]}
    for identifier, values in changes.items():
        row = seed.get(identifier)
        if row is None:
            missing.append(identifier)
            continue
        for key, value in values.items():
            if row.get(key, [] if key in {"images", "image_hotspots"} else "") == rows_before[identifier][key]:
                row[key] = value
            elif row.get(key) != value:
                conflicts.append({"id": identifier, "field": key})
    return conflicts, missing


def run(*, root=ROOT, plan_path=None, database=None, apply=False):
    root = Path(root).resolve()
    database = Path(database or root / ".velora/velora.sqlite3")
    plan = read_json(Path(plan_path or root / "json/reports/object-label-photo-plan.json"))
    catalog_path = source_file(root, "json/catalog", "product-catalog.json")
    if not database.is_file():
        raise ValueError("Start Velora before adding object labels.")
    backup, conflicts, missing_seed = None, [], []
    with closing(sqlite3.connect(database, timeout=30)) as db:
        db.row_factory = sqlite3.Row
        before = read_products(db)
        result = build_changes(root, plan, before)
        if apply and result["changes"]:
            backups = database.parent / "backups"
            backups.mkdir(parents=True, exist_ok=True)
            backup = backups / ("before-object-labels-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".sqlite3")
            with closing(sqlite3.connect(backup)) as destination:
                db.backup(destination)
            db.execute("BEGIN IMMEDIATE")
            try:
                before = read_products(db)
                result = build_changes(root, plan, before)
                for identifier, values in result["changes"].items():
                    encoded = {key: json.dumps(value, ensure_ascii=False) if key in {"images", "image_hotspots"} else value for key, value in values.items()}
                    encoded["updated_at"] = utc_now()
                    db.execute(f"UPDATE products SET {','.join(key + '=?' for key in encoded)} WHERE id=?", (*encoded.values(), identifier))
                    db.execute("INSERT INTO product_activity(actor_id,actor_name,action,product_id,product_name,created_at) VALUES(NULL,?,?,?,?,?)",
                               ("Velora object labels", "update", identifier, before[identifier]["name"], utc_now()))
                db.commit()
            except BaseException:
                db.rollback()
                raise
            catalog = read_json(catalog_path)
            conflicts, missing_seed = sync_seed(catalog, before, result["changes"])
            atomic_json(catalog_path, catalog)
    return {"applied": apply, "changedProducts": len(result["changes"]), "addedLabels": result["addedLabels"],
            "repairedMissingPhotos": result["repairedMissingPhotos"], "skipped": result["skipped"],
            "correctedPhotos": result["correctedPhotos"], "removedCopiedLabels": result["removedCopiedLabels"],
            "backup": str(backup.relative_to(root)) if backup else None,
            "seedConflictsPreserved": conflicts, "productsOnlyInDatabase": missing_seed,
            "changes": result["changes"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    arguments = parser.parse_args()
    report = run(apply=arguments.apply)
    if arguments.apply:
        atomic_json(ROOT / "json/reports/object-label-apply.json", report)
    print(json.dumps({key: value for key, value in report.items() if key != "changes"}, indent=2))
