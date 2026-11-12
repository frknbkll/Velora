# Velora project review

Completed locally on 11 November 2026. The app is available at
http://127.0.0.1:8000; these changes have not been deployed to velora.org.

## Requested areas

| Area | Findings and changes |
| --- | --- |
| Folder structure | Moved 9 maintenance guides into `docs/`, 11 offline prompt/provenance manifests into `data/creative/`, and the color export script into `tools/`. Added a root README with setup and a project map. Updated cross-links, provenance references and the moved script's root resolution. Root files decreased from 125 to 107 despite the new entry-point guides/styles. Public page and product asset URLs remain stable. |
| Unused packages | The web app has no npm or pip runtime packages. Archived the unused project-local image-generation SDK environment, including 14 package folders, and the inactive bundled Python 3.14.10 runtime. The selected Python 3.15.2 runtime and global developer packages remain available. |
| Unused images | Checked source code, live/draft product photo records, global presets, dynamic image names, web manifest and creation records. Archived 8 confirmed unused images. Referenced duplicates and original creation masters remain available. Recently superseded WebP files remain during the cache grace period. |
| Image quality | Decoded the image inventory; found no corrupt files or undersized live product originals. Responsive preparation now uses 146 verified matching lossless masters, avoiding another JPEG compression pass. It preserves original URLs, framing, garment colors and marker coordinates. Verified 647 originals and 1,665 responsive candidates, without upscaling. |
| Missing dependencies | No missing application dependencies were found. Pinned the already available Pillow 13.0.0 as an optional developer-tool dependency in `requirements-tools.txt`. No unnecessary installation or global package removal was performed. |
| Website structure/security | Verified all 24 HTML pages, 120 local references, discovery routes and four 3D vendor modules. Confirmed existing authorization, department permissions, CSRF, session/MFA and private-file controls with disposable-data tests. Fixed the maintenance scanner so it does not open private environment/key files and added vendor integrity checks. Replaced the broken Conda workflow with the project's real unittest/scanner checks. |
| Visuals and 3D | Added an editorial discovery section with three live collection entry points. Improved 3D garment shaping and added Fabric/Construction inspection plus warm/daylight lighting. GLB/PNG exports, camera controls, mobile layout and 2D fallback remain available. These are concept meshes, not cloth simulation or sewing patterns. |
| Continued exploration | Collection previews use real current product counts, clear stale filters when selected and move keyboard focus to results. A studio link connects discovery to the design school. Mobile browsing uses compact image-and-text rows, while reduced-motion preferences are respected. These changes improve discovery; no claim about retention or sales lift has been measured. |

## Cleanup and recovery

The private recovery archive contains **60,745,026 bytes** moved out of the active
folders: 8 images and 2 old runtime/tooling environments. Archiving is reversible
and does not free that amount of disk space. Paths, hashes, package metadata and
restore instructions are recorded in
[the cleanup manifest](../json/reports/asset-cleanup-manifest.json).

The final media inventory includes retained cached sizes and creation masters.
Removing a file based solely on its absence from HTML or its duplicate hash
would break saved catalog paths or discard useful source material.

## Validation

- Full Python suite: **233 tests run; 232 passed, 1 skipped**. The skipped
  symbolic-link fixture needs Windows link-creation privileges. The existing AI
  response fixture was updated to the current 14-field schema; network calls
  remain mocked. Log: `tmp/maintenance-unittest-final.txt`.
- Discovery: **25 browser checks** at 320, 390, 768 and 1440 pixels.
- Image delivery: **14 browser checks**, including high-density screens and no
  original photo download before explicit zoom.
- Product photo labels: **21 final browser checks** on mobile/desktop. Catalog
  audit confirms all **514 product photos** retain labels, with no broken photo
  references, invalid targets or unintended product metadata changes.
- 3D browser suite: silhouettes, depth, camera/customization, construction and
  lighting changes, clean GLB export, PNG export, mobile and no-WebGL fallback
  passed. Representative final screenshots were visually inspected.
- Static structure audit: **24 pages / 120 references / 4 vendor modules**, no
  missing titles, alt attributes, source references or required response headers
  in the checked scope. See [the structure report](../json/reports/site-structure-review.json).
- Scanner self-test, vendor integrity and four image-master identity guards
  passed. Security verification details are in [the security audit](SECURITY_AUDIT.md).

The GitHub workflow is configured; it has not been executed on GitHub in this
session. It uses immutable action commits verified against the official
[checkout release](https://github.com/actions/checkout/releases/tag/v7.0.1) and
[setup-python release](https://github.com/actions/setup-python/releases/tag/v7.0.0).

## Remaining launch work

The local Python HTTP server remains a development server. Public launch still
needs a maintained production hosting stack with HTTPS and private persistent
storage, plus working email verification/recovery. Customer checkout remains a
no-charge preview. Actual operator details, image permissions, product details
and availability require confirmation before a real commercial launch. The
existing [launch guide](LAUNCH_SETUP.md) records these boundaries.

No credentials, real account contents or private department documents were
opened for this review. No production account roles, product prices or stock
were changed by the cleanup/design work.

Further details: [assets and dependencies](ASSETS_AND_DEPENDENCIES.md),
[third-party inventory](THIRD_PARTY_AUDIT.md), and
[project map](../README.md).
