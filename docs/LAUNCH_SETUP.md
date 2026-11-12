# Velora public-page setup

The public origin is configured as **https://velora.org** in `json/config/site-config.json`.
This configures URLs; it does not register the domain, configure DNS/TLS, or publish
the local application.

## Metadata and discovery

Every root HTML page has a title, description, icon links and sharing metadata.
Published product pages receive their current title, description, canonical URL
and product image in the initial HTML response. Variant, tracking and preview
parameters do not create separate canonical product URLs. Unpublished, deleted,
unknown or duplicate product identifiers return a 404 response with noindex
metadata and no product details in the head.

The server provides these routes:

- `/robots.txt`: local and alternate-host previews disallow crawling. On the
  configured HTTPS origin, public pages and required public catalog/review data
  can be crawled. Authentication remains the protection for private data.
- `/sitemap.xml`: generated from the current published, non-deleted catalog and
  the explicit public-page list. Publishing or unpublishing a product updates it
  without a manual rebuild. Account, admin, intranet, sign-in, registration,
  unsubscribe and error pages are excluded.
- `/site.webmanifest` and `/favicon.ico`: the manifest and icon entry point.
  The manifest uses normal browser display; it does not claim offline or
  installable-app functionality.

Local responses have `X-Robots-Tag: noindex, nofollow`. Private account/workspace
pages and API responses retain noindex headers on the public origin as well.
Robots instructions do not grant or restrict access permissions.

The existing local Python server is a development server, not a production
hosting stack. When using the documented trusted HTTPS endpoint mode,
`--secure-cookies` permits only the configured public hostname in addition to the
local bind host. Other Host values remain rejected. Do not enable this mode on a
plain HTTP visitor-facing site. See `ACCOUNT_SETUP.md` and `SECURITY.md` for the
existing hosting requirements. A maintained production server should preserve
the same metadata, discovery and authentication behavior.

`--public-url https://velora.org` can override the config for a server instance.
The origin must be HTTPS and cannot contain credentials, a path, query or
fragment. Request Host values are never used to create public canonical URLs.

## Brand assets

`assets/brand/` contains the SVG/ICO/PNG favicon set, Apple touch and maskable
icons, and the 1200 × 630 sharing card. Public product links use their current
product photo instead of the generic brand card. Graphics use the existing
bundled fonts and palette; their dimensions and attribution are documented in
`assets/brand/README.md`.

## Image preparation and page templates

Run these from the project folder after changing public images or templates:

```powershell
py -3.14 py/tools/prepare-brand-assets.py
py -3.14 py/tools/prepare-responsive-images.py
python py/tools/prepare-site-pages.py
```

Only the two image preparation tools need Pillow; it is installed in this
workspace's Python 3.14 runtime. The web server remains standard-library Python.
Image preparation keeps originals unchanged. It generates real-width WebP
candidates without upscaling. Static image markup and dynamic product, team,
careers and admin thumbnails use those candidates; explicit product zoom still
loads the original. Newly uploaded photos fall back to their original source
until the image preparation tool is run again. Existing generated files are not
automatically deleted.

The page tool is repeatable. It updates the managed metadata/icon blocks and
static responsive image sources while preserving other page content. New public
pages need an entry in `seo.PAGES`; utility/private pages must remain excluded
from the sitemap. Meaningful images have descriptive alt text; decorative images
and labelled thumbnail controls retain empty alt text to avoid repetition.

## Product controls and current limits

On mobile, product pages show the name, euro price and options link before the
full photo. The sticky action requires an explicit size choice, reflects current
stock, and stays clear of the privacy banner and support controls. Product/API
and photograph failures offer retry actions.

In Admin Studio, a new product's first cover photo and each alternate-color
upload fill in a color name and swatch automatically. Detection runs locally in
the browser without an external service. It estimates the visible garment color;
mixed outfits, prints and difficult lighting may need a correction. Unclear
images leave the color for manual entry. Manual corrections and saved product
colors are preserved when adding gallery photos. Use **Detect from cover photo**
to explicitly check a primary color again.

