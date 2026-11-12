"""Regress session bags, currency and stock selection against disposable data."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

import base64
import json
from pathlib import Path
import runpy
import sys
import tempfile
import threading

import server

helpers = runpy.run_path(str(ROOT / "py/tests/run-account-browser.py"))
Checks, start_chrome = helpers["Checks"], helpers["start_chrome"]


def main():
    (ROOT / "tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="shopping-state-", dir=ROOT / "tmp", ignore_cleanup_errors=True) as directory:
        directory = Path(directory)
        image = "assets/careers/fashion-design-assistant.jpg"
        catalog = directory / "catalog.json"
        catalog.write_text(json.dumps({"products": [{
            "id": "bag-fixture", "name": "Session bag fixture", "image": image,
            "images": [image], "base_color": "Black", "color_hex": "#222222",
            "color_variants": [{"name": "Cream", "hex": "#eee7dc", "image": image}],
            "sizes": ["S", "M"], "price": 119.95, "stock": 2,
            "description": "A disposable shopping fixture.", "founder": "Velora",
            "collection": "THE LAYERING EDIT", "published": True,
        }]}), encoding="utf-8")
        app = server.make_server(port=0, database=directory / "accounts.sqlite3", catalog=catalog, root=ROOT)
        with app.connect() as db:
            db.execute("UPDATE products SET color_variants=? WHERE id='bag-fixture'", (json.dumps([{"name": "Cream", "hex": "#eee7dc", "image": image}]),))
        app.RequestHandlerClass.log_message = lambda *args: None
        serving = threading.Thread(target=app.serve_forever, daemon=True); serving.start()
        browser = connection = None
        try:
            browser, connection = start_chrome(directory / "chrome")
            connection.call("Page.enable")
            connection.call("Page.addScriptToEvaluateOnNewDocument", {"source": "window.__bagErrors=[];addEventListener('error',e=>__bagErrors.push(e.message));addEventListener('unhandledrejection',e=>__bagErrors.push(String(e.reason)));"})
            checks = Checks(connection, f"http://127.0.0.1:{app.server_port}")
            def home(bag=False):
                checks.navigate("index.html" + ("?view=bag#collection" if bag else ""), ready="document.documentElement.dataset.catalogState==='managed'")
                if bag: checks.wait("document.querySelector('#shop-dialog').open")
            def detail(): checks.navigate("product.html?id=bag-fixture", ready="!document.querySelector('#product-page-content').hidden")
            def color(value): checks.evaluate("[...document.querySelectorAll('#product-page-colors button')].find(b=>b.textContent===" + json.dumps(value) + ").click()")
            def count(): return checks.evaluate("Number(document.querySelector('[data-product-bag-count]')?.textContent ?? document.querySelector('#cart-count').textContent)")
            def quantity(value): return checks.evaluate("[...shoppingCart].reduce((n,[k,q])=>n+(getCartItem(k)?.color===" + json.dumps(value) + "?q:0),0)")
            def increase(value): checks.evaluate("[...document.querySelectorAll('[data-shop-action=increase]')].find(b=>getCartItem(b.dataset.productKey)?.color===" + json.dumps(value) + ").click()")
            home(); checks.click('#privacy-banner [data-privacy-choice="necessary"]')
            checks.check(checks.evaluate("localStorage.getItem('velora-shopping-v1')===null"), "Necessary-only choice does not enable optional saved looks")
            checks.check(checks.evaluate("document.querySelector('[data-category=\"THE LAYERING EDIT\"]').textContent==='Layering'"), "Category label is readable")
            detail()
            checks.check(checks.evaluate("document.querySelector('#product-page-price').textContent==='€119.95'"), "Product detail uses the shared EUR formatter")
            checks.click('#product-page-add')
            checks.check(count() == 1, "Product detail exposes the active bag count")
            checks.check(checks.evaluate("localStorage.getItem('velora-shopping-v1')===null && JSON.parse(sessionStorage.getItem('velora-session-bag-v1')).cart['product:bag-fixture::Black::M']===1"), "Necessary-only bag is saved in the active tab session")
            home(True)
            checks.check(count() == 1 and checks.evaluate("document.querySelector('#shop-dialog-content').textContent.includes('€119.95')"), "View bag retains the detail-page addition and EUR price")
            checks.check(checks.evaluate("!new URLSearchParams(location.search).has('view')"), "Consumed View bag request is removed from the URL")
            home(); checks.check(count() == 1, "Necessary-only bag survives reload")
            detail(); color('Cream'); checks.click('#product-page-add'); color('Black'); checks.click('#product-page-add')
            checks.check(count() == 2 and checks.evaluate("document.querySelector('#product-page-feedback').textContent.includes('Only 2')"), "Detail shared stock caps the sum across colors")
            checks.evaluate("VeloraPrivacy.clearDeviceData()")
            checks.check(count() == 0 and checks.evaluate("sessionStorage.getItem('velora-session-bag-v1')===null && localStorage.getItem('velora-shopping-v1')===null"), "Explicit device-data clearing removes active and optional bag state")

            with app.connect() as db:
                state = json.loads(db.execute("SELECT data FROM commerce_state WHERE id=1").fetchone()[0])
                state['variants'] = [{"id": name, "product": "bag-fixture", "size": "M", "color": name, "stock": stock,
                    "location": "Main warehouse", "lot": "Default", "threshold": 0, "target": 5, "sku": name, "barcode": name}
                    for name, stock in (("Black", 1), ("Cream", 5))]
                db.execute("UPDATE commerce_state SET data=? WHERE id=1", (json.dumps(state),))
                db.execute("UPDATE products SET stock=6 WHERE id='bag-fixture'")
            detail(); checks.click('#privacy-banner [data-privacy-choice="necessary"]'); checks.click('#product-page-add'); checks.click('#product-page-add')
            checks.check(count() == 1, "Detail cannot exceed its selected variant stock")
            color('Cream'); checks.click('#product-page-add'); home(True)
            checks.evaluate("selectedVariants.set('product:bag-fixture',{color:'Cream',size:'M'})")
            increase('Black'); checks.check(quantity('Black') == 1, "Bag cannot increase a sold-out row when another card color is selected")
            checks.evaluate("selectedVariants.set('product:bag-fixture',{color:'Black',size:'M'})")
            increase('Cream'); checks.check(quantity('Cream') == 2, "Bag can increase an available row while the card's other color is full")
            checks.evaluate("savedLooks.add('product:bag-fixture::Cream::M');activeShopView='wishlist';renderShopDialog()")
            checks.click('[data-shop-action=wishlist-to-cart]')
            checks.check(quantity('Cream') == 3 and quantity('Black') == 1, "Wishlist-to-bag retains the wishlist row's variant")

            checks.evaluate("document.querySelector('#shop-dialog').close();VeloraPrivacy.openSettings()")
            checks.evaluate("document.querySelector('#privacy-saved-looks').checked=true;document.querySelector('#privacy-settings-form').requestSubmit()")
            checks.check(checks.evaluate("JSON.parse(localStorage.getItem('velora-shopping-v1')).cart['product:bag-fixture::Cream::M']===3"), "Opting in additionally saves the existing session bag")
            checks.evaluate("VeloraPrivacy.openSettings();document.querySelector('#privacy-settings [data-privacy-choice=necessary]').click()")
            home(); checks.check(count() == 4 and checks.evaluate("localStorage.getItem('velora-shopping-v1')===null && document.querySelector('#wishlist-count').textContent==='0'"), "Withdrawing optional saving retains only the active bag across pages")
            detail()
            for width in (320, 390):
                connection.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 844, "deviceScaleFactor": 1, "mobile": True})
                checks.evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
                checks.check(checks.evaluate(f"innerWidth==={width} && document.documentElement.scrollWidth<=document.documentElement.clientWidth && [...document.querySelectorAll('.product-header-actions a')].every(a=>{{const r=a.getBoundingClientRect();return r.left>=0 && r.right<=innerWidth}})"), f"Product shopping navigation fits true {width}px mobile width")
            (ROOT / "tmp/shopping-state-product-mobile.png").write_bytes(base64.b64decode(connection.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})["data"]))
            checks.evaluate("VeloraPrivacy.clearDeviceData();window.__originalSetItem=Storage.prototype.setItem;Storage.prototype.setItem=function(){throw new Error('Test storage unavailable')}")
            checks.click('#product-page-add')
            checks.check(checks.evaluate("document.querySelector('#product-page-feedback').textContent.includes('could not be retained')"), "Blocked browser storage shows an accurate retention warning")
            checks.evaluate("Storage.prototype.setItem=window.__originalSetItem")
            home(); checks.check(count() == 0, "A blocked-storage addition is not falsely reported as retained")
            checks.check(checks.evaluate("window.__bagErrors.length===0"), "Shopping changes produce no runtime errors")
            report = {"passed": len(checks.passed), "checks": checks.passed}
            (ROOT / "tmp/shopping-state-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report))
        finally:
            if connection: connection.socket.close()
            if browser: browser.terminate(); browser.wait(timeout=10)
            app.shutdown(); app.server_close(); serving.join(timeout=5)


if __name__ == '__main__': main()
