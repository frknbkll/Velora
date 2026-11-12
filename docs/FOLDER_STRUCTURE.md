# Folder structure

Velora's first-party source files are grouped by file type. Feature names such
as `admin-folder-access`, `product-page` and `school-3d` make related browser
files easy to find across the folders.

```text
Velora/
  html/                   Website pages
    index.html            Homepage
    product.html          Product details
    admin.html            Admin panel
    preview/              Standalone launch hint
    tests/                Legacy visual test page
  css/                    All website stylesheets
  js/                     All browser JavaScript
    vendor/               Bundled QR and Three.js modules
    tests/                JavaScript test runner
  py/
    app/                  Backend modules and source-path resolver
    launch/               App launcher and runtime installer
    tools/                Audits, imports and image preparation
    tests/                Python API and browser test runners
  json/
    catalog/              Product seed and copy updates
    config/               Public-origin settings and runtime pin
    creative/             Image prompts and generation records
    departments/          Department document templates
    maps/                 World-map data and provenance
    media/                Image-rights register
    vendor/               Bundled library provenance and hashes
    reports/              Review plans, snapshots and audit results
    migrations/           File move manifest
  assets/                 Images, fonts, icons and licenses
  docs/                   Setup, operation and review guides
  tools/                  PowerShell utility
  output/                 Exported images and human-readable notes
  Start-Velora.cmd        Start the app
  Update-VeloraRuntime.cmd
  README.md
```

## Run the website

Double-click **Start-Velora.cmd**, or run from the project root:

```powershell
.\.runtime\python-3.15.2\python.exe -I py/launch/start-velora.py
```

Open http://127.0.0.1:8000. Public addresses stay `/`, `/product.html`,
`/admin.html` and so on; the backend resolves those pages from `html/`.
Stylesheets and scripts use `/css/` and `/js/` URLs. Open pages through the app
server so accounts, catalog routes and source paths work together.

## Maintenance

Run Python tools from the project root with their full path:

```powershell
py -3.14 py/tools/prepare-responsive-images.py
py -3.14 py/tools/prepare-site-pages.py
py -3.14 -m unittest discover -s py/tests -p "test_*.py"
```

The source-path helper supports intentionally flat disposable test fixtures.
This compatibility does not expose physical `html/` or Python source paths over
HTTP. JSON configuration, draft data and reports remain private; only the
explicit public map-data route is served.

## Files kept in conventional locations

`.vscode/launch.json` stays under `.vscode/` so the IDE can find it.
`site.webmanifest`, the Windows command launchers and repository configuration
also retain their normal entry-point locations. The ignored `.runtime/`,
`.velora/` and `tmp/` folders contain interpreter files, private state and
temporary test artifacts; their internal files are not part of the source
reorganization. The existing database, security key, uploaded images and private
department documents stay in place.
