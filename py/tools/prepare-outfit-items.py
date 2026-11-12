"""Prepare auditable item-photo jobs for the visually reviewed outfit catalog.

This only reads public catalog data and writes project output manifests. Image
generation uses the built-in image tool; this script does not call an AI API.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

import hashlib
import json
from pathlib import Path
import re
from urllib.request import urlopen

OUTPUT = ROOT / "json/reports"
EXISTING = {
    "velora-example-espresso-bag": "assets/generated-items/espresso-top-handle-bag-v1.png",
    "velora-example-nude-court-shoes": "assets/generated-items/nude-pointed-court-shoes-v1.png",
    "velora-example-taupe-scarf": "assets/generated-items/taupe-draped-scarf-v1.png",
}


def prompt_for(item):
    pair = "Show ONE matching pair, not a single shoe." if item["kind"] == "shoes" else ""
    return (
        "Use case: product-mockup. Asset type: individual fashion e-commerce item photograph for Velora. "
        "Input image 1 is the exact outfit/product reference. Generate ONLY the following product, isolated from the person and the rest of the outfit: "
        + item["name"] + ". Visible construction to preserve: " + item["description"] + " " + pair + " "
        "Match the reference design, color, shape, seam lines and hardware faithfully. If the named product is a coordinated two- or three-piece set, show its matching pieces together as ONE product image. "
        "Use a natural invisible-mannequin presentation or neat product arrangement for garments; a three-quarter product view for bags and shoes; loose natural folds for scarves. "
        "Preserve a back/side view when the reference only shows that view; do not invent hidden front details. "
        "Photorealistic studio photograph on seamless soft off-white, restrained natural lighting, real fabric texture and gentle contact shadows. "
        "Entire item or coordinated set visible, centered, balanced close portrait framing with a modest margin. "
        "No person, head, body, hair, hands, mannequin, hanger or accessories other than the requested product. "
        "No brand names, text, price, watermark, added patterns, invented decorations or extra straps. "
        "Avoid CGI, 3D render, cartoon, synthetic surfaces, plastic fabric, warped geometry, melted seams, floating parts, duplicated objects (except a matching shoe pair), blur, overexposure, oversaturation, oversharpening and excessive HDR."
    )


def prepare():
    with urlopen("http://127.0.0.1:8000/api/catalog", timeout=10) as response:
        products = json.load(response)["products"]
    by_id = {product["id"]: product for product in products}
    plans = [plan for path in sorted(OUTPUT.glob("outfit-item-plan-*.json")) for plan in json.loads(path.read_text(encoding="utf-8"))]
    if len({plan["product_id"] for plan in plans}) != len(plans):
        raise ValueError("Outfit plans contain duplicate parent IDs; reconcile before generating.")
    forced = {}
    for plan in plans:
        for item in plan["items"]:
            if item.get("existing_product_id") in EXISTING:
                forced[(item["kind"], item["visual_key"])] = (item["existing_product_id"], EXISTING[item["existing_product_id"]])
    jobs, parents, changed, missing = {}, [], [], []
    for plan in plans:
        product = by_id.get(plan["product_id"])
        if product is None:
            missing.append(plan["product_id"]); continue
        if product["image"] != plan["image"]:
            changed.append({"id": product["id"], "plannedImage": plan["image"], "currentImage": product["image"]}); continue
        if sum(bool(item["is_primary"]) for item in plan["items"]) != 1:
            raise ValueError("Each outfit needs exactly one primary piece.")
        parent = {"product_id": product["id"], "name": product["name"], "image": product["image"], "note": plan.get("note", ""), "items": []}
        for item in plan["items"]:
            if not all(isinstance(item[axis], (int, float)) and 0 <= item[axis] <= 1 for axis in ("x", "y")):
                raise ValueError("A marker falls outside its source image.")
            fingerprint = "primary:" + product["id"] if item["is_primary"] else item["kind"] + ":" + item["visual_key"]
            digest = hashlib.sha256(fingerprint.encode()).hexdigest()[:20]
            identity = forced.get((item["kind"], item["visual_key"]))
            target_id = product["id"] if item["is_primary"] else identity[0] if identity else "piece-" + digest
            asset = "assets/generated-items/garment-" + product["id"] + "-v1.png" if item["is_primary"] else identity[1] if identity else "assets/generated-items/item-" + digest + "-v1.png"
            job = jobs.setdefault(asset, {"id": Path(asset).stem, "output": asset, "reference": product["image"], "kind": item["kind"],
                                          "name": item["name"], "description": item["description"], "color": item["color"], "hex": item["hex"],
                                          "target_product_id": target_id, "parent_product_id": product["id"], "is_primary": item["is_primary"],
                                          "prompt": prompt_for(item), "used_by": []})
            job["used_by"].append(product["id"])
            parent["items"].append({**item, "product_id": target_id, "asset": asset})
        parents.append(parent)
    unplanned = [{"id": p["id"], "name": p["name"], "image": p["image"]} for p in products if p["id"] not in {parent["product_id"] for parent in parents}
                 and not p["id"].startswith(("velora-example-", "piece-")) and not p.get("parent_product_id")]
    result = {"parents": parents, "jobs": sorted(jobs.values(), key=lambda job: (-len(job["used_by"]), job["is_primary"], job["id"])),
              "unplanned": unplanned, "changed": changed, "unpublished": missing}
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / "outfit-catalog-source.json").write_text(json.dumps({"products": products}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUTPUT / "outfit-items-manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ready = sum((ROOT / job["output"]).is_file() for job in jobs.values())
    print(json.dumps({"outfits": len(parents), "linkedItems": sum(len(p["items"]) for p in parents), "uniqueImages": len(jobs), "imagesReady": ready,
                      "unplanned": unplanned, "changed": changed, "unpublished": missing}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    prepare()