Product pages and homepage quick view now offer **Zoom photo** (or click the
photo). The viewer opens the original image, with zoom in/out, fit, scroll and
mouse drag controls. Click a pulsing object marker to reveal the linked product,
its current euro price and **View item**. Markers are attached to one exact
photograph, so another pose or color does not inherit misplaced dots. Reduced
motion disables the animations.

In **Admin Studio → Products → Edit → Shop the photo**, choose the photograph,
click an object (or enter percentage coordinates), select a published product,
and choose **Add marker**, then **Save changes**. The marker can be edited or
removed. Draft or trashed linked products disappear from public markers; prices
come from the current product record. Marker changes remain in the editor until
the product is saved.

The approved accessory examples are linked from the Espresso Tailored Suit:
Espresso Top-Handle Bag (€49), Nude Pointed Court Shoes (€59, illustrative EU
36–42), and Taupe Draped Scarf (€19). Names, prices, sizes and photos are editable
in Products. Each has its own generated item photo. The full outfit remains one
collection card, with individual items grouped underneath it in **Shop this
look**. These are showcase examples, with unconfirmed materials, fit and
availability. Existing collection data and prices are preserved.

This grouping applies across the reviewed outfit catalog. Individual items keep
separate product IDs for their prices, sizes, stock, wishlists and shopping bags;
they do not repeat the outfit's full-model photo as separate collection cards.
Shared matching pieces can appear in more than one outfit. Each original look
keeps its full styling photo, and its generated primary-piece photo is added to
the gallery. **View piece** opens that photo directly. Item pages link back to
their outfit. Cards and markers follow the selected source photograph; an
unannotated color or pose does not inherit another photo's item list.

Admin product editors include **Part of an outfit** and **Individual product
photo**. The latter selects an image already in that product's gallery. Removing
the selected image clears its reference; prices and stock are independent of
these grouping controls. Outfit parents cannot be nested into their own items.

The reviewed visual plan and exact built-in generation prompts are saved in
`json/reports/outfit-items-manifest.json`; generated assets live in
`assets/generated-items/`. Per-image provenance and SHA256 review records live
under `output/image-generation-*.json` and `json/reports/outfit-items-image-qa.json`.
The images reconstruct visible design details from the styling references;
hidden construction, measurements and materials remain unconfirmed.

`python py/tools/apply-outfit-items.py` previews ready and pending outfits.
`--apply --ready-only` applies complete, approved outfits; `--apply` requires all
planned outfits to be ready. The tool checks reviewed file hashes, backs up the
database, saves a transaction journal, and preserves later owner edits on repeat
runs. It also synchronizes setup changes to the default seed catalog without
replacing unrelated seed edits. `json/reports/applied-outfit-items.json` mirrors the
private database journal for review and recovery.

`python py/tools/add-accessory-examples.py` previews the example setup;
`--apply` adds missing records and markers after the new server schema is
running. It backs up the database under the private `.velora/backups` directory,
records product activity, and preserves existing example prices and placements.

Checkout remains a clearly labelled preview. No real-order thank-you page,
payment collection, analytics, advertising tags or tracking provider has been
added. Choosing an analytics provider and measurement plan would require a
separate privacy/preferences update.

## Verification

```powershell
python -m unittest discover -s py/tests -p test_seo_server.py
python py/tests/run-product-launch-ux.py
python py/tests/run-image-delivery.py
python py/tests/run-team-portraits.py
node js/tests/test-product-color-detection.cjs
python py/tests/run-admin-auto-color.py
python -m unittest discover -s py/tests -p test_image_hotspots_server.py
python py/tests/run-shoppable-images.py
python -m unittest discover -s py/tests -p test_outfit_items_server.py
python -m unittest discover -s py/tests -p test_outfit_items_setup.py
python py/tests/run-outfit-items.py
python py/tests/run-outfit-admin.py
py -3.14 py/tools/prepare-responsive-images.py --verify
```

API and product tests use disposable databases. The image/team checks use
isolated browser profiles and read public pages from the running local app.
