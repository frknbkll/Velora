"""Exercise one-card outfit grouping and individually shoppable item images."""
import base64
import json
from pathlib import Path
import runpy
import shutil
import struct
import sys
import tempfile
import threading
import zlib

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
import server

helpers = runpy.run_path(str(ROOT / "tests/run-account-browser.py"))
Checks, start_chrome = helpers["Checks"], helpers["start_chrome"]
fixture_site = runpy.run_path(str(ROOT / "tests/run-admin-auto-color.py"))["fixture_site"]


def fixture_picture(path, color):
    width, height = 180, 240
    rows = b"".join(b"\0" + bytes(color if 35 < y < 210 else (248, 246, 241)) * width for y in range(height))
    def chunk(kind, data):
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!2I5B", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def main():
    (ROOT / "tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="outfit-items-", dir=ROOT / "tmp", ignore_cleanup_errors=True) as folder:
        directory = Path(folder); root = fixture_site(directory)
        shutil.copy2(ROOT / "assets/gallery/new-arrivals/espresso-tailored-suit.jpg", root / "assets/look.jpg")
        for name, color in [("suit", (77, 51, 40)), ("bag", (93, 61, 47)), ("shoes", (204, 169, 134)), ("other", (91, 112, 127)), ("navy", (31, 37, 54))]:
            fixture_picture(root / "assets" / f"{name}.png", color)
        # Real responsive images carry original-pixel width/height attributes.
        # Exercise that delivery path with small candidates of the same ratio.
        (root / "assets/candidates").mkdir()
        for name in ("suit", "bag", "shoes", "other", "navy"):
            shutil.copy2(root / "assets" / f"{name}.png", root / "assets/candidates" / f"{name}.png")
        responsive = {f"assets/{name}.png": {"src": f"assets/candidates/{name}.png", "srcset": f"assets/candidates/{name}.png 180w",
                       "width": 1200, "height": 1600} for name in ("suit", "bag", "shoes", "other", "navy")}
        with (root / "product-responsive-images.js").open("a", encoding="utf-8") as stream:
            stream.write("\nObject.assign(window.VeloraResponsiveImages, " + json.dumps(responsive) + ");\n")
        points = [{"image": "assets/look.jpg", "x": .47, "y": .45, "product_id": "outfit-parent", "label": "Suit"},
                  {"image": "assets/look.jpg", "x": .29, "y": .64, "product_id": "outfit-bag", "label": "Bag"},
                  {"image": "assets/look.jpg", "x": .23, "y": .96, "product_id": "outfit-shoes", "label": "Shoes"},
                  {"image": "assets/look.jpg", "x": .31, "y": .65, "product_id": "outfit-bag", "label": "Bag detail"}]
        products = []
        for identifier, name, source, price, parent in [
            ("outfit-parent", "The Espresso Styling Suit", "assets/look.jpg", 149, ""),
            ("outfit-bag", "The Espresso Standalone Bag", "assets/bag.png", 49, "outfit-parent"),
            ("outfit-shoes", "The Nude Standalone Shoes", "assets/shoes.png", 59, "outfit-parent"),
            ("outfit-other", "The Other Outfit", "assets/other.png", 89, ""),
        ]:
            item_image = "assets/suit.png" if identifier == "outfit-parent" else source
            products.append({"id": identifier, "name": name, "image": source, "images": [source, item_image] if source != item_image else [source],
                             "item_image": item_image, "parent_product_id": parent, "published": True, "price": price,
                             "founder": "Outfit Browser Fixture", "collection": "THE POLISHED EDIT", "base_color": "Espresso", "color_hex": "#493027",
                             "color_key": identifier, "sizes": ["One size"] if parent else ["S", "M"], "description": "Disposable outfit item fixture.",
                             "stock": 3 if parent else None, "image_hotspots": points if identifier == "outfit-parent" else []})
        (root / "product-catalog.json").write_text(json.dumps({"products": products}), encoding="utf-8")
        app = server.make_server(port=0, database=directory / "test.sqlite3", root=root)
        app.RequestHandlerClass.log_message = lambda *args: None
        with app.connect() as db:
            db.execute("UPDATE products SET color_variants=? WHERE id='outfit-parent'", (json.dumps([{"name": "Navy", "hex": "#252232", "image": "assets/navy.png"}]),))
        serving = threading.Thread(target=app.serve_forever, daemon=True); serving.start()
        browser = connection = None
        try:
            browser, connection = start_chrome(directory / "chrome")
            connection.call("Page.enable"); connection.call("Network.enable")
            connection.call("Network.setCacheDisabled", {"cacheDisabled": True})
            connection.call("Page.addScriptToEvaluateOnNewDocument", {"source": "window.__outfitErrors=[];addEventListener('error',e=>{if(e.message)__outfitErrors.push(e.message)});addEventListener('unhandledrejection',e=>__outfitErrors.push(String(e.reason)));addEventListener('securitypolicyviolation',e=>__outfitErrors.push('CSP '+e.violatedDirective));"})
            checks = Checks(connection, f"http://127.0.0.1:{app.server_port}")
            errors = []
            def go(path, ready):
                errors.extend(checks.evaluate("window.__outfitErrors || []") or [])
                checks.navigate(path, ready=ready)
            def viewport(width, height=950):
                connection.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": width <= 760})
                checks.evaluate("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
            def detail(identifier="outfit-parent", extra=""):
                go("product.html?id=" + identifier + extra, "!document.querySelector('#product-page-content').hidden && document.querySelector('#product-main-photo').dataset.photoState==='ready'")
                checks.evaluate("document.querySelector('#privacy-banner [data-privacy-choice=necessary]')?.click()")
            viewport(1440)
            go("index.html", "document.documentElement.dataset.catalogState==='managed'")
            checks.evaluate("document.querySelector('#privacy-banner [data-privacy-choice=necessary]')?.click()")
            checks.check(checks.evaluate("document.querySelectorAll('.look-tile').length===2 && !document.querySelector('.look-tile[data-product-id=outfit-bag]') && !document.querySelector('.look-tile[data-product-id=outfit-shoes]')"), "The homepage presents each outfit once and groups its individual pieces")
            checks.check(checks.evaluate("lookByKey.has('product:outfit-parent') && lookByKey.has('product:outfit-bag') && lookByKey.has('product:outfit-shoes')"), "Grouped pieces remain in the shopping lookup for direct links, bags and wishlists")
            detail()
            checks.check(checks.evaluate("document.querySelectorAll('.product-look-item').length===3 && new Set([...document.querySelectorAll('.product-look-item')].map(c=>c.dataset.lookProductId)).size===3"), "Shop this look deduplicates repeated markers into three distinct item cards")
            checks.check(checks.evaluate("[...document.querySelectorAll('.product-look-item img')].every(i=>i.getAttribute('src')!=='assets/look.jpg') && new Set([...document.querySelectorAll('.product-look-item img')].map(i=>i.getAttribute('src'))).size===3"), "Each item card uses its standalone image rather than repeating the full outfit photo")
            checks.check(checks.evaluate("[...document.querySelectorAll('.product-look-item img')].every(i=>{const r=i.getBoundingClientRect();return i.getAttribute('height')==='1600' && r.width>0 && Math.abs(r.height/r.width-4/3)<.015})"), "Desktop item photos retain compact equal-height frames when responsive delivery adds original image dimensions")
            checks.check(checks.evaluate("document.querySelector('[data-look-product-id=outfit-bag] .product-look-item-price').textContent==='€49' && document.querySelector('#product-parent-look').hidden"), "Outfit item cards display live euro prices without an unnecessary parent link")
            checks.click('[data-look-product-id="outfit-parent"] a')
            checks.wait("new URLSearchParams(location.search).get('view')==='item' && document.querySelector('#product-page-image').currentSrc.endsWith('/assets/candidates/suit.png')")
            checks.check(checks.evaluate("document.querySelector('#product-page-image').alt.includes('item-only')"), "The main-piece card opens the generated item photograph within the outfit gallery")
            checks.click("#product-page-colors button:nth-child(2)")
            checks.wait("document.querySelector('#product-page-image').currentSrc.endsWith('/assets/candidates/navy.png')")
            checks.check(True, "Changing color does not retain a different color's standalone photograph")
            checks.check(checks.evaluate("document.querySelector('#product-shop-look').hidden"), "A different outfit color does not show item cards tagged only on the original photograph")
            detail()
            checks.click("#product-main-photo .vpi-marker")
            checks.check(checks.evaluate("document.querySelector('#product-main-photo .vpi-item-link').getAttribute('href')==='product.html?id=outfit-parent&view=item'"), "The primary garment marker links to its standalone item view")
            checks.click('[data-look-product-id="outfit-bag"] a')
            checks.wait("document.querySelector('#product-page-title').textContent==='The Espresso Standalone Bag' && document.querySelector('#product-main-photo').dataset.photoState==='ready'")
            checks.check(checks.evaluate("!document.querySelector('#product-parent-look').hidden && document.querySelector('#product-parent-look').getAttribute('href')==='product.html?id=outfit-parent' && document.querySelector('#product-shop-look').hidden"), "An individual piece links back to its full outfit without repeating a one-item look grid")
            checks.check(checks.evaluate("document.querySelector('#product-page-image').currentSrc.endsWith('/assets/candidates/bag.png') && document.querySelectorAll('#product-main-photo .vpi-marker').length===0"), "The separate bag page uses its item image and has no copied outfit-coordinate markers")
            checks.click("#product-page-add")
            go("index.html?view=bag#collection", "document.documentElement.dataset.catalogState==='managed' && document.querySelector('#shop-dialog').open")
            checks.check(checks.evaluate("document.querySelector('#shop-dialog-content').textContent.includes('The Espresso Standalone Bag') && document.querySelector('#shop-dialog-content').textContent.includes('€49') && document.querySelector('#cart-count').textContent==='1'"), "A grouped accessory can be added from its page and remains available in the homepage bag")
            checks.click(".shop-dialog-close")
            checks.evaluate("savedLooks.add('product:outfit-shoes');activeShopView='wishlist';renderShopDialog()")
            checks.check(checks.evaluate("document.querySelector('#shop-dialog-content').textContent.includes('The Nude Standalone Shoes')"), "The wishlist can still resolve an individual shoe product hidden from outfit cards")
            for width in (390, 320):
                viewport(width, 844); detail()
                checks.evaluate("document.querySelector('#product-shop-look').scrollIntoView({block:'start',behavior:'instant'});new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
                checks.check(checks.evaluate(f"innerWidth==={width} && document.documentElement.clientWidth==={width} && document.documentElement.scrollWidth<={width} && getComputedStyle(document.querySelector('#product-look-items')).gridTemplateColumns.split(' ').length===2 && [...document.querySelectorAll('.product-look-item-link')].every(a=>{{const r=a.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth}})"), f"Individual-item cards fit a true {width}px mobile viewport in two columns")
                checks.check(checks.evaluate("[...document.querySelectorAll('.product-look-item img')].every(i=>{const r=i.getBoundingClientRect();return i.getAttribute('height')==='1600' && r.width>0 && Math.abs(r.height/r.width-4/3)<.015})"), f"Item images remain proportionate at {width}px with original-pixel dimension attributes")
                if width == 390:
                    checks.evaluate("document.fonts.ready;new Promise(r=>setTimeout(r,250))")
                    shot = connection.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
                    (ROOT / "tmp/outfit-items-mobile.png").write_bytes(base64.b64decode(shot["data"]))
            with app.connect() as db:
                db.execute("UPDATE products SET price=61 WHERE id='outfit-bag'")
            viewport(1440); detail()
            checks.check(checks.evaluate("document.querySelector('[data-look-product-id=outfit-bag] .product-look-item-price').textContent==='€61'"), "Changing an accessory price updates its grouped item card")
            with app.connect() as db:
                db.execute("UPDATE products SET published=0 WHERE id='outfit-bag'")
            detail()
            checks.check(checks.evaluate("!document.querySelector('[data-look-product-id=outfit-bag]') && document.querySelectorAll('.product-look-item').length===2"), "Unpublished accessories disappear from the outfit's item cards")
            errors.extend(checks.evaluate("window.__outfitErrors || []") or [])
            checks.check(not errors, "Outfit grouping, item views, shopping and mobile layouts produce no runtime or CSP errors: " + str(errors))
            report = {"passed": len(checks.passed), "checks": checks.passed}
            (ROOT / "tmp/outfit-items-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report))
        finally:
            if connection: connection.socket.close()
            if browser: browser.terminate(); browser.wait(timeout=10)
            app.shutdown(); app.server_close(); serving.join(timeout=5)


if __name__ == "__main__":
    main()
