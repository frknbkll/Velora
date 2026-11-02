"""Verify catalog administration and galleries using isolated Chrome/server data.

Run ``python tests/run-catalog-browser.py`` from the project root. The real account
database and uploaded assets are never opened or changed by this runner.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import runpy
import secrets
import shutil
import tempfile
import threading
import time


ROOT = Path(__file__).resolve().parent.parent
helpers = runpy.run_path(str(ROOT / "tests" / "run-account-browser.py"))
Checks = helpers["Checks"]
start_chrome = helpers["start_chrome"]


class CatalogChecks(Checks):
    def choose(self, selector, value):
        self.evaluate(f"""(() => {{
            const field = document.querySelector({json.dumps(selector)});
            field.value = {json.dumps(value)};
            field.dispatchEvent(new Event('input', {{bubbles:true}}));
            field.dispatchEvent(new Event('change', {{bubbles:true}}));
        }})()""")

    def sizes(self, selected):
        self.evaluate(f"""(() => {{
            const selected = {json.dumps(selected)};
            document.querySelectorAll('#admin-edit-form input[name="sizes"]').forEach(input => {{
                input.checked = selected.includes(input.value);
                input.dispatchEvent(new Event('change', {{bubbles:true}}));
            }});
        }})()""")

    def upload(self, files, selector="#admin-image-files"):
        root = self.connection.call("DOM.getDocument")
        node = self.connection.call("DOM.querySelector", {
            "nodeId": root["root"]["nodeId"], "selector": selector,
        })
        self.connection.call("DOM.setFileInputFiles", {
            "nodeId": node["nodeId"], "files": [str(path) for path in files],
        })

    def product_api(self, product_id):
        return self.evaluate(f"""window.VeloraAuth.request('/api/admin/products').then(data =>
            data.products.find(product => product.id === {json.dumps(product_id)}))""")

    def products_view(self, search="", visibility="all"):
        self.navigate("admin.html#products", ready="document.querySelector('#admin-shell') && !document.querySelector('#admin-shell').hidden && document.querySelector('#admin-total-products').textContent !== '—'")
        self.fill_search("#admin-product-search", search)
        self.choose("#admin-product-filter", visibility)

    def card_expression(self, name):
        return f"Array.from(document.querySelectorAll('.look-tile')).find(card => card.querySelector('.look-tile-caption strong')?.textContent === {json.dumps(name)})"

    def store(self):
        self.navigate("index.html", ready="window.veloraCatalogReady && document.documentElement.dataset.catalogState === 'managed'")
        # This scenario verifies explicitly requested persistence across navigation.
        self.evaluate("document.querySelector('#privacy-banner [data-privacy-choice=\"saved\"]')?.click()")
        self.show_all_store_products()

    def card_action(self, name, selector):
        self.evaluate(f"{self.card_expression(name)}.querySelector({json.dumps(selector)}).click()")

    def editor_widths(self, label):
        self.check_widths(label)
        for width in (320, 390, 768, 1366, 1920):
            self.viewport(width)
            dimensions = self.evaluate("""(() => {
                const dialog=document.querySelector('#admin-edit-dialog'), rect=dialog.getBoundingClientRect();
                return {left:rect.left,right:rect.right,scroll:dialog.scrollWidth,client:dialog.clientWidth};
            })()""")
            self.check(dimensions["left"] >= -1 and dimensions["right"] <= width + 1, f"{label}: dialog fits the viewport at {width}px")
            self.check(dimensions["scroll"] <= dimensions["client"] + 1, f"{label}: dialog content does not overflow at {width}px")

    def color_dialog_widths(self, label):
        for width in (320, 390, 768, 1366):
            self.viewport(width)
            dimensions = self.evaluate("""(() => {
                const dialog=document.querySelector('#admin-color-dialog'), rect=dialog.getBoundingClientRect();
                return {left:rect.left,right:rect.right,scroll:dialog.scrollWidth,client:dialog.clientWidth};
            })()""")
            self.check(dimensions["left"] >= -1 and dimensions["right"] <= width + 1, f"{label}: dialog fits the viewport at {width}px")
            self.check(dimensions["scroll"] <= dimensions["client"] + 1, f"{label}: dialog content does not overflow at {width}px")


def prepare_root(temporary):
    root = temporary / "site"
    root.mkdir()
    for pattern in ("*.html", "*.css", "*.js"):
        for source in ROOT.glob(pattern):
            shutil.copy2(source, root / source.name)
    products = json.loads((ROOT / "product-catalog.json").read_text(encoding="utf-8"))["products"][:2]
    for product in products:
        target = root / product["image"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / product["image"], target)
    # Keep the hero present for clean previews while avoiding a copy of the large catalog.
    for filename in ("hero-founders-1920.jpg", "hero-founders-3840.jpg", "hero-founders-8k.jpg"):
        source = ROOT / "assets" / filename
        if source.is_file():
            shutil.copy2(source, root / "assets" / filename)
    (root / "product-catalog.json").write_text(json.dumps({"products": products}), encoding="utf-8")
    incoming = temporary / "incoming-images"
    incoming.mkdir()
    files = []
    for index, product in enumerate(products):
        target = incoming / f"gallery-angle-{index + 1}.jpg"
        shutil.copy2(ROOT / product["image"], target)
        files.append(target)
    return root, products, files


def run_scenarios(checks, email, password, files):
    name = "The Browser Verification Jacket"
    renamed = "The Updated Browser Verification Jacket"
    sku = "QA-JACKET-2026"
    description = "A thoughtfully detailed jacket with two complementary gallery photographs."

    checks.navigate("login.html", ready="window.VeloraAuth && document.querySelector('#login-form')")
    checks.fill("#login-form", {"email": email, "password": password})
    checks.submit("#login-form")
    checks.wait("location.pathname === '/admin.html' && document.querySelector('#admin-shell') && !document.querySelector('#admin-shell').hidden && document.querySelector('#admin-total-products').textContent !== '—'")
    checks.check(True, "Administrator can sign in to the isolated catalog")
    checks.click('[data-admin-section="products"]')
    checks.check_widths("Catalog product table")
    checks.click("#admin-add-product")
    checks.wait("document.querySelector('#admin-edit-dialog').open")
    checks.check(not checks.evaluate("document.querySelector('#admin-edit-published').checked"), "New products start as drafts")
    checks.fill("#admin-edit-form", {
        "name": name, "sku": sku, "founder": "Victoria Mendez", "collection": "THE EVERYDAY EDIT",
        "price": "87.49", "description": description, "stock": "4", "base_color": "Sand", "color_hex": "#c9b8a1", "published": True,
    })
    checks.sizes(["XS", "M", "XL"])
    checks.upload(files)
    checks.wait("document.querySelectorAll('#admin-image-gallery > [data-image-index]').length === 2 && !document.querySelector('#admin-edit-save').disabled", timeout=25)
    checks.check(True, "Two selected image files upload and appear in the editor")
    original_images = checks.evaluate("Array.from(document.querySelectorAll('#admin-image-gallery > [data-image-index] img'), image => image.getAttribute('src'))")
    checks.check(len(set(original_images)) == 2, "Uploaded gallery files have distinct stored image paths")
    checks.click('[data-image-action="right"][data-image-index="0"]')
    checks.check(checks.evaluate("document.querySelector('#admin-image-gallery > [data-image-index] img').getAttribute('src')") == original_images[1], "The reorder-right action moves a photo to the next position")
    checks.click('[data-image-action="left"][data-image-index="1"]')
    checks.check(checks.evaluate("document.querySelector('#admin-image-gallery > [data-image-index] img').getAttribute('src')") == original_images[0], "The reorder-left action restores the photo order")
    checks.click('[data-image-action="remove"][data-image-index="1"]')
    checks.check(checks.evaluate("document.querySelectorAll('#admin-image-gallery > [data-image-index]').length") == 1, "A gallery photo can be removed before saving")
    checks.upload([files[1]])
    checks.wait("document.querySelectorAll('#admin-image-gallery > [data-image-index]').length === 2 && !document.querySelector('#admin-edit-save').disabled", timeout=25)
    original_images = checks.evaluate("Array.from(document.querySelectorAll('#admin-image-gallery > [data-image-index] img'), image => image.getAttribute('src'))")
    checks.click('[data-image-action="cover"][data-image-index="1"]')
    cover = checks.evaluate("document.querySelector('#admin-image-gallery > [data-image-index] img').getAttribute('src')")
    checks.check(cover == original_images[1], "Choosing a cover photo moves it to the first position")
    ai_description = "A polished, modern jacket with a clean silhouette and considered detailing."
    checks.evaluate("""(() => {
        const original = window.VeloraAuth.request;
        window.__catalogOriginalRequest = original;
        window.__catalogDescriptionRequest = null;
        window.VeloraAuth.request = async (path, options) => {
            if (path === "/api/admin/product-description") {
                window.__catalogDescriptionRequest = options.body;
                return {description: "A polished, modern jacket with a clean silhouette and considered detailing."};
            }
            return original.call(window.VeloraAuth, path, options);
        };
    })()""")
    checks.click("#admin-generate-description")
    checks.wait("document.querySelector('#admin-edit-description').value === 'A polished, modern jacket with a clean silhouette and considered detailing.'")
    generated_request = checks.evaluate("window.__catalogDescriptionRequest")
    checks.check(generated_request["name"] == name and generated_request["collection"] == "THE EVERYDAY EDIT" and generated_request["base_color"] == "Sand" and generated_request["image"] == cover, "AI draft uses the current product details and selected cover photo")
    checks.check(checks.evaluate("document.querySelector('#admin-description-status').textContent.includes('Review and edit')"), "AI-generated copy is identified as a reviewable, unsaved draft")
    checks.evaluate("window.VeloraAuth.request = window.__catalogOriginalRequest; delete window.__catalogOriginalRequest;")
    description = ai_description
    checks.editor_widths("Product editor with uploaded gallery")
    checks.screenshot("catalog-editor-desktop.png", 1366, 900)
    checks.screenshot("catalog-editor-mobile.png", 390, 844)
    checks.submit("#admin-edit-form")
    checks.wait("!document.querySelector('#admin-edit-dialog').open", timeout=25)
    products = checks.evaluate("window.VeloraAuth.request('/api/admin/products').then(data => data.products)")
    created = next((product for product in products if product["sku"] == sku), None)
    checks.check(created is not None, "Saving the form creates a product in the catalog")
    product_id = created["id"]
    checks.check(created["name"] == name and created["price"] == 87.49 and created["stock"] == 4, "Identity, cents and stock persist after creation")
    checks.check(created["sizes"] == ["XS", "M", "XL"], "The selected product sizes persist")
    checks.check(len(created["images"]) == 2 and created["image"] == cover, "The ordered gallery and chosen cover persist")
    checks.click("#admin-add-color")
    checks.wait("document.querySelector('#admin-color-dialog').open")
    checks.color_dialog_widths("Add color dialog")
    checks.choose("#admin-color-product", product_id)
    checks.fill("#admin-color-form", {"admin-color-name": "Midnight"})
    checks.evaluate("document.querySelector('#admin-color-hex').value='#252321'; document.querySelector('#admin-color-hex').dispatchEvent(new Event('input',{bubbles:true}))")
    checks.upload([files[1]], "#admin-color-image-file")
    checks.wait("!document.querySelector('#admin-color-save').disabled && !document.querySelector('#admin-color-image-preview').hidden", timeout=25)
    checks.submit("#admin-color-form")
    checks.wait("!document.querySelector('#admin-color-dialog').open", timeout=25)
    created = checks.product_api(product_id)
    color_variant = created["color_variants"][0] if created["color_variants"] else {}
    checks.check(len(created["color_variants"]) == 1 and color_variant.get("name") == "Midnight" and color_variant.get("hex") == "#252321" and color_variant.get("image") not in created["images"], "Adding a color links its swatch and separate photo to the explicitly selected product")
    checks.choose("#admin-stock-filter", "low")
    checks.check(sku in checks.evaluate("document.querySelector('#admin-products-body').textContent"), "The low-stock filter includes the product with four units")
    checks.choose("#admin-stock-filter", "all")
    checks.fill_search("#admin-product-search", sku)
    checks.check(checks.evaluate("document.querySelectorAll('#admin-products-body tr').length") == 1, "Product search finds a SKU")

    checks.store()
    checks.check(checks.evaluate(f"Boolean({checks.card_expression(name)})"), "A newly created published product appears in the actual storefront")
    checks.check(checks.evaluate(f"Array.from({checks.card_expression(name)}.querySelectorAll('.product-color-option'),button=>button.title).some(title=>title==='Midnight')"), "The added product color appears as a storefront swatch")
    rendered = checks.evaluate(f"{checks.card_expression(name)}.textContent")
    checks.check("87.49" in rendered and description in rendered, "The storefront shows the saved price and description")
    card = checks.card_expression(name)
    checks.check(checks.evaluate(f"{card}.dataset.productId") == product_id, "The card carries the managed product ID")
    checks.check(checks.evaluate(f"Array.from({card}.querySelectorAll('.product-size-option'), button => button.textContent)") == ["XS", "M", "XL"], "The card only offers the saved available sizes")
    checks.check(checks.evaluate(f"{card}.querySelector('.product-size-option[aria-pressed=\"true\"]').textContent") == "M", "The saved available default size is selected")
    gallery = f"{card}.querySelector('.product-gallery')"
    first_photo = checks.evaluate(f"{gallery}.querySelector('[data-gallery-main]').getAttribute('src')")
    checks.card_action(name, '[data-gallery-action="next"]')
    second_photo = checks.evaluate(f"{gallery}.querySelector('[data-gallery-main]').getAttribute('src')")
    checks.check(first_photo != second_photo, "The product card next button changes the displayed photo")
    checks.check("2 / 2" in checks.evaluate(f"{gallery}.querySelector('.product-gallery-count').textContent"), "The gallery count follows the current photo")
    checks.card_action(name, '[data-gallery-action="previous"]')
    checks.check(checks.evaluate(f"{gallery}.querySelector('[data-gallery-main]').getAttribute('src')") == first_photo, "The previous button returns to the cover photo")
    checks.card_action(name, '[data-gallery-index="1"]')
    checks.check(checks.evaluate(f"{gallery}.querySelector('[data-gallery-main]').getAttribute('src')") == second_photo, "The card thumbnail selects its corresponding photo")
    checks.card_action(name, ".look-quick-view")
    checks.wait("document.querySelector('#product-dialog').open")
    checks.check(checks.evaluate("document.querySelectorAll('#product-dialog [data-gallery-index]').length") == 2, "Quick view includes both gallery thumbnails")
    checks.click('#product-dialog [data-gallery-index="0"]')
    checks.click('#product-dialog [data-gallery-action="next"]')
    checks.check(checks.evaluate("document.querySelector('#product-dialog .product-dialog-image').getAttribute('src')") == second_photo, "Quick-view gallery changes to the selected second photo")
    checks.evaluate("document.querySelector('#product-dialog').close()")
    checks.check_widths("Storefront with managed product gallery")
    checks.card_action(name, ".save-look")
    checks.card_action(name, ".add-to-bag")
    old_key = checks.evaluate(f"{checks.card_expression(name)}.querySelector('.product-options').dataset.productKey")
    checks.products_view(sku)
    checks.click(f'[data-edit-product="{product_id}"]')
    checks.wait("document.querySelector('#admin-edit-dialog').open")
    checks.check(checks.evaluate("document.querySelectorAll('#admin-color-variants [data-remove-color]').length") == 1, "The editor lists saved alternate colors for management")
    checks.fill("#admin-edit-form", {"name": renamed, "stock": "0"})
    checks.click('[data-image-action="cover"][data-image-index="1"]')
    checks.submit("#admin-edit-form")
    checks.wait("!document.querySelector('#admin-edit-dialog').open")
    updated = checks.product_api(product_id)
    checks.check(updated["id"] == product_id and updated["name"] == renamed, "Editing the product name keeps its stable identity")
    checks.check(updated["stock"] == 0 and updated["image"] != cover, "Stock and a new cover save together")
    checks.store()
    checks.check(checks.evaluate(f"{checks.card_expression(renamed)}.querySelector('.product-options').dataset.productKey") == old_key, "Storefront identity survives a name and cover edit")
    checks.check(checks.evaluate(f"{checks.card_expression(renamed)}.querySelector('.save-look').getAttribute('aria-pressed')") == "true", "A saved product remains in the wishlist after editing")
    checks.check(checks.evaluate(f"{checks.card_expression(renamed)}.querySelector('.add-to-bag').disabled"), "An out-of-stock product cannot be added to the bag")
    checks.click('[data-shop-view="cart"]')
    checks.check(renamed in checks.evaluate("document.querySelector('#shop-dialog-content').textContent"), "The bag uses the product's current name after an edit")
    checks.evaluate("document.querySelector('#shop-dialog').close()")

    checks.products_view(sku)
    checks.choose("#admin-stock-filter", "out")
    checks.check(sku in checks.evaluate("document.querySelector('#admin-products-body').textContent"), "The out-of-stock filter reflects the saved inventory")
    checks.choose("#admin-stock-filter", "all")
    checks.click(f'[data-duplicate-product="{product_id}"]')
    checks.wait("Number(document.querySelector('#admin-total-products').textContent) === 4")
    checks.wait("document.querySelector('#admin-edit-dialog').open")
    checks.check(not checks.evaluate("document.querySelector('#admin-edit-published').checked"), "The duplicate opens as an unpublished draft for editing")
    checks.click("#admin-edit-cancel")
    all_products = checks.evaluate("window.VeloraAuth.request('/api/admin/products').then(data => data.products)")
    duplicate = next((product for product in all_products if product["id"] != product_id and product["name"].startswith(renamed)), None)
    checks.check(duplicate is not None and not duplicate["published"], "Duplicating a product creates a separate draft")
    checks.check(duplicate["sku"] != sku and duplicate["images"] == updated["images"], "A duplicate gets its own SKU and retains the ordered photos")
    checks.choose("#admin-product-filter", "all")
    checks.fill_search("#admin-product-search", sku)
    checks.click(f'[data-trash-product="{product_id}"]')
    checks.wait("document.querySelector('#admin-delete-dialog').open")
    checks.check(renamed in checks.evaluate("document.querySelector('#admin-delete-dialog').textContent"), "The deletion confirmation names the selected product")
    checks.click("#admin-delete-cancel")
    checks.check(checks.product_api(product_id)["deleted_at"] is None, "Cancelling deletion leaves the product active")
    checks.click(f'[data-trash-product="{product_id}"]')
    checks.click("#admin-delete-confirm")
    checks.wait("!document.querySelector('#admin-delete-dialog').open")
    checks.check(checks.product_api(product_id)["deleted_at"] is not None, "Confirmed deletion moves the product to trash")
    checks.store()
    checks.check(not checks.evaluate(f"Boolean({checks.card_expression(renamed)})"), "Trashed products disappear from the storefront")
    checks.products_view(sku, "trash")
    checks.click(f'[data-restore-product="{product_id}"]')
    checks.wait(f"!document.querySelector('[data-restore-product=\"{product_id}\"]')")
    restored = checks.product_api(product_id)
    checks.check(restored["deleted_at"] is None and not restored["published"], "Restoring a product keeps it as a draft")
    checks.choose("#admin-product-filter", "all")
    checks.click('[data-admin-section="activity"]')
    checks.wait("!document.querySelector('#admin-activity').hidden")
    activity = checks.evaluate("document.querySelector('#admin-activity-list').textContent")
    checks.check(renamed in activity and name in activity, "The activity log records the product changes")
    checks.check_widths("Catalog activity log")
    checks.products_view()
    downloads = files[0].parent.parent / "downloads"
    downloads.mkdir()
    checks.connection.call("Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": str(downloads)})
    checks.click("#admin-export-products")
    deadline = time.monotonic() + 10
    exported = []
    while time.monotonic() < deadline:
        exported = list(downloads.glob("*.csv"))
        if exported:
            break
        time.sleep(.1)
    checks.check(bool(exported), "Catalog export downloads a CSV file")
    csv = exported[0].read_text(encoding="utf-8-sig")
    checks.check(renamed in csv and sku in csv, "The CSV contains the current product name and SKU")


def main():
    (ROOT / "tmp").mkdir(exist_ok=True)
    spec = importlib.util.spec_from_file_location("catalog_browser_server", ROOT / "server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.VeloraHandler.log_message = lambda *args: None
    with tempfile.TemporaryDirectory(prefix="catalog-browser-", dir=ROOT / "tmp", ignore_cleanup_errors=True) as directory:
        temporary = Path(directory)
        site, products, files = prepare_root(temporary)
        app = module.make_server(host="127.0.0.1", port=0, database=temporary / "catalog.sqlite3", catalog=site / "product-catalog.json", root=site)
        email, password = f"catalog-admin-{secrets.token_hex(6)}@example.test", secrets.token_urlsafe(24)
        with app.connect() as connection:
            connection.execute("INSERT INTO users (name,email,password_hash,role,created_at) VALUES (?,?,?,'admin',?)", ("Catalog Test Administrator", email, module.hash_password(password), module.now_iso()))
        serving = threading.Thread(target=app.serve_forever, daemon=True)
        serving.start()
        browser = connection = checks = None
        try:
            browser, connection = start_chrome(temporary / "chrome-profile")
            checks = CatalogChecks(connection, f"http://127.0.0.1:{app.server_port}")
            run_scenarios(checks, email, password, files)
            report = f"PASS: {len(checks.passed)} catalog browser checks\n" + "\n".join(checks.passed) + "\n"
            (ROOT / "tmp" / "catalog-browser-results.txt").write_text(report, encoding="utf-8")
            print(report.splitlines()[0])
        except BaseException as error:
            report = f"FAIL: {type(error).__name__}: {error}\nCompleted checks: {len(checks.passed) if checks else 0}\n"
            (ROOT / "tmp" / "catalog-browser-results.txt").write_text(report, encoding="utf-8")
            if checks:
                try:
                    size = checks.evaluate("({width:innerWidth,height:innerHeight})")
                    checks.screenshot("catalog-browser-failure.png", size["width"], size["height"])
                except Exception:
                    pass
            raise
        finally:
            if connection:
                connection.socket.close()
            if browser:
                browser.terminate()
                browser.wait(timeout=10)
            app.shutdown()
            app.server_close()
            serving.join(timeout=10)


if __name__ == "__main__":
    main()
