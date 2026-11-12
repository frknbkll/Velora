# Images and dependency maintenance

Reviewed 11 November 2026. The application uses the Python standard library;
there is no Node/npm installation or application pip dependency to prune.
The browser's local Three.js and QR libraries are active features and remain
bundled; see [the third-party inventory](THIRD_PARTY_AUDIT.md).

Pillow is used only by optional image preparation/audit tools, not by the
isolated application runtime. The installed and tested version is pinned in
[requirements-tools.txt](../requirements-tools.txt). Its
[official 13.0.0 release notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html)
confirm the release and supported Python versions. No additional packages or
global package removals were necessary. The unused project-local image SDK
environment was archived as described below. For a separate developer environment:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-tools.txt
.venv\Scripts\python.exe tools\audit-assets.py
.venv\Scripts\python.exe tools\prepare-responsive-images.py
.venv\Scripts\python.exe tools\prepare-responsive-images.py --verify
```

## Image quality

The initial inventory checked 2,566 public image files and found no corrupt
images or product originals with a short side below 640 pixels. Small brand
icons and the 1200×630 sharing image have intentional dimensions. Resolution
and decoding checks do not establish photographic authenticity or native
detail; the existing enlarged hero must not be described as native 8K.

The optimizer now checks for lossless PNG creation masters beside JPEG
exports. It uses a master only when its orientation-corrected dimensions agree
and its downsampled pixel comparison is within the conservative reviewed
threshold. Different products, colors, crops, corrupt masters or missing files
fall back to the original export. Four targeted tests cover these identity
guards. No garment, person, color, framing or object-label coordinates change.

This preparation used 146 matching masters, avoiding another lossy JPEG decode
as the source of the WebP export. The 109 previously unreferenced pose PNGs are
valuable inputs to this process and are deliberately retained. The public JPEG
URLs and full-resolution originals used for deliberate zoom stay intact.

The verified manifest contains 647 originals and 1,665 candidate references.
Small candidates total 10,231,084 bytes versus 682,384,220 bytes of referenced
originals (98.5% less); browsers select an appropriate candidate rather than
downloading every size. No candidates are upscaled. These are encoding and
delivery improvements; they do not invent missing image detail.

All 14 image-delivery browser checks passed after updating static sources:
mobile and desktop use optimized candidates, thumbnails and quick view remain
optimized, and the original is downloaded only when the customer opens zoom.
No JavaScript or content-security-policy errors were observed in these checks.

## Reversible cleanup

Six obsolete WebP caches, two unused SVG illustrations, the inactive local
Python 3.14.10 runtime and the unused `.runtime/imagegen` SDK environment were
moved out of the served/active folders, into
`.velora/cleanup-archive/2026-11-11/`. The launcher and runtime lock select
Python 3.15.2; the active application remained healthy during the move.

The SDK environment contained the OpenAI SDK and 13 supporting packages:
4,772 files totalling 35,160,404 bytes. Repository imports and runtime paths do
not use this legacy environment; current application API calls use the Python
standard library. Metadata inspection found no linked files or directories.
No environment keys or configuration contents were read, and the active
Python 3.15.2 runtime and global Python packages were left intact.

The archive removes 60,745,026 bytes from the public/active tree, including
1,133,568 bytes of unused images. Nothing was permanently deleted. The
[cleanup manifest](../json/reports/asset-cleanup-manifest.json) records original and
archive paths, image hashes, byte counts and restoration instructions. Restore
only to an absent original path after verifying the intended workspace target.

Byte-identical files that still have referenced URLs were retained. A duplicate
hash alone is not sufficient reason to break a product's saved image link.
Newly superseded responsive hashes are retained during the browser-cache grace
period so existing tabs can finish using an older manifest.

## Repeatable audit

`py/tools/audit-assets.py` checks source references, public and draft product photo
fields, the web manifest, dynamic team portraits, creation/rights records and
responsive candidates. It reads no credentials, account records or private
department documents. Its report is
[json/reports/asset-dependency-audit.json](../json/reports/asset-dependency-audit.json).

Before future removal, inspect references across all these sources, not only
HTML. After regenerating responsive images, refresh static sources with
`py/tools/prepare-site-pages.py`, verify the manifest and run the image-delivery
browser check. Keep current hashes and any hashes still needed by cached pages.
