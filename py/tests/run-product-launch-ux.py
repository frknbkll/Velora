"""Verify mobile product actions and recoverable loading against disposable data."""

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
    with tempfile.TemporaryDirectory(prefix="product-launch-", dir=ROOT / "tmp", ignore_cleanup_errors=True) as folder:
        directory = Path(folder)
        image = "assets/careers/fashion-design-assistant.jpg"
        catalog = directory / "catalog.json"
        catalog.write_text(json.dumps({"products": [{
            "id": "launch-fixture", "name": "The Studio Wrap Dress", "image": image, "images": [image],
            "base_color": "Black", "color_hex": "#222222", "sizes": ["M", "L"], "price": 119.95,
            "stock": 3, "description": "A disposable product launch fixture.", "founder": "Velora",
            "collection": "THE EVERYDAY EDIT", "published": True,
        }]}), encoding="utf-8")
        app = server.make_server(port=0, database=directory / "test.sqlite3", catalog=catalog, root=ROOT)
        app.RequestHandlerClass.log_message = lambda *args: None
        with app.connect() as db:
            db.execute("UPDATE products SET color_variants=? WHERE id='launch-fixture'", (json.dumps([{"name": "Cream", "hex": "#eee7dc", "image": image}]),))
            data = json.loads(db.execute("SELECT data FROM commerce_state WHERE id=1").fetchone()[0])
            data["variants"] = [
                {"id": "black-m", "product": "launch-fixture", "color": "Black", "size": "M", "stock": 2},
                {"id": "cream-m", "product": "launch-fixture", "color": "Cream", "size": "M", "stock": 0},
                {"id": "cream-l", "product": "launch-fixture", "color": "Cream", "size": "L", "stock": 1},
            ]
            db.execute("UPDATE commerce_state SET data=? WHERE id=1", (json.dumps(data),))
        serving = threading.Thread(target=app.serve_forever, daemon=True)
        serving.start()
        browser = connection = None
        try:
            browser, connection = start_chrome(directory / "chrome")
            connection.call("Page.enable")
            connection.call("Network.enable")
            connection.call("Network.setCacheDisabled", {"cacheDisabled": True})
            connection.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
                window.__launchErrors=[];
                addEventListener('error',e=>{if(e.message)__launchErrors.push(e.message)});
                addEventListener('unhandledrejection',e=>__launchErrors.push(String(e.reason)));
                addEventListener('securitypolicyviolation',e=>__launchErrors.push('CSP '+e.violatedDirective));
                const originalFetch=fetch;
                window.fetch=(...args)=>{
                  if(String(args[0]).includes('/api/catalog/launch-fixture') && location.search.includes('qa=retry') && !sessionStorage.getItem('qa-product-failed')){
                    sessionStorage.setItem('qa-product-failed','1');
                    return new Promise(resolve=>setTimeout(()=>resolve(new Response('{}',{status:503})),650));
                  }
                  return originalFetch(...args);
                };
            """})
            checks = Checks(connection, f"http://127.0.0.1:{app.server_port}")
            def viewport(width, height=844):
                connection.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": width <= 760})
                checks.evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
            checks.viewport = viewport
            def choose(selector, value):
                checks.evaluate(f"[...document.querySelectorAll({json.dumps(selector)})].find(b=>b.textContent.trim()==={json.dumps(value)}).click()")
            def fits(width):
                return checks.evaluate(f"innerWidth==={width} && document.documentElement.clientWidth==={width} && document.documentElement.scrollWidth<={width}")
            def no_collisions():
                return checks.evaluate("""(()=>{
                  const bar=document.querySelector('#product-mobile-bar'),banner=document.querySelector('#privacy-banner'),chat=document.querySelector('.support-launcher');
                  const r=bar.getBoundingClientRect();if(!r.height)return true;
                  if(r.left<0||r.right>innerWidth||r.top<0||r.bottom>innerHeight)return false;
                  if(banner && !banner.hidden && r.bottom>banner.getBoundingClientRect().top)return false;
                  if(chat && chat.getBoundingClientRect().height && chat.getBoundingClientRect().bottom>r.top)return false;
                  return true;
                })()""")
            def shot(name):
                checks.evaluate("new Promise(resolve=>setTimeout(resolve,150))")
                capture=connection.call("Page.captureScreenshot", {"format":"png", "captureBeyondViewport":False})
                (ROOT / "tmp" / name).write_bytes(base64.b64decode(capture["data"]))

            viewport(390)
            checks.navigate("product.html?id=launch-fixture&qa=retry", ready="document.querySelector('#main-content').getAttribute('aria-busy')==='true'")
            checks.check(checks.evaluate("document.querySelector('#product-page-status').textContent.includes('Loading product')"), "Product request has a visible busy state")
            checks.wait("document.querySelector('#product-page-retry')")
            checks.check(checks.evaluate("document.querySelector('#main-content').getAttribute('aria-busy')==='false' && document.querySelector('#product-page-status').getAttribute('role')==='alert' && document.querySelector('#product-mobile-bar').hidden"), "Network failure shows a recoverable error and hides purchase actions")
            checks.click("#product-page-retry")
            checks.wait("!document.querySelector('#product-page-content').hidden && document.querySelector('#product-main-photo').dataset.photoState==='ready'")
            checks.check(checks.evaluate("document.querySelector('#main-content').getAttribute('aria-busy')==='false' && !document.querySelector('#product-page-retry')"), "Retry restores the product and clears the error state")
            checks.check(checks.evaluate("document.querySelector('[data-product-choose-options]').getBoundingClientRect().bottom<innerHeight"), "Mobile shoppers see a product options action above the fold")
            checks.check(no_collisions(), "Mobile bar does not overlap the privacy banner or support launcher")
            checks.click('#privacy-banner [data-privacy-choice="necessary"]')
            checks.wait("document.querySelector('#product-mobile-bar').getBoundingClientRect().height>0")
            checks.check(checks.evaluate("document.querySelector('#product-mobile-action').textContent==='Choose options'"), "Initial mobile action asks for an explicit size choice")
            checks.click("#product-mobile-action")
            checks.check(checks.evaluate("document.activeElement.id==='product-page-options' && document.querySelector('[data-product-bag-count]').textContent==='0'"), "Choose options focuses the controls without adding a default size")
            choose("#product-page-sizes button", "M")
            checks.check(checks.evaluate("document.querySelector('#product-mobile-action').textContent==='Add to bag' && !document.querySelector('#product-mobile-action').disabled"), "Choosing a size enables the matching mobile bag action")
            choose("#product-page-colors button", "Cream")
            checks.check(checks.evaluate("document.querySelector('#product-mobile-action').disabled && document.querySelector('#product-mobile-action').textContent==='Sold out' && document.querySelector('#product-page-add').disabled"), "Sold-out color/size disables both bag actions")
            choose("#product-page-sizes button", "L")
            checks.check(checks.evaluate("document.querySelector('#product-mobile-selection').textContent==='Cream · L' && document.querySelector('#product-mobile-price').textContent==='€119.95' && !document.querySelector('#product-mobile-action').disabled"), "Mobile selection, price and stock stay in sync")
            checks.click("#product-mobile-action")
            checks.check(checks.evaluate("document.querySelector('[data-product-bag-count]').textContent==='1' && !document.querySelector('#product-mobile-feedback').hidden && JSON.parse(sessionStorage.getItem('velora-session-bag-v1')).cart['product:launch-fixture::Cream::L']===1"), "Sticky action adds the chosen variant and gives visible feedback")
            for width in (320,390):
                viewport(width)
                checks.check(fits(width) and no_collisions(), f"Product controls fit true {width}px without overlay collisions")
                checks.check(checks.evaluate("(()=>{const b=document.querySelector('#product-mobile-action').getBoundingClientRect();return b.height>=44&&b.width>=44})()"), f"Sticky action has a usable touch target at {width}px")
            viewport(390)
            checks.evaluate("window.scrollTo(0,0)")
            shot("product-launch-mobile.png")
            viewport(1440,1000)
            checks.check(checks.evaluate("getComputedStyle(document.querySelector('#product-mobile-bar')).display==='none' && getComputedStyle(document.querySelector('.product-mobile-intro')).display==='none'"), "Desktop keeps the established product layout")
            connection.call("Network.setBlockedURLs", {"urls": ["*assets/careers/fashion-design-assistant.jpg*", "*assets/responsive/*"]})
            checks.navigate("product.html?id=launch-fixture", ready="document.querySelector('#product-main-photo').dataset.photoState==='error'")
            checks.check(checks.evaluate("!document.querySelector('#product-photo-retry').hidden && document.querySelector('#product-page-image').hidden && !document.querySelector('#product-page-content').hidden"), "A failed photograph offers retry without hiding the product details")
            connection.call("Network.setBlockedURLs", {"urls": []})
            checks.click("#product-photo-retry")
            checks.wait("document.querySelector('#product-main-photo').dataset.photoState==='ready' && document.querySelector('#product-page-image').naturalWidth>0")
            checks.check(checks.evaluate("document.querySelector('#product-photo-state').hidden && !document.querySelector('#product-page-image').hidden"), "Photograph retry restores the full image")
            checks.check(checks.evaluate("window.__launchErrors.length===0"), "Product interactions have no runtime or CSP errors")
            result={"passed":len(checks.passed),"checks":checks.passed}
            (ROOT / "tmp/product-launch-ux-results.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
            print(json.dumps(result))
        finally:
            if connection: connection.socket.close()
            if browser:
                browser.terminate()
                browser.wait(timeout=10)
            app.shutdown()
            app.server_close()
            serving.join(timeout=5)


if __name__ == "__main__":
    main()
