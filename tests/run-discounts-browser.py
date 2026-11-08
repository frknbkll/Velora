"""Check themed admin codes and anonymous bag previews using disposable data."""
import json
from pathlib import Path
import runpy
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
import server
from test_auth_server import Client, PASSWORD

helpers = runpy.run_path(str(ROOT / "tests/run-account-browser.py"))
Checks, start_chrome = helpers["Checks"], helpers["start_chrome"]


def main():
    (ROOT / "tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="discount-browser-", dir=ROOT / "tmp", ignore_cleanup_errors=True) as folder:
        directory = Path(folder)
        app = server.make_server(port=0, database=directory / "accounts.sqlite3", root=ROOT, catalog=ROOT / "product-catalog.json")
        app.RequestHandlerClass.log_message = lambda *args: None
        with app.connect() as db:
            db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,'admin',?)", ("Discount Browser Owner", "discount-owner@example.test", server.hash_password(PASSWORD), server.now_iso()))
        serving = threading.Thread(target=app.serve_forever, daemon=True); serving.start()
        admin = Client(app); assert admin.login(email="discount-owner@example.test")[0] == 200
        product = admin.request("GET", "/api/admin/products")[1]["products"][0]
        product_id = product["id"]
        assert admin.request("PATCH", f"/api/admin/products/{product_id}", {"price": 101.05, "stock": 10, "published": True})[0] == 200
        browser = connection = checks = None
        try:
            browser, connection = start_chrome(directory / "chrome")
            connection.call("Page.enable"); connection.call("Network.setCacheDisabled", {"cacheDisabled": True})
            connection.call("Page.addScriptToEvaluateOnNewDocument", {"source": "window.__discountErrors=[];addEventListener('error',e=>{if(e.message)__discountErrors.push(e.message)});addEventListener('unhandledrejection',e=>__discountErrors.push(String(e.reason)));addEventListener('securitypolicyviolation',e=>__discountErrors.push('CSP '+e.violatedDirective));"})
            origin = f"http://127.0.0.1:{app.server_port}"
            checks = Checks(connection, origin)
            def cookie(owner=True):
                connection.call("Network.clearBrowserCookies")
                if owner:
                    name, value = admin.cookie.split("=", 1)
                    assert connection.call("Network.setCookie", {"name": name, "value": value, "url": origin, "path": "/", "httpOnly": True, "sameSite": "Lax"})["success"]
            def codes(): return admin.request("GET", "/api/admin/discounts")[1]["discounts"]
            def apply(code):
                checks.fill(".shop-discount-form", {"discountCode": code}); checks.submit(".shop-discount-form")
                checks.wait("!bagDiscount.pending")
            def storefront():
                checks.navigate("index.html", ready="window.veloraCatalogReady && document.documentElement.dataset.catalogState==='managed'")
                checks.evaluate("document.querySelector('#privacy-banner [data-privacy-choice=necessary]')?.click()")
                checks.show_all_store_products()
                checks.click(f'.add-to-bag[data-product-key="product:{product_id}"]')
                checks.click('.header-shop-actions [data-shop-view="cart"]')
                checks.wait("document.querySelector('#shop-dialog').open && document.querySelector('.shop-discount-form')")
            def fits(label):
                checks.check(checks.evaluate("document.documentElement.scrollWidth<=innerWidth+1"), label + " page fits")
                checks.check(checks.evaluate("(()=>{const d=document.querySelector('dialog[open]');return !d || (d.getBoundingClientRect().left>=-1 && d.getBoundingClientRect().right<=innerWidth+1 && d.scrollWidth<=d.clientWidth+1)})()"), label + " dialog fits")

            cookie(); checks.viewport(1440, 1000)
            checks.navigate("admin.html#discounts", ready="document.querySelector('#discounts-count')?.textContent==='0 of 0 codes'")
            checks.evaluate("document.querySelector('#privacy-banner [data-privacy-choice=necessary]')?.click()")
            checks.check(checks.evaluate("document.querySelectorAll('.discount-template').length===6"), "Six seasonal templates are available")
            checks.click('.discount-template.theme-halloween')
            checks.check(checks.evaluate("document.querySelector('#discount-editor').open && !document.querySelector('#discount-active').checked"), "Themed drafts start inactive")
            checks.fill("#discount-editor-form", {"name": "Halloween browser offer", "code": "SPOOKY21", "amount": 21, "minSubtotal": 0, "active": True})
            checks.submit("#discount-editor-form"); checks.wait("!document.querySelector('#discount-editor').open && document.querySelectorAll('#discounts-rows tr[data-discount-id]').length===1")
            promo = next(item for item in codes() if item["code"] == "SPOOKY21")
            checks.check(promo["active"] and promo["theme"] == "halloween" and promo["amount"] == 21, "The themed percentage offer is saved")
            checks.click('.discount-template.theme-black-friday'); checks.fill("#discount-editor-form", {"code": "BLACKFRIDAY20"}); checks.submit("#discount-editor-form")
            checks.wait("!document.querySelector('#discount-editor').open && document.querySelectorAll('#discounts-rows tr[data-discount-id]').length===2")
            checks.check(not next(item for item in codes() if item["code"] == "BLACKFRIDAY20")["active"], "Saving a draft does not activate it")
            checks.screenshot("discounts-admin-desktop.png", 1440, 1000)

            cookie(False); storefront(); apply("spooky21")
            checks.check(checks.evaluate("bagDiscount.quote.subtotalCents===10105 && bagDiscount.quote.discountCents===2122 && bagDiscount.quote.totalCents===7983 && document.querySelector('.shop-discount-saving').textContent.includes('SPOOKY21')"), "Case-insensitive code applies server-rounded 21% saving")
            checks.evaluate("window.__originalDiscountFetch=window.fetch;window.__delayedDiscountFetch=false;window.fetch=async(...args)=>{const response=await window.__originalDiscountFetch(...args);if(String(args[0]).includes('/api/discounts/validate')&&!window.__delayedDiscountFetch){window.__delayedDiscountFetch=true;await new Promise(resolve=>setTimeout(resolve,600));}return response};document.querySelector('.shop-discount-form').requestSubmit()")
            checks.click('.shop-quantity-button[data-shop-action="increase"]'); checks.wait("!bagDiscount.pending && bagDiscount.quote?.subtotalCents===20210")
            checks.evaluate("new Promise(resolve=>setTimeout(resolve,700))")
            checks.check(checks.evaluate("bagDiscount.quote.discountCents===4244 && bagDiscount.quote.totalCents===15966"), "Changing quantity revalidates the discount")
            checks.check(checks.evaluate("bagDiscount.quote.subtotalCents===20210 && bagDiscount.quote.totalCents===15966"), "A delayed old response cannot replace the latest bag quote")
            checks.evaluate("window.fetch=window.__originalDiscountFetch;delete window.__originalDiscountFetch;delete window.__delayedDiscountFetch")
            assert admin.request("PATCH", f"/api/admin/products/{product_id}", {"price": 199.95})[0] == 200
            checks.evaluate("loadManagedCatalog()")
            checks.wait("!bagDiscount.pending && bagDiscount.quote?.subtotalCents===39990")
            checks.check(checks.evaluate("bagDiscount.quote.discountCents===8398 && bagDiscount.quote.totalCents===31592"), "Updated server catalog prices replace the prior quote")
            checks.screenshot("discounts-bag-desktop.png", 1440, 1000)
            checks.click('[data-checkout-action="review"]'); checks.wait("!bagDiscount.pending && document.querySelector('[data-checkout-action=complete]')")
            checks.check(checks.evaluate("document.querySelector('.shop-discount-saving').textContent.includes('SPOOKY21') && !document.querySelector('[data-checkout-action=complete]').disabled"), "The review stage retains a freshly validated saving")
            checks.click('[data-checkout-action="complete"]'); checks.wait("document.querySelector('#checkout-preview-complete-title')")
            checks.check(checks.evaluate("document.querySelector('.checkout-preview-complete').textContent.includes('No order was placed') && document.querySelector('.shop-discount-saving').textContent.includes('SPOOKY21')"), "Sample confirmation shows discount and no-order disclosure")
            operations = admin.request("GET", "/api/admin/commerce")[1]
            checks.check(len(operations["orders"]) == 0, "Applying a preview code creates no orders")
            checks.click('[data-checkout-action="done"]'); checks.click('.header-shop-actions [data-shop-view="cart"]'); checks.wait("!bagDiscount.pending")
            checks.click('.shop-discount-remove'); checks.check(checks.evaluate("!bagDiscount.quote && !document.querySelector('.shop-discount-saving')"), "Remove restores the undiscounted bag")
            apply("WRONGCODE"); checks.check(checks.evaluate("document.querySelector('.shop-discount-message').classList.contains('is-error') && !document.querySelector('.shop-discount-saving')"), "Invalid code shows an error without a stale saving")
            for code, amount, minimum in (("FIXED500", 500, 0), ("MIN500", 10, 500)):
                assert admin.request("POST", "/api/admin/discounts", {"name": code, "code": code, "theme": "custom", "type": "fixed", "amount": amount, "minSubtotal": minimum, "startsAt": None, "endsAt": None, "active": True})[0] == 201
            apply("FIXED500"); checks.check(checks.evaluate("bagDiscount.quote.totalCents===0 && bagDiscount.quote.discountCents===39990"), "Fixed discount is capped at subtotal")
            apply("MIN500"); checks.check(checks.evaluate("!bagDiscount.quote && document.querySelector('.shop-discount-message').classList.contains('is-error')"), "Minimum spend blocks an ineligible code")
            apply("SPOOKY21"); assert admin.request("PATCH", f"/api/admin/discounts/{promo['id']}", {"active": False})[0] == 200
            checks.click('.shop-dialog-close'); checks.click('.header-shop-actions [data-shop-view="cart"]'); checks.wait("!bagDiscount.pending")
            checks.check(checks.evaluate("!bagDiscount.quote && !document.querySelector('.shop-discount-saving') && document.querySelector('.shop-discount-message').classList.contains('is-error')"), "Deactivating a code clears it on bag revalidation")

            cookie(); checks.navigate("admin.html#discounts", ready="document.querySelectorAll('#discounts-rows tr[data-discount-id]').length===4")
            checks.click(f'[data-discount-id="{promo["id"]}"] button[aria-label="Edit discount SPOOKY21"]')
            checks.fill("#discount-editor-form", {"type": "fixed", "amount": 10, "active": True}); checks.submit("#discount-editor-form"); checks.wait("!document.querySelector('#discount-editor').open")
            checks.check(next(item for item in codes() if item["id"] == promo["id"])["type"] == "fixed", "Editing changes a saved code to fixed EUR")
            checks.click(f'[data-discount-id="{promo["id"]}"] button[aria-label="Deactivate discount SPOOKY21"]'); checks.wait(f"document.querySelector('[data-discount-id=\"{promo['id']}\"] .discount-status').textContent==='Inactive'")
            checks.click(f'[data-discount-id="{promo["id"]}"] button[aria-label="Activate discount SPOOKY21"]'); checks.wait(f"document.querySelector('[data-discount-id=\"{promo['id']}\"] .discount-status').textContent==='Active'")
            checks.check(True, "Admin activation and deactivation controls persist")
            checks.viewport(390, 844); checks.click('.discount-template.theme-halloween'); fits("Mobile admin")
            checks.screenshot("discounts-editor-mobile.png", 390, 844)
            checks.evaluate("document.querySelector('#discount-editor').close()")
            cookie(False); storefront(); apply("SPOOKY21"); fits("Mobile bag")
            checks.check(checks.evaluate("bagDiscount.quote.discountCents===1000 && bagDiscount.quote.totalCents===18995"), "Mobile bag applies the edited fixed offer")
            checks.screenshot("discounts-bag-mobile.png", 390, 844)
            checks.check(checks.evaluate("window.__discountErrors.length===0"), "No runtime or CSP errors")
            report = {"passed": len(checks.passed), "checks": checks.passed}
            (ROOT / "tmp/discounts-browser-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report))
        finally:
            if connection: connection.socket.close()
            if browser: browser.terminate(); browser.wait(timeout=10)
            app.shutdown(); app.server_close(); serving.join(timeout=5)


if __name__ == "__main__": main()
