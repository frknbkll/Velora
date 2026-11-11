# Outfit and individual-item images

Completed on 10 November 2026: all 86 outfit looks are applied to the local
website and Admin Products. The catalog contains 86 outfit records and 174
individual styling-item records, with 330 shopping-marker placements. The
homepage presents one collection card per outfit; its pieces are available
through **Shop this look**, photo markers and direct product links.

All 260 active standalone images passed visual review and file-hash checks.
Five rejected image versions are retained as superseded history. Existing
outfit names, prices, stock, sizes, cover photos and color variants were
preserved. Public catalog and seed consistency checks passed; see
[outfit-final-catalog-audit.json](outfit-final-catalog-audit.json) and
[outfit-final-assets-audit.json](outfit-final-assets-audit.json).

Responsive image preparation verified 644 public originals and 1,659 WebP
candidates, including every active generated item asset. The original images
remain available for explicit zoom. The final catalog application is recorded
in [outfit-final-apply.json](outfit-final-apply.json).

Validation passed: 19 backend/setup tests, 21 grouped-product browser checks,
19 admin checks, 14 image-delivery checks and 17 read-only live-site checks.
Live desktop and mobile review confirmed that all 86 homepage outfit cards
load, individual photos fit consistent 3:4 frames, and shopping markers and
separate item pages work. The item-card CSS explicitly overrides intrinsic
image heights so optimized photo dimensions cannot stretch the cards.

The outfit plan covers 86 looks and 330 visible item placements. Matching shared
pieces reduce this to 260 distinct item-image jobs. Originals are preserved.

Each look keeps one full-outfit collection card. Its primary item-only image is
an additional gallery photo. Separate styling pieces have their own product IDs
and standalone images, grouped under their outfit and reachable through the
photograph's shopping markers and **Shop this look** cards.

Generation uses the built-in image generation tool. No API key is needed for
this workflow. Exact prompts, references, product IDs and destination paths are
in [outfit-items-manifest.json](outfit-items-manifest.json). Final images are
saved in `assets/generated-items/`, inside the Velora project. Individual
`image-generation-*.json` records retain the original generation output path and
the actual prompt used. The original generated files are retained as well.

Image reviews are recorded with file SHA256 hashes in
[outfit-items-image-qa.json](outfit-items-image-qa.json). The setup tool only
publishes complete looks whose item files match approved hashes. These are
concept-store product images; small hidden construction details may be
reconstructed from the visible outfit, and material/fit information is not
inferred as fact.

`python tools/apply-outfit-items.py` previews readiness. Use
`python tools/apply-outfit-items.py --apply --ready-only` for completed looks
while generation continues, or `--apply` once all looks are ready. A private
database backup and transaction journal protect existing prices, stock and
owner edits. [applied-outfit-items.json](applied-outfit-items.json) mirrors the
setup journal.

After applying new files, run `py -3.14 tools/prepare-responsive-images.py` to
prepare smaller WebP downloads. Original item images remain available for zoom.
Generation worksets and records let an interrupted run skip files already saved.
