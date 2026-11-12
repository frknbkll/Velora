"""Build smaller public-photo downloads without changing the original photos.

Run from any directory with ``python py/tools/prepare-responsive-images.py``.
Requires Pillow. Use ``--verify`` to check existing candidates without writing.
References come from the site's source files, catalog and color map. Public
uploads are included because their catalog references can live in the database;
the database, private folders, environment files and output drafts are not read.
Originals remain available for explicit enlarged views.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file


from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from PIL import Image, ImageChops, ImageOps, ImageStat


ASSETS = (ROOT / "assets").resolve()
DESTINATION = (ROOT / "assets" / "responsive").resolve()
WIDTHS = (480, 960, 1440)
HERO_WIDTHS = (480, 960, 1440, 1920, 2560, 3840)
QUALITY = 82
# The encoding recipe is unchanged, so existing correct candidates are reused.
RECIPE = f"webp-v1-quality-{QUALITY}-method-6-exif-transpose".encode("ascii")
IMAGE_REFERENCE = re.compile(r'''assets/[^"'\s<>`\\)]+\.(?:jpg|jpeg|png|webp)''', re.I)
SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def verified_lossless_master(source: Path) -> Path:
    """Prefer a matching PNG creation master over a JPEG export.

    The public source key and full-resolution original stay unchanged. A same
    filename alone is insufficient: orientation-corrected dimensions and pixel
    similarity must agree, otherwise the existing JPEG remains the input.
    """
    gallery = ASSETS / "gallery"
    if source.suffix.lower() not in {".jpg", ".jpeg"} or not source.is_relative_to(gallery):
        return source
    candidate = source.with_suffix(".png").resolve()
    if not candidate.is_relative_to(gallery) or not candidate.is_file():
        return source
    try:
        with Image.open(source) as original, Image.open(candidate) as master:
            original = ImageOps.exif_transpose(original).convert("RGB")
            master = ImageOps.exif_transpose(master).convert("RGB")
            if original.size != master.size:
                return source
            original.thumbnail((256, 256), Image.Resampling.LANCZOS)
            master = master.resize(original.size, Image.Resampling.LANCZOS)
            # Compression noise in the reviewed pairs is under 1.1/255 RMS.
            if max(ImageStat.Stat(ImageChops.difference(original, master)).rms) > 2:
                return source
    except (OSError, ValueError):
        return source
    return candidate


def referenced_images() -> list[str]:
    references: set[str] = set()
    sources = [ROOT / "json/catalog/product-catalog.json"]
    for folder in ("html", "css", "js"):
        sources.extend(path for path in (ROOT / folder).glob("*." + folder) if path.name != "product-responsive-images.js")
    for source in sources:
        references.update(IMAGE_REFERENCE.findall(source.read_text(encoding="utf-8")))
    # The team alternate image paths are constructed by team-portraits.js.
    references.update(reference.replace("assets/team/", "assets/team/hover/")
                      for reference in list(references)
                      if reference.startswith("assets/team/") and "/hover/" not in reference)
    upload_directory = ASSETS / "uploads"
    if upload_directory.is_dir():
        references.update(path.relative_to(ROOT).as_posix() for path in upload_directory.iterdir()
                          if path.is_file() and path.suffix.lower() in SUFFIXES)
    # Exclude generated files and non-file references such as JS examples.
    return sorted(reference for reference in references
                  if not reference.startswith(("assets/responsive/", "assets/brand/")) and
                  (ROOT / reference).resolve().is_relative_to(ASSETS) and
                  (ROOT / reference).is_file())


def candidate_widths(reference: str, width: int) -> list[int]:
    requested = HERO_WIDTHS if Path(reference).name.startswith("hero-") else WIDTHS
    return sorted({min(width, requested_width) for requested_width in requested})


def valid_candidate(target: Path, width: int, height: int) -> bool:
    try:
        with Image.open(target) as candidate:
            if candidate.format != "WEBP" or candidate.size != (width, height):
                return False
            candidate.verify()
        return True
    except (OSError, ValueError):
        return False


def prepare(reference: str) -> tuple[str, dict, int, int, int, bool]:
    source = (ROOT / reference).resolve()
    if not source.is_relative_to(ASSETS) or source.is_relative_to(DESTINATION) or not source.is_file():
        raise ValueError(f"Referenced image is missing or outside the public originals: {reference}")
    original_bytes = source.stat().st_size
    master = verified_lossless_master(source)
    source_bytes = master.read_bytes()
    fingerprint = hashlib.sha256(RECIPE + b"\0" + source_bytes).hexdigest()[:24]
    with Image.open(master) as photo:
        photo = ImageOps.exif_transpose(photo)
        if photo.mode not in ("RGB", "RGBA"):
            photo = photo.convert("RGBA" if "transparency" in photo.info else "RGB")
        width, height = photo.size
        candidates: list[tuple[str, int]] = []
        for target_width in candidate_widths(reference, width):
            target = DESTINATION / f"{fingerprint}-{target_width}.webp"
            if not target.resolve().is_relative_to(DESTINATION):
                raise ValueError("Responsive image destination is outside its asset directory")
            target_height = max(1, round(height * target_width / width))
            if not valid_candidate(target, target_width, target_height):
                resized = photo.resize((target_width, target_height), Image.Resampling.LANCZOS)
                # An atomic replace also handles identical originals processed by
                # different workers without exposing a partially written image.
                with tempfile.NamedTemporaryFile(dir=DESTINATION, suffix=".webp", delete=False) as temporary:
                    temporary_path = Path(temporary.name)
                try:
                    resized.save(temporary_path, "WEBP", quality=QUALITY, method=6)
                    temporary_path.replace(target)
                finally:
                    if temporary_path.exists():
                        temporary_path.unlink()
            candidates.append((target.relative_to(ROOT).as_posix(), target_width))
    small_bytes = (ROOT / candidates[0][0]).stat().st_size
    generated_bytes = sum((ROOT / path).stat().st_size for path, _ in candidates if path != reference)
    return reference, {
        "src": candidates[0][0],
        "srcset": ", ".join(f"{path} {candidate_width}w" for path, candidate_width in candidates),
        "width": width,
        "height": height,
    }, original_bytes, small_bytes, generated_bytes, master != source


HELPER = '''
// Explicit application keeps portrait/zoom code in control of its original URL.
(() => {
  "use strict";
  const get = (original) => window.VeloraResponsiveImages[original] || null;
  function apply(image, original, sizes) {
    if (!image || image.tagName !== "IMG" || typeof original !== "string") return false;
    const responsive = get(original);
    image.dataset.originalSrc = original;
    if (responsive) {
      image.srcset = responsive.srcset;
      image.sizes = sizes || image.sizes || "100vw";
      image.width = responsive.width;
      image.height = responsive.height;
      image.src = responsive.src;
    } else {
      image.removeAttribute("srcset");
      image.src = original;
    }
    return Boolean(responsive);
  }
  window.VeloraImageSources = Object.freeze({ get, apply });
})();
'''


def verify_manifest() -> None:
    source = (ROOT / "js/product-responsive-images.js").read_text(encoding="utf-8")
    manifest, _ = json.JSONDecoder().raw_decode(source.split("window.VeloraResponsiveImages =", 1)[1].lstrip())
    candidates = 0
    for reference, details in manifest.items():
        original = (ROOT / reference).resolve()
        if not original.is_relative_to(ASSETS) or original.is_relative_to(DESTINATION):
            raise ValueError(f"Invalid original path: {reference}")
        with Image.open(original) as photo:
            photo = ImageOps.exif_transpose(photo)
            width, height = photo.size
        if (details["width"], details["height"]) != (width, height):
            raise ValueError(f"Original dimensions differ: {reference}")
        for candidate in details["srcset"].split(", "):
            relative_path, descriptor = candidate.rsplit(" ", 1)
            target_width = int(descriptor.removesuffix("w"))
            target = (ROOT / relative_path).resolve()
            if (not target.is_relative_to(DESTINATION) or target_width > width or
                    not valid_candidate(target, target_width, max(1, round(height * target_width / width)))):
                raise ValueError(f"Invalid responsive candidate: {candidate}")
            candidates += 1
    print(f"Verified {len(manifest)} public originals and {candidates} correctly sized WebP candidates; no upscaling.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Check the existing generated manifest without writing files.")
    args = parser.parse_args()
    if args.verify:
        verify_manifest()
        return
    if not DESTINATION.is_relative_to(ROOT):
        raise ValueError("Responsive image directory must be inside the project")
    DESTINATION.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as executor:
        results = list(executor.map(prepare, referenced_images()))
    manifest = {reference: details for reference, details, *_ in results}
    output = ROOT / "js/product-responsive-images.js"
    output.write_text(
        "// Generated by py/tools/prepare-responsive-images.py. Originals are retained for zoom.\n"
        "window.VeloraResponsiveImages = " + json.dumps(manifest, ensure_ascii=False, indent=2) + ";\n" + HELPER,
        encoding="utf-8",
    )
    originals = sum(row[2] for row in results)
    small = sum(row[3] for row in results)
    generated = sum(row[4] for row in results)
    saving = (1 - small / originals) * 100 if originals else 0
    print(f"Prepared {len(results)} referenced images. Originals: {originals:,} bytes; "
          f"smallest candidates: {small:,} bytes ({saving:.1f}% smaller); "
          f"all generated candidates: {generated:,} bytes.")
    print(f"Used {sum(row[5] for row in results)} geometry/pixel-matched PNG masters to avoid recompressing JPEG exports. "
          "Public source URLs and full-resolution zoom originals are unchanged.")


if __name__ == "__main__":
    main()
