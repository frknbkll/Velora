"""Apply visually approved outfit/item assets without replacing the owner's shop edits.

Default is a read-only preview. --apply requires every planned outfit to be
ready; --apply --ready-only applies complete outfits while images are generated.
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
import hashlib
import json
import math
from pathlib import Path
import re
import runpy
import sqlite3
import sys
import tempfile

from server import image_extension

JOURNAL_TABLE = "outfit_item_setup"
PRICE_BY_KIND = {"bag": 49, "shoes": 59, "scarf": 19, "top": 29, "bottom": 49, "outerwear": 89}
JSON_FIELDS = {"images", "sizes", "color_variants", "image_hotspots"}
MARKER_LABELS = {"bag": "Bag", "shoes": "Shoes", "scarf": "Scarf", "top": "Top", "bottom": "Trousers", "outerwear": "Outerwear"}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def json_text(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def asset_path(root, value):
    if not isinstance(value, str) or not value.startswith("assets/") or "\\" in value or "%" in value or any(ord(c) < 32 for c in value):
        raise ValueError("An item asset must be a relative path inside assets/.")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError("An item asset path contains an invalid component.")
    path = (root / value).resolve()
    if not path.is_relative_to((root / "assets").resolve()) or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("An item asset must be a raster image inside assets/.")
    return path


def read_json(path, fallback=None):
    if not path.is_file():
        if fallback is not None:
            return fallback
        raise ValueError(f"Required file is missing: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.is_file() and path.read_text(encoding="utf-8") == body:
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent, prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(body)
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def validate_manifest(root, manifest):
    parents, jobs = manifest.get("parents"), manifest.get("jobs")
    if not isinstance(parents, list) or not isinstance(jobs, list):
        raise ValueError("The manifest needs parents and jobs arrays.")
    by_asset, parent_ids, job_ids = {}, set(), set()
    if any(not isinstance(parent, dict) for parent in parents):
        raise ValueError("Every outfit plan must be an object.")
    all_parent_ids = {parent.get("product_id") for parent in parents if isinstance(parent.get("product_id"), str)}
    source_images = {parent.get("image") for parent in parents if isinstance(parent.get("image"), str)}
    for job in jobs:
        if not isinstance(job, dict) or not isinstance(job.get("id"), str) or job["id"] in job_ids:
            raise ValueError("Every image job needs a unique ID.")
        asset_path(root, job.get("output"))
        if job["output"] in source_images:
            raise ValueError("An individual item image cannot reuse a full-outfit source photo.")
        if job["output"] in by_asset:
            raise ValueError("Every image output must have one manifest job.")
        by_asset[job["output"]] = job; job_ids.add(job["id"])
    for parent in parents:
        parent_id, items = parent.get("product_id"), parent.get("items")
        if not isinstance(parent_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", parent_id) or parent_id in parent_ids:
            raise ValueError("Every outfit needs a unique valid product ID.")
        parent_ids.add(parent_id); asset_path(root, parent.get("image"))
        if not isinstance(items, list) or not 1 <= len(items) <= 24 or any(not isinstance(item, dict) for item in items) or sum(item.get("is_primary") is True for item in items) != 1:
            raise ValueError("Each outfit needs exactly one primary item and at most 24 placements.")
        for item in items:
            job = by_asset.get(item.get("asset"))
            target = item.get("product_id")
            if job is None or job.get("target_product_id") != target or not isinstance(target, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", target):
                raise ValueError("Each item needs an image job for its exact product ID.")
            if item["is_primary"] and target != parent_id:
                raise ValueError("The primary item must retain its outfit's product ID.")
            if not item["is_primary"] and target in all_parent_ids:
                raise ValueError("An outfit record cannot be converted into another outfit's individual item.")
            if not isinstance(item.get("is_primary"), bool) or any(isinstance(item.get(key), bool) or not isinstance(item.get(key), (int, float)) or not math.isfinite(item[key]) or not 0 <= item[key] <= 1 for key in ("x", "y")):
                raise ValueError("Item marker positions must be finite fractions inside the photo.")
            if not all(isinstance(item.get(key), str) and item[key].strip() for key in ("name", "description", "kind", "color", "hex")) or not re.fullmatch(r"#[a-fA-F0-9]{6}", item["hex"]):
                raise ValueError("An item needs visible product details and a valid color swatch.")
    return by_asset


def approval_status(root, job, approvals):
    path = asset_path(root, job["output"])
    if not path.is_file():
        return None, "image_missing"
    review = approvals.get(job["id"])
    if not review or review.get("status") != "approved" or review.get("output") != job["output"]:
        return None, "image_not_approved"
    sha = digest(path)
    if not isinstance(review.get("sha256"), str) or sha != review["sha256"]:
        return None, "approval_hash_mismatch"
    if path.stat().st_size > 32 * 1024 * 1024 or image_extension(path.read_bytes()) is None:
        return None, "image_invalid"
    return sha, None


def stored_records(db):
    return {row["id"]: dict(row) for row in db.execute("SELECT * FROM products")}


def stored_journal(db):
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (JOURNAL_TABLE,)).fetchone() is None:
        return {}
    return {(row["entity_kind"], row["entity_id"]): dict(row) for row in db.execute(f"SELECT * FROM {JOURNAL_TABLE}")}


def public_seed_values(values):
    result = dict(values)
    for key in JSON_FIELDS & result.keys():
        result[key] = json.loads(result[key]) if isinstance(result[key], str) else result[key]
    if "published" in result:
        result["published"] = bool(result["published"])
    return result


def build_plan(root, manifest, qa, rows, journal, catalog):
    jobs = validate_manifest(root, manifest)
    approvals = {review["id"]: review for review in qa.get("images", []) if isinstance(review, dict) and isinstance(review.get("id"), str)}
    assets = {asset: approval_status(root, job, approvals) for asset, job in jobs.items()}
    source_images = {parent["image"] for parent in manifest["parents"]}
    planned_parents = {parent["product_id"]: parent for parent in manifest["parents"]}
    seed_by_id = {product["id"]: product for product in catalog["products"]}
    old_examples = {item["id"]: item["description"] for item in runpy.run_path(str(Path(__file__).with_name("add-accessory-examples.py")))["EXAMPLES"]}
    changes, entries, statuses, checked_assets = {}, {}, [], {}

    def preferred_parent(job, target_id, fallback_id):
        # A shared item must not be made permanently private just because its
        # first reference outfit was unpublished after the visual review.
        candidates = [job.get("parent_product_id"), *(job.get("used_by") or []), fallback_id,
                      *(parent_id for parent_id, plan in planned_parents.items()
                        if any(not item["is_primary"] and item["product_id"] == target_id for item in plan["items"]))]
        available, seen = [], set()
        for candidate in candidates:
            if not isinstance(candidate, str) or candidate in seen:
                continue
            seen.add(candidate)
            record, plan = rows.get(candidate), planned_parents.get(candidate)
            if not record or not plan or record.get("deleted_at") or record.get("parent_product_id") or record["image"] != plan["image"]:
                continue
            if not any(not item["is_primary"] and item["product_id"] == target_id for item in plan["items"]):
                continue
            available.append((candidate, record))
        return next((item for item in available if item[1]["published"]), available[0] if available else (fallback_id, rows[fallback_id]))

    def record_change(kind, product_id, values, created, fingerprint):
        previous = changes.get(product_id)
        if previous:
            return
        changes[product_id] = {"values": values, "created": created}
        seed_changes = public_seed_values(values)
        current_seed = seed_by_id.get(product_id)
        details = {"created": created, "seed_changes": seed_changes,
                   "seed_before": {key: {"present": current_seed is not None and key in current_seed,
                                        "value": current_seed.get(key) if current_seed is not None else None} for key in seed_changes},
                   "seed_record": public_seed_values({**rows.get(product_id, {}), **values})}
        entries[(kind, product_id)] = {"fingerprint": fingerprint, "details": details}

    for parent in manifest["parents"]:
        parent_id = parent["product_id"]
        row = rows.get(parent_id)
        problems = [{"asset": item["asset"], "reason": assets[item["asset"]][1]} for item in parent["items"] if assets[item["asset"]][1]]
        if problems:
            statuses.append({"product_id": parent_id, "status": "pending", "reasons": problems}); continue
        fingerprint = hashlib.sha256(json_text({"parent": parent, "assets": {item["asset"]: assets[item["asset"]][0] for item in parent["items"]}}).encode()).hexdigest()
        previous = journal.get(("parent", parent_id))
        if previous:
            statuses.append({"product_id": parent_id, "status": "already_applied" if previous["fingerprint"] == fingerprint else "applied_plan_changed_review_required"}); continue
        if row is None or row.get("deleted_at"):
            statuses.append({"product_id": parent_id, "status": "skipped", "reason": "outfit_missing_or_trashed"}); continue
        if row["image"] != parent["image"] or row.get("parent_product_id"):
            statuses.append({"product_id": parent_id, "status": "skipped", "reason": "outfit_cover_or_group_changed"}); continue
        primary = next(item for item in parent["items"] if item["is_primary"])
        images = json.loads(row["images"])
        if primary["asset"] not in images:
            if len(images) >= 12:
                statuses.append({"product_id": parent_id, "status": "skipped", "reason": "outfit_gallery_full"}); continue
            images.append(primary["asset"])
        planned_targets = {item["product_id"] for item in parent["items"]}
        markers = [point for point in json.loads(row["image_hotspots"]) if point.get("image") != parent["image"] or point.get("product_id") not in planned_targets]
        markers += [{"image": parent["image"], "x": round(float(item["x"]), 6), "y": round(float(item["y"]), 6), "product_id": item["product_id"],
                     "label": parent["name"][:80] if item["is_primary"] else MARKER_LABELS.get(item["kind"], "Item")} for item in parent["items"]]
        if len(markers) > 24:
            statuses.append({"product_id": parent_id, "status": "skipped", "reason": "custom_markers_leave_no_room"}); continue
        blocked = [item for item in parent["items"] if not item["is_primary"] and item["product_id"] in rows
                   and (rows[item["product_id"]].get("deleted_at") or (not rows[item["product_id"]].get("parent_product_id") and any(other.get("parent_product_id") == item["product_id"] for other in rows.values())))]
        if blocked:
            statuses.append({"product_id": parent_id, "status": "skipped", "reason": "linked_item_trashed_or_has_children"}); continue
        for item in parent["items"]:
            checked_assets[item["asset"]] = assets[item["asset"]][0]
            if item["is_primary"] or ("item", item["product_id"]) in journal or item["product_id"] in changes:
                continue
            target_id, job = item["product_id"], jobs[item["asset"]]
            existing = rows.get(target_id)
            preferred_id, preferred = preferred_parent(job, target_id, parent_id)
            stamp = utc_now()
            if existing:
                values = {}
                # Replace old full-outfit copies once. An owner's independently edited item photo is retained.
                if existing["image"] in source_images:
                    retained_photos = [photo for photo in json.loads(existing["images"]) if photo not in source_images and photo != item["asset"]]
                    values.update(image=item["asset"], images=json_text([item["asset"], *retained_photos]), item_image=item["asset"], color_key=target_id)
                elif not existing.get("item_image"):
                    values["item_image"] = existing["image"]
                if not existing.get("parent_product_id"):
                    values["parent_product_id"] = preferred_id
                stale = json.loads(existing["image_hotspots"])
                retained = [point for point in stale if point.get("image") not in source_images]
                if retained != stale:
                    values["image_hotspots"] = json_text(retained)
                if existing.get("description") == old_examples.get(target_id):
                    values["description"] = f"{item['description']} Styled with {preferred['name']}. Materials, measurements and availability are unconfirmed."
                if values:
                    values["updated_at"] = stamp
            else:
                sizes = ["One size"] if item["kind"] in {"bag", "scarf"} else [str(size) for size in range(36, 43)] if item["kind"] == "shoes" else json.loads(row["sizes"])
                values = {"id": target_id, "name": item["name"][:160], "image": item["asset"], "images": json_text([item["asset"]]),
                          "founder": row["founder"], "collection": row["collection"], "price": PRICE_BY_KIND.get(item["kind"], 79),
                          "description": f"{item['name']} in {item['color']}, styled with {preferred['name']}. An individual styling item for this showcase; price and sizes are illustrative. Material, fit and availability are not confirmed.",
                          "published": int(preferred["published"]), "updated_at": stamp, "created_at": stamp, "color_key": target_id, "legacy_key": "",
                          "base_color": item["color"][:40], "color_hex": item["hex"].lower(), "sku": "VL-ITEM-" + hashlib.sha256(target_id.encode()).hexdigest()[:16].upper(),
                          "stock": None, "sizes": json_text(sizes), "deleted_at": None, "color_variants": "[]", "image_hotspots": "[]",
                          "material": "", "fabric_weight": "", "origin": "", "fit": "", "parent_product_id": preferred_id, "item_image": item["asset"]}
            item_fingerprint = hashlib.sha256(json_text({"job": job["id"], "asset": assets[item["asset"]][0]}).encode()).hexdigest()
            record_change("item", target_id, values, existing is None, item_fingerprint)
        item_image = row.get("item_image") if row.get("item_image") and row["item_image"] not in source_images else primary["asset"]
        record_change("parent", parent_id, {"images": json_text(images), "item_image": item_image, "image_hotspots": json_text(markers), "updated_at": utc_now()}, False, fingerprint)
        statuses.append({"product_id": parent_id, "status": "ready"})
    return {"changes": changes, "entries": entries, "statuses": statuses, "checked_assets": checked_assets}


def synchronize_catalog(catalog, journal):
    """Replay setup metadata only when the seed still has its recorded previous value."""
    result = json.loads(json.dumps(catalog))
    by_id = {product["id"]: product for product in result["products"]}
    conflicts = []
    for entry in journal.values():
        details = json.loads(entry["details"]) if isinstance(entry["details"], str) else entry["details"]
        record = details["seed_record"]
        product_id = record["id"]
        if product_id not in by_id:
            result["products"].append(record); by_id[product_id] = record; continue
        if details["created"]:
            continue
        product = by_id[product_id]
        for key, value in details["seed_changes"].items():
            before = details["seed_before"][key]
            same_before = (key in product) == before["present"] and (not before["present"] or product[key] == before["value"])
            if same_before or product.get(key) == value:
                product[key] = value
            else:
                conflicts.append({"product_id": product_id, "field": key})
    return result, conflicts


def run(*, root=ROOT, database=None, manifest_path=None, qa_path=None, journal_path=None, catalog_path=None, apply=False, ready_only=False):
    root = Path(root).resolve()
    database = Path(database or root / ".velora/velora.sqlite3").resolve()
    manifest_path = Path(manifest_path or root / "json/reports/outfit-items-manifest.json")
    qa_path = Path(qa_path or root / "json/reports/outfit-items-image-qa.json")
    journal_path = Path(journal_path or root / "json/reports/applied-outfit-items.json")
    catalog_path = Path(catalog_path or source_file(root, "json/catalog", "product-catalog.json"))
    if not database.is_file():
        raise ValueError("Start the updated Velora server before applying outfit items.")
    manifest, qa, catalog = read_json(manifest_path), read_json(qa_path, {"images": []}), read_json(catalog_path)
    if not isinstance(catalog, dict) or not isinstance(catalog.get("products"), list):
        raise ValueError("The default catalog needs a products array.")
    backup = None
    with closing(sqlite3.connect(database, timeout=30)) as db:
        db.row_factory = sqlite3.Row
        columns = {row["name"] for row in db.execute("PRAGMA table_info(products)")}
        if not {"parent_product_id", "item_image", "image_hotspots"} <= columns:
            raise ValueError("Restart the updated Velora server to enable grouped outfit items, then run this command again.")
        plan = build_plan(root, manifest, qa, stored_records(db), stored_journal(db), catalog)
        if apply:
            blockers = [s for s in plan["statuses"] if s["status"] in {"pending", "skipped", "applied_plan_changed_review_required"}]
            if blockers and not ready_only:
                return {"applied": False, "reason": "Not all outfits are ready. Complete the assets or use --ready-only.", "counts": count_statuses(plan["statuses"]), "outfits": plan["statuses"]}
            if plan["changes"]:
                backup_directory = database.parent / "backups"; backup_directory.mkdir(parents=True, exist_ok=True)
                backup = backup_directory / ("before-outfit-items-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".sqlite3")
                with closing(sqlite3.connect(backup)) as destination:
                    db.backup(destination)
                db.execute("BEGIN IMMEDIATE")
                try:
                    # Re-read under the write lock so an edit made during backup is not overwritten.
                    plan = build_plan(root, manifest, qa, stored_records(db), stored_journal(db), catalog)
                    if not ready_only and any(s["status"] in {"pending", "skipped", "applied_plan_changed_review_required"} for s in plan["statuses"]):
                        raise ValueError("The catalog changed while preparing. No outfit changes were applied; preview again.")
                    db.execute(f"CREATE TABLE IF NOT EXISTS {JOURNAL_TABLE}(entity_kind TEXT NOT NULL,entity_id TEXT NOT NULL,fingerprint TEXT NOT NULL,applied_at TEXT NOT NULL,details TEXT NOT NULL,PRIMARY KEY(entity_kind,entity_id))")
                    for product_id, change in plan["changes"].items():
                        values = change["values"]
                        if change["created"]:
                            db.execute(f"INSERT INTO products({','.join(values)}) VALUES({','.join('?' for _ in values)})", tuple(values.values()))
                        elif values:
                            db.execute(f"UPDATE products SET {','.join(key + '=?' for key in values)} WHERE id=?", (*values.values(), product_id))
                        if values:
                            name = db.execute("SELECT name FROM products WHERE id=?", (product_id,)).fetchone()["name"]
                            db.execute("INSERT INTO product_activity(actor_id,actor_name,action,product_id,product_name,created_at) VALUES(NULL,?,?,?,?,?)", ("Velora outfit setup", "create" if change["created"] else "update", product_id, name, utc_now()))
                    for (kind, product_id), entry in plan["entries"].items():
                        db.execute(f"INSERT INTO {JOURNAL_TABLE} VALUES(?,?,?,?,?)", (kind, product_id, entry["fingerprint"], utc_now(), json_text(entry["details"])))
                    if any(digest(asset_path(root, asset)) != sha for asset, sha in plan["checked_assets"].items()):
                        raise ValueError("An approved image changed during setup. No outfit changes were applied; review its new hash first.")
                    db.commit()
                except BaseException:
                    db.rollback(); raise
            journal = stored_journal(db)
            seed, conflicts = synchronize_catalog(catalog, journal)
            atomic_json(catalog_path, seed)
            atomic_json(journal_path, {"version": 1, "entries": [entry for _, entry in sorted(journal.items())]})
        else:
            conflicts = []
    counts = count_statuses(plan["statuses"])
    return {"applied": bool(apply), "counts": counts, "wouldCreate": sum(c["created"] for c in plan["changes"].values()),
            "wouldUpdate": sum(not c["created"] and bool(c["values"]) for c in plan["changes"].values()),
            "backup": str(backup.relative_to(root)) if backup and backup.is_relative_to(root) else str(backup) if backup else None,
            "seedConflictsPreserved": conflicts, "outfits": plan["statuses"]}


def count_statuses(statuses):
    return {key: sum(status["status"] == key for status in statuses) for key in ("ready", "pending", "skipped", "already_applied", "applied_plan_changed_review_required")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--ready-only", action="store_true")
    args = parser.parse_args()
    try:
        result = run(apply=args.apply, ready_only=args.ready_only)
    except (ValueError, OSError, sqlite3.Error) as error:
        parser.exit(2, str(error) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.apply and not result["applied"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
