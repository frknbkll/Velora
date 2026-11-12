# Velora

A local fashion storefront, product administration, colleague workspace and
design school. The frontend uses HTML, CSS and JavaScript; the account/catalog
server uses Python's standard library and SQLite. No npm install is required.

## Start

On Windows, double-click **Start-Velora.cmd**, or run from this folder:

```powershell
.\.runtime\python-3.15.2\python.exe -I py/launch/start-velora.py
```

Open [Velora](http://127.0.0.1:8000). The launcher reuses a running server. Run
**Update-VeloraRuntime.cmd** if the bundled runtime is missing. Current minimums
are Python 3.14.10 or 3.15.2; the launcher enforces the supported release family.

## Project map

| Location | Purpose |
| --- | --- |
| `html/` | Website pages; public addresses such as `/product.html` stay the same |
| `css/` | Website stylesheets, grouped by feature filename |
| `js/` | Browser code, with `vendor/` and `tests/` subfolders |
| `py/app/` | Account, catalog, commerce, security and folder APIs |
| `py/launch/` | App launcher and pinned-runtime installer |
| `py/tools/` | Python audits, image preparation and catalog maintenance |
| `py/tests/` | Disposable-data API tests and isolated browser checks |
| `json/` | Catalog, configuration, creative records, maps and reports |
| `assets/` | Public originals, generated item photos, responsive WebP, fonts and licenses |
| `docs/` | Setup, administration, launch, security and image-maintenance guides |
| `tools/` | PowerShell maintenance utilities |
| `output/` | Image exports and notes; JSON reports live in `json/reports/` |
| `.velora/` | Private database, keys, shared files, backups and reversible cleanup archive; ignored |
| `.runtime/` | Isolated Windows app runtime; ignored |
| `tmp/` | Disposable preview/test artifacts; ignored |

Public assets and private data have separate serving boundaries. Documentation,
creative briefs, source code and private state are not served by the app. The
live product database may contain changes newer than `json/catalog/product-catalog.json`;
maintenance tools must inspect both before removing images.

## Development

The app requires no pip packages. Optional image preparation and media tests
need the pinned Pillow dependency in [requirements-tools.txt](requirements-tools.txt).
Use a separate developer Python environment for those tools, not the embedded
application runtime:

```powershell
py -3.14 -m pip install -r requirements-tools.txt
py -3.14 py/tools/prepare-responsive-images.py
py -3.14 py/tools/prepare-site-pages.py
py -3.14 -m unittest discover -s py/tests -p "test_*.py"
```

Existing tools-only dependencies can be reused; installation is unnecessary when
the pinned version is already present. Image preparation preserves originals
and prefers verified matching lossless masters when available. Do not upscale
photos or regenerate product details to disguise a weak source.

The GitHub workflow runs the same standard-library test suite and scanner
self-test. Browser scripts in `py/tests/run-*.py` additionally need local Chrome;
they use temporary profiles and disposable data.

## Guides

- [Folder structure and file locations](docs/FOLDER_STRUCTURE.md)
- [Completed project review](docs/PROJECT_REVIEW.md)
- [Accounts and setup](docs/ACCOUNT_SETUP.md)
- [Admin operations](docs/ADMIN_OPERATIONS.md)
- [Launch setup and hosting limits](docs/LAUNCH_SETUP.md)
- [Account security](SECURITY.md) and [security audit](docs/SECURITY_AUDIT.md)
- [Third-party inventory](docs/THIRD_PARTY_AUDIT.md)
- [Image provenance](docs/IMAGE_RIGHTS.md)
- [Image quality, cleanup and dependencies](docs/ASSETS_AND_DEPENDENCIES.md)

This is a local development application. Public hosting requires the production
hosting, HTTPS, email and operational work described in the launch/security
guides. The local app does not process real payments.
