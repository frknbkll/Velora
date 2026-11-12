"""Read-only public-image/dependency inventory; never scans credentials or accounts.

References include source code, all product photo fields (including drafts),
generated responsive candidates, creation records and rights metadata. A file
being absent from HTML alone is not evidence that it is safe to remove.
Run with a developer Python containing Pillow for image dimension verification.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file


import ast
from collections import defaultdict
from contextlib import closing
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import sys

ASSETS = ROOT / "assets"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".ico"}
REFERENCE = re.compile(r'''assets/[^"'\s<>`\\)]+\.(?:jpg|jpeg|png|webp|gif|svg|ico)''', re.I)


def image_references(text):
    return set(REFERENCE.findall(text))


def source_references():
    live, historical = set(), set()
    sources = [ROOT / "site.webmanifest", *(ROOT / "html").glob("*.html"), *(ROOT / "css").glob("*.css"),
               *(ROOT / "js").glob("*.js"), *(ROOT / "py/app").glob("*.py"),
               *(ROOT / "json/catalog").glob("*.json"), *(ROOT / "json/config").glob("*.json")]
    for path in sources:
        if not path.is_file() or path.suffix.lower() not in {".html", ".css", ".js", ".py", ".json", ".webmanifest"}:
            continue
        if path.name == "product-responsive-images.js":
            continue
        target = live if path.suffix.lower() != ".json" or path.name in {"product-catalog.json", "site-config.json"} else historical
        target.update(image_references(path.read_text(encoding="utf-8-sig")))
    # This alternate portrait filename is deliberately constructed at runtime.
    live.update(reference.replace("assets/team/", "assets/team/hover/") for reference in list(live)
                if reference.startswith("assets/team/") and "/hover/" not in reference)
    database = ROOT / ".velora/velora.sqlite3"
    if database.is_file():
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
            available = {row[1] for row in connection.execute("PRAGMA table_info(products)")}
            columns = [key for key in ("image", "images", "item_image", "image_hotspots", "color_variants", "color_key") if key in available]
            for row in connection.execute("SELECT " + ",".join(columns) + " FROM products"):
                for value in row:
                    if isinstance(value, str):
                        live.update(image_references(value))
    for directory in (ROOT / "json", ROOT / "output", ROOT / "docs", ROOT / "py/tools", ROOT / "py/tests"):
        for path in directory.rglob("*") if directory.is_dir() else []:
            if path.name in {"asset-dependency-audit.json", "asset-cleanup-manifest.json"}:
                continue  # Inventory output is not evidence of actual usage.
            if (path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(ROOT) and
                    path.suffix.lower() in {".json", ".jsonl", ".md", ".txt", ".py", ".ps1"} and path.stat().st_size < 30_000_000):
                historical.update(image_references(path.read_text(encoding="utf-8-sig", errors="replace")))
    return live, historical


def dependency_report():
    files = [*(ROOT / "py/app").glob("*.py"), *(ROOT / "py/launch").glob("*.py"),
             *(ROOT / "py/tools").glob("*.py"), *(ROOT / "py/tests").glob("*.py")]
    local = {path.stem for path in files}
    imports = defaultdict(set)
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            names = [alias.name.split(".")[0] for alias in node.names] if isinstance(node, ast.Import) else (
                [node.module.split(".")[0]] if isinstance(node, ast.ImportFrom) and node.module else [])
            for name in names:
                if name not in sys.stdlib_module_names and name not in local:
                    imports[name].add(path.relative_to(ROOT).as_posix())
    return [{"module": module, "availableInAuditPython": importlib.util.find_spec(module) is not None,
             "usedBy": sorted(paths)} for module, paths in sorted(imports.items())]


def audit():
    try:
        from PIL import Image, ImageOps
    except ImportError:
        Image = ImageOps = None
    live, historical = source_references()
    source = (ROOT / "js/product-responsive-images.js").read_text(encoding="utf-8")
    responsive, _ = json.JSONDecoder().raw_decode(source.split("window.VeloraResponsiveImages =", 1)[1].lstrip())
    generated = {entry.rsplit(" ", 1)[0] for details in responsive.values() for entry in details["srcset"].split(", ")}
    live.update(generated)
    # Complete favicon outputs are intentionally retained even if a particular
    # browser only requests favicon.ico. Creation uses dynamically built names.
    live.update(path.relative_to(ROOT).as_posix() for path in (ASSETS / "brand").glob("*"))
    # Lossless creation masters are now actively used by the optimizer. Preserve
    # only the geometry/pixel-confirmed pairs used for referenced JPEG exports.
    masters = set()
    if Image:
        import runpy
        select_master = runpy.run_path(str(ROOT / "py/tools/prepare-responsive-images.py"))["verified_lossless_master"]
        for reference in live | set(responsive):
            path = (ROOT / reference).resolve()
            if path.is_file() and path.is_relative_to(ASSETS):
                master = select_master(path)
                if master != path:
                    masters.add(master.relative_to(ROOT).as_posix())
        live.update(masters)
    # Manifest originals remain retained even when only a historic upload uses one.
    retained = live | historical | set(responsive)
    images, hashes = [], defaultdict(list)
    broken, small, linked = [], [], []
    for path in sorted(ASSETS.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if path.is_symlink() or not path.resolve().is_relative_to(ASSETS.resolve()):
            linked.append(relative)
            continue
        row = {"path": relative, "bytes": path.stat().st_size,
               "usage": "live" if relative in live else "historical" if relative in historical else "responsive-manifest-only" if relative in responsive else "unreferenced"}
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        row["sha256"] = digest
        hashes[digest].append(relative)
        if Image and path.suffix.lower() not in {".svg", ".ico"}:
            try:
                with Image.open(path) as original:
                    original.verify()
                with Image.open(path) as original:
                    photo = ImageOps.exif_transpose(original)
                    row.update(width=photo.width, height=photo.height, format=original.format)
                if relative in live and not relative.startswith(("assets/responsive/", "assets/brand/")) and min(row["width"], row["height"]) < 640:
                    small.append({key: row[key] for key in ("path", "width", "height", "bytes")})
            except (OSError, ValueError) as error:
                broken.append({"path": relative, "error": str(error)})
        images.append(row)
    unused = [row for row in images if row["path"] not in retained]
    unused_responsive = [row for row in unused if row["path"].startswith("assets/responsive/")]
    return {"scope": "Public image assets and product photo fields only; no secrets, accounts or private documents read.",
            "images": images, "totals": {"images": len(images), "bytes": sum(row["bytes"] for row in images),
                "liveReferences": len(live), "historicalReferences": len(historical), "responsiveOriginals": len(responsive),
                "verifiedLosslessMasters": len(masters),
                "responsiveCandidateReferences": len(generated), "unreferencedImages": len(unused),
                "unreferencedBytes": sum(row["bytes"] for row in unused), "obsoleteResponsiveFiles": len(unused_responsive),
                "obsoleteResponsiveBytes": sum(row["bytes"] for row in unused_responsive)},
            "unreferenced": unused, "duplicateGroups": [paths for paths in hashes.values() if len(paths) > 1],
            "corruptImages": broken, "smallLiveOriginals": small, "linkedFilesSkipped": linked, "dependencies": dependency_report(),
            "pillowAvailableForVerification": bool(Image)}


if __name__ == "__main__":
    report = audit()
    destination = ROOT / "json/reports/asset-dependency-audit.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in {"images", "unreferenced", "duplicateGroups"}}, indent=2))
    print(f"Duplicate byte-identical image groups: {len(report['duplicateGroups'])}. Full report: json/reports/asset-dependency-audit.json")
