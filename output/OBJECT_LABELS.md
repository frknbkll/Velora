# Product photo object labels

Applied on 10 November 2026 to the local Velora website and Admin Products.

The live catalog contains 265 products and 510 displayable product-photo
placements, including standalone item images, gallery poses and color variants
from the global photo presets. Every existing displayable photo has at least
one clickable object label. There are 1,128 saved label points in total.

The reviewed plan added 303 points on 299 previously unlabelled photos. Existing
markers, product names, prices, stock, sizes, colors and relationships were
preserved. Two gallery entries pointing to nonexistent standalone files were
removed; their working cover photos were retained. The original entries remain
in the catalog snapshot and database backup.

Labels display the linked product's current price. A garment's own label on an
alternate color keeps the selected color in its product link. Text labels stay
within the displayed photo on homepage collection cards, product pages, quick
view and zoom. Collection labels follow color/pose selections and retain normal
photo links, gallery controls and wishlist buttons. Small price cards scroll
when necessary so their product links remain reachable. Admin supports up to
24 labels per photo and 288 across a product's gallery.

Targeted validation passed: 4 application-safety tests, 9 backend marker tests,
25 admin browser checks, 57 label/zoom checks, 21 grouped-item checks and 14
image-delivery checks. Read-only live product-page review passed 35 checks at
desktop and mobile widths. Responsive image preparation verified 647 originals
and 1,665 WebP candidates. An unrelated existing AI-draft catalog test fixture
uses an outdated draft schema; AI generation code was not changed.

- [Reviewed positions](object-label-photo-plan.json)
- [Photo coverage review](object-label-photo-coverage.json)
- [Application report and private backup location](object-label-apply.json)
- [Final live catalog audit](object-label-final-audit.json)

`python tools/apply-object-labels.py` previews the reviewed plan. `--apply`
backs up the private database and adds missing labels in one transaction.
Repeat applications preserve existing photo labels and make no further changes.
Manual edits are available in Admin Products through the photo-marker editor.
