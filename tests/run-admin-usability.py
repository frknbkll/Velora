"""Exercise admin edit protection and mobile navigation with disposable data."""
import json
import base64
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
    with tempfile.TemporaryDirectory(prefix="admin-usability-", dir=ROOT / "tmp", ignore_cleanup_errors=True) as folder:
        directory = Path(folder)
        app = server.make_server(port=0, database=directory / "accounts.sqlite3", root=ROOT)
        app.RequestHandlerClass.log_message = lambda *args: None
        with app.connect() as db:
            db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,'admin',?)", ("Usability Browser Owner", "usability-owner@example.test", server.hash_password(PASSWORD), server.now_iso()))
        serving = threading.Thread(target=app.serve_forever, daemon=True); serving.start()
        owner = Client(app); assert owner.login(email="usability-owner@example.test")[0] == 200
        products = owner.request("GET", "/api/admin/products")[1]["products"]
        product, other, alternate = products[:3]
        product_id = product["id"]
        assert owner.request("PATCH", f"/api/admin/products/{product_id}", {"images": [product["image"], other["image"]], "color_variants": [{"name": "Test Teal", "hex": "#008080", "image": alternate["image"]}]})[0] == 200
        browser = connection = None
        try:
            browser, connection = start_chrome(directory / "chrome")
            connection.call("Page.enable"); connection.call("Network.enable")
            connection.call("Network.setCacheDisabled", {"cacheDisabled": True})
            connection.call("Page.addScriptToEvaluateOnNewDocument", {"source": "window.__usabilityErrors=[];addEventListener('error',e=>{if(e.message)__usabilityErrors.push(e.message)});addEventListener('unhandledrejection',e=>__usabilityErrors.push(String(e.reason)));addEventListener('securitypolicyviolation',e=>__usabilityErrors.push('CSP '+e.violatedDirective));"})
            origin = f"http://127.0.0.1:{app.server_port}"
            checks = Checks(connection, origin)
            def viewport(width, height=950):
                connection.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": width <= 899})
                checks.evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
            checks.viewport = viewport
            name, value = owner.cookie.split("=", 1)
            assert connection.call("Network.setCookie", {"name": name, "value": value, "url": origin, "path": "/", "httpOnly": True, "sameSite": "Lax"})["success"]
            checks.viewport(1440)
            checks.navigate("admin.html#products", ready="!document.querySelector('#admin-shell').hidden && document.querySelectorAll('#admin-products-body tr').length>0")
            checks.evaluate("document.querySelector('#privacy-banner [data-privacy-choice=necessary]')?.click();document.documentElement.style.scrollBehavior='auto';document.fonts.ready")
            edit_selector = f'[data-edit-product="{product_id}"]'
            def open_editor():
                checks.click(edit_selector); checks.wait("document.querySelector('#admin-edit-dialog').open")
            def close_unchanged():
                checks.click("#admin-edit-close")
                checks.check(checks.evaluate("!document.querySelector('#admin-edit-dialog').open && !document.querySelector('#admin-discard-dialog').open"), "Unchanged editor closes without a discard warning")
            open_editor(); close_unchanged()
            open_editor()
            original = checks.evaluate("document.querySelector('#admin-edit-product-name').value")
            checks.fill("#admin-edit-form", {"name": original + " unsaved"})
            checks.evaluate("document.querySelector('#admin-edit-dialog').dispatchEvent(new Event('cancel',{cancelable:true}))")
            checks.check(checks.evaluate("document.querySelector('#admin-discard-dialog').open"), "Escape protects a changed product")
            checks.click("#admin-discard-keep")
            checks.check(checks.evaluate("document.querySelector('#admin-edit-dialog').open && document.querySelector('#admin-edit-product-name').value.endsWith(' unsaved')"), "Keep editing retains entered changes")
            checks.check(checks.evaluate("(()=>{const e=new Event('beforeunload',{cancelable:true});window.dispatchEvent(e);return e.defaultPrevented})()"), "Leaving the page protects an unsaved product")
            checks.click("#admin-edit-close"); checks.click("#admin-discard-confirm")
            checks.check(checks.evaluate("!document.querySelector('#admin-edit-dialog').open"), "Discard closes the editor")
            open_editor()
            checks.check(checks.evaluate("document.querySelector('#admin-edit-product-name').value==="+json.dumps(original)), "Discarded changes do not alter the product")
            checks.click('#admin-image-gallery [data-image-action="right"][data-image-index="0"]'); checks.click("#admin-edit-cancel")
            checks.check(checks.evaluate("document.querySelector('#admin-discard-dialog').open"), "Photo ordering is protected as an unsaved edit")
            checks.click("#admin-discard-confirm"); open_editor()
            checks.click("#admin-color-variants [data-remove-color]"); checks.click("#admin-edit-close")
            checks.check(checks.evaluate("document.querySelector('#admin-discard-dialog').open"), "Color removal is protected as an unsaved edit")
            checks.click("#admin-discard-confirm"); open_editor()
            checks.fill("#admin-edit-form", {"fit": "Unsaved fit note"})
            checks.evaluate("location.hash='operations'")
            checks.wait("document.querySelector('#admin-discard-dialog').open")
            checks.check(checks.evaluate("location.hash==='#products' && !document.querySelector('#admin-products').hidden"), "Section changes wait for an unsaved-edit decision")
            checks.click("#admin-discard-keep")
            checks.fill("#admin-edit-form", {"fit": "Disposable fit note", "name": original + " saved"})
            checks.submit("#admin-edit-form"); checks.wait("!document.querySelector('#admin-edit-dialog').open")
            checks.check(not checks.evaluate("document.querySelector('#admin-discard-dialog').open"), "Saving closes without a discard warning")
            # The products collection is the supported admin read endpoint.
            saved_product = next(p for p in owner.request("GET", "/api/admin/products")[1]["products"] if p["id"] == product_id)
            checks.check(saved_product["name"] == original + " saved" and saved_product["fit"] == "Disposable fit note", "Save persists edited product fields")
            checks.evaluate("window.scrollTo(0,1800)")
            checks.click('[data-admin-section="operations"]'); checks.wait("!document.querySelector('#admin-operations').hidden && scrollY===0")
            checks.check(checks.evaluate("document.activeElement===document.querySelector('#admin-operations h1')"), "Section navigation resets scroll and focuses its heading")
            checks.click('[data-admin-section="products"]')
            for width in (390, 320):
                checks.viewport(width, 844)
                checks.check(checks.evaluate(f"innerWidth==={width} && document.documentElement.clientWidth==={width} && document.documentElement.scrollWidth<={width}"), f"Mobile product view fits {width}px without shrink-to-fit")
                checks.check(checks.evaluate("getComputedStyle(document.querySelector('.admin-nav')).display==='none' && document.querySelector('#admin-menu-toggle').getBoundingClientRect().height>=44"), f"Mobile admin navigation has an accessible menu at {width}px")
                checks.click("#admin-menu-toggle")
                checks.check(checks.evaluate("document.querySelector('#admin-menu-toggle').getAttribute('aria-expanded')==='true' && [...document.querySelectorAll('.admin-nav a:not([hidden])')].every(a=>{const r=a.getBoundingClientRect();return r.width>0&&r.left>=0&&r.right<=innerWidth&&r.height>=44})"), f"All admin sections are visible inside the open menu at {width}px")
                checks.evaluate("document.querySelector('#admin-section-nav').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}))")
                checks.check(checks.evaluate("document.querySelector('#admin-menu-toggle').getAttribute('aria-expanded')==='false' && document.activeElement.id==='admin-menu-toggle'"), f"Escape closes the menu and restores focus at {width}px")
                actions_fit = checks.evaluate("[...document.querySelector('#admin-products-body tr').querySelectorAll('button')].every(b=>{const r=b.getBoundingClientRect();return r.left>=-0.5&&r.right<=innerWidth+0.5&&r.height>=43.9})")
                checks.check(actions_fit, f"Product actions remain visible and touch-sized at {width}px")
            checks.viewport(390, 844)
            checks.evaluate("document.querySelector('#admin-products-body tr').scrollIntoView({block:'start',behavior:'instant'})")
            checks.evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
            shot = connection.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
            (ROOT / "tmp/admin-usability-products-mobile.png").write_bytes(base64.b64decode(shot["data"]))
            checks.evaluate("window.scrollTo({top:0,behavior:'instant'})")
            checks.click("#admin-menu-toggle"); checks.screenshot("admin-usability-menu-mobile.png", 390, 844)
            checks.click("#admin-menu-toggle")
            checks.click("#admin-menu-toggle"); checks.click('[data-admin-section="folder-access"]')
            checks.wait("!document.querySelector('#admin-colleague-create').disabled")
            checks.check(checks.evaluate("document.querySelector('#admin-menu-toggle').getAttribute('aria-expanded')==='false' && !document.querySelector('#admin-folder-access').hidden && scrollY===0"), "Choosing a mobile section closes the menu and opens at the top")
            checks.click("#admin-colleague-create"); checks.wait("document.querySelector('#admin-folder-access-dialog').open")
            checks.check(checks.evaluate("(()=>{const d=document.querySelector('#admin-folder-access-dialog').getBoundingClientRect(),b=document.querySelector('#admin-folder-access-save').getBoundingClientRect();return b.top>=d.top&&b.bottom<=d.bottom&&b.height>=44})()"), "Colleague Save stays visible at the start of a long form")
            checks.screenshot("admin-usability-colleague-mobile.png", 390, 844)
            checks.click("#admin-folder-access-cancel")
            checks.check(checks.evaluate("window.__usabilityErrors.length===0"), "Admin interactions produce no runtime or CSP errors")
            report = {"passed": len(checks.passed), "checks": checks.passed}
            (ROOT / "tmp/admin-usability-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report))
        finally:
            if connection: connection.socket.close()
            if browser: browser.terminate(); browser.wait(timeout=10)
            app.shutdown(); app.server_close(); serving.join(timeout=5)


if __name__ == "__main__": main()
