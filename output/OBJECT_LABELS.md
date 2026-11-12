# Product photo object labels

Applied on 10–11 November 2026 to the local Velora website and Admin Products.

The live catalog contains 266 products and 514 displayable product-photo
placements, including standalone item images, gallery poses and color variants
from the global photo presets. Every existing displayable photo has at least
one clickable object label. There are 864 saved label points in total.

The reviewed plan added 307 points on 303 previously unlabelled photos, including
the newly added Champagne Satin Gown and its three alternate photos. Reviewed
corrections on 130 photos removed 268 copied labels for absent or mismatched
objects and placed the remaining labels on visible fabric/accessories. All 86
generated primary garment photos now show only their own product label.
Unreviewed custom markers, product names, prices, stock, sizes, colors and
relationships were preserved. Three gallery entries pointing to nonexistent
standalone files were removed; their working cover photos were retained. The
original entries remain in the catalog snapshots and private database backups.

Labels display the linked product's current price. A garment's own label on an
alternate color keeps the selected color in its product link. Text labels stay
within the displayed photo on homepage collection cards, product pages, quick
view and zoom. Collection labels follow color/pose selections and retain normal
photo links, gallery controls and wishlist buttons. Small price cards scroll
when necessary so their product links remain reachable. Admin supports up to
24 labels per photo and 288 across a product's gallery.

Targeted validation passed: 5 application-safety tests, 9 backend marker tests,
25 admin browser checks, 59 label/zoom checks, 21 grouped-item checks and 14
image-delivery checks. Read-only live review passed 35 product-page checks and
21 homepage checks at desktop and mobile widths, plus 10 checks of corrected
item-only/hanger photos and 10 checks of the newly added dress. Responsive image
preparation verified 647 originals
and 1,665 WebP candidates. An unrelated existing AI-draft catalog test fixture
uses an outdated draft schema; AI generation code was not changed.

- [Reviewed positions](../json/reports/object-label-photo-plan.json)
- [Photo coverage review](../json/reports/object-label-photo-coverage.json)
- [Application report and private backup location](../json/reports/object-label-apply.json)
- [Reviewed corrections](../json/reports/object-label-corrections.json)
- [Correction application report](../json/reports/object-label-corrections-apply.json)
- [New dress application report](../json/reports/object-label-final-additions-apply.json)
- [Final live catalog audit](../json/reports/object-label-final-audit.json)

`python py/tools/apply-object-labels.py` previews the reviewed plan. `--apply`
backs up the private database and adds missing labels in one transaction.
Reviewed corrections require an exact match with the saved pre-review labels;
later manual edits cause the operation to stop instead of being overwritten.
Repeat applications make no further changes. The final audit found no unlabelled
photos, broken photo references, invalid product links, unexpected metadata
changes or changes to unreviewed markers.
Manual edits are available in Admin Products through the photo-marker editor.
