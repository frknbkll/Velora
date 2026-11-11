"""Exercise shoppable photos, zoom and their admin editor with disposable data."""
import base64
import json
from pathlib import Path
import runpy
import shutil
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
import server
from test_auth_server import Client, PASSWORD

helpers = runpy.run_path(str(ROOT / "tests/run-account-browser.py"))
Checks, start_chrome = helpers["Checks"], helpers["start_chrome"]
fixture_site = runpy.run_path(str(ROOT / "tests/run-admin-auto-color.py"))["fixture_site"]


def main():
    (ROOT / "tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="shoppable-photo-", dir=ROOT / "tmp", ignore_cleanup_errors=True) as folder:
        directory = Path(folder)
        root = fixture_site(directory)
        for source, name in [("espresso-tailored-suit.jpg", "style.jpg"), ("navy-wide-leg-suit.jpg", "other.jpg")]:
            shutil.copy2(ROOT / "assets/gallery/new-arrivals" / source, root / "assets" / name)
        shutil.copy2(root / "assets/other.jpg", root / "assets/navy.jpg")
        image = "assets/style.jpg"
        points = [
            {"image": image, "x": .288, "y": .634, "product_id": "fixture-bag", "label": "Bag"},
            {"image": image, "x": .516, "y": .151, "product_id": "fixture-scarf", "label": "Scarf"},
        ]
        products = [{"id": item_id, "name": name, "price": price, "image": image, "images": [image],
                     "founder": "Photo Studio Fixture", "collection": "THE POLISHED EDIT", "published": True,
                     "base_color": "Brown", "color_hex": "#4e342e", "description": "Disposable shoppable-photo fixture.",
                     "sizes": ["One size"] if item_id != "fixture-look" else ["S", "M"],
                     "image_hotspots": points if item_id == "fixture-look" else []}
                    for item_id, name, price in [("fixture-look", "The Styling Suit", 149), ("fixture-bag", "The Espresso Bag", 49), ("fixture-scarf", "The Taupe Scarf", 19)]]
        (root / "product-catalog.json").write_text(json.dumps({"products": products}), encoding="utf-8")
        app = server.make_server(port=0, database=directory / "test.sqlite3", root=root)
        app.RequestHandlerClass.log_message = lambda *args: None
        with app.connect() as db:
            db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,'admin',?)",
                       ("Photo Browser Owner", "photo-owner@example.test", server.hash_password(PASSWORD), server.now_iso()))
        serving = threading.Thread(target=app.serve_forever, daemon=True); serving.start()
        owner = Client(app); assert owner.login(email="photo-owner@example.test")[0] == 200
        assert owner.request("PATCH", "/api/admin/products/fixture-look", {"images": [image, "assets/other.jpg"],
                            "color_variants": [{"name": "Navy", "hex": "#252232", "image": "assets/navy.jpg"}]})[0] == 200
        browser = connection = None
        try:
            browser, connection = start_chrome(directory / "chrome")
            connection.call("Page.enable"); connection.call("Network.enable")
            connection.call("Network.setCacheDisabled", {"cacheDisabled": True})
            connection.call("Page.addScriptToEvaluateOnNewDocument", {"source": "window.__photoErrors=[]; addEventListener('error',e=>{if(e.message)__photoErrors.push(e.message)});addEventListener('unhandledrejection',e=>__photoErrors.push(String(e.reason)));addEventListener('securitypolicyviolation',e=>__photoErrors.push('CSP '+e.violatedDirective));"})
            origin = f"http://127.0.0.1:{app.server_port}"
            checks = Checks(connection, origin)
            def viewport(width, height=950):
                connection.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": width <= 760})
                checks.evaluate("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
            def detail():
                checks.navigate("product.html?id=fixture-look", ready="!document.querySelector('#product-page-content').hidden && document.querySelector('#product-page-image').complete && !document.querySelector('#product-main-photo .vpi-open').disabled")
                checks.evaluate("document.querySelector('#privacy-banner [data-privacy-choice=necessary]')?.click()")
                checks.wait("document.querySelectorAll('#product-main-photo .vpi-marker:not([hidden])').length>=2")
            def shot(name):
                checks.evaluate("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
                data = connection.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
                (ROOT / "tmp" / name).write_bytes(base64.b64decode(data["data"]))
            def actual_click(selector):
                p = checks.evaluate(f"(()=>{{const r=document.querySelector({json.dumps(selector)}).getBoundingClientRect();return {{x:r.x+r.width/2,y:r.y+r.height/2}}}})()")
                connection.call("Input.dispatchMouseEvent", {"type": "mousePressed", "button": "left", "clickCount": 1, **p})
                connection.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "button": "left", "clickCount": 1, **p})
            def close_zoom():
                checks.click(".vpi-close")
                checks.wait("!document.querySelector('#velora-photo-inspector').open && !document.querySelector('.vpi-original').hasAttribute('src')")
            def labels_fit(layer, picture, clip=None):
                return checks.evaluate(f"""(()=>{{
                    const photo=document.querySelector({json.dumps(picture)}).getBoundingClientRect();
                    const clip={('document.querySelector('+json.dumps(clip)+').getBoundingClientRect()') if clip else 'photo'};
                    return [...document.querySelectorAll({json.dumps(layer + ' .vpi-marker:not([hidden]) .vpi-marker-label')})].every(label=>{{
                        const r=label.getBoundingClientRect();
                        return !label.hidden && r.width>0 && r.left>=Math.max(photo.left,clip.left)-1 && r.right<=Math.min(photo.right,clip.right)+1
                            && r.top>=Math.max(photo.top,clip.top)-1 && r.bottom<=Math.min(photo.bottom,clip.bottom)+1;
                    }});
                }})()""")
            viewport(1440)
            detail()
            checks.check(checks.evaluate("document.querySelectorAll('#product-main-photo .vpi-marker').length===2"), "Product photos show the linked items for their exact photo")
            checks.check(checks.evaluate("[...document.querySelectorAll('#product-main-photo .vpi-marker-label')].map(l=>l.textContent).join(',')==='Bag,Scarf' && [...document.querySelectorAll('#product-main-photo .vpi-marker')].every(b=>{const r=b.getBoundingClientRect();return r.width===44&&r.height===44})"), "Each object has a visible text label while retaining its 44px pin target")
            checks.check(labels_fit("#product-main-photo", "#product-page-image"), "Object labels stay within the displayed desktop photograph")
            geometry = checks.evaluate("(()=>{const i=document.querySelector('#product-page-image').getBoundingClientRect(),m=document.querySelector('#product-main-photo .vpi-marker').getBoundingClientRect();return {dx:Math.abs(m.x+m.width/2-i.x-i.width*.288),dy:Math.abs(m.y+m.height/2-i.y-i.height*.634)}})()")
            checks.check(geometry["dx"] < 1 and geometry["dy"] < 1, "Marker coordinates follow the actual displayed photograph")
            actual_click("#product-main-photo .vpi-marker-label")
            checks.check(checks.evaluate("!document.querySelector('#product-main-photo .vpi-item-card').hidden && document.querySelector('#product-main-photo .vpi-item-price').textContent.includes('49') && document.querySelector('#product-main-photo .vpi-item-link').getAttribute('href')==='product.html?id=fixture-bag' && !document.querySelector('#velora-photo-inspector')?.open"), "A marker opens the real product name, current euro price and product link without zooming")
            checks.evaluate("document.querySelector('#product-main-photo .vpi-marker').dispatchEvent(new PointerEvent('pointerenter',{pointerType:'mouse'}));document.querySelector('#product-main-photo .vpi-hotspots').dispatchEvent(new PointerEvent('pointerleave',{pointerType:'mouse'}))")
            checks.check(checks.evaluate("!document.querySelector('#product-main-photo .vpi-item-card').hidden"), "A mouse user can cross the gap from the marker to its clickable price card")
            checks.click("#product-main-photo .vpi-open")
            checks.wait("document.querySelector('#velora-photo-inspector')?.open && document.querySelector('.vpi-original').complete && document.querySelector('.vpi-original').naturalWidth>0 && !document.querySelector('.vpi-viewport').hidden")
            checks.check(checks.evaluate("document.querySelector('.vpi-original').getAttribute('src').endsWith('/assets/style.jpg') && !document.querySelector('.vpi-original').hasAttribute('srcset') && document.querySelector('.vpi-amount').textContent==='100%'"), "Zoom opens the original photograph in fit mode")
            actual_click('.vpi-toolbar [aria-label="Zoom in"]'); checks.click('.vpi-toolbar [aria-label="Zoom in"]')
            checks.check(checks.evaluate("document.querySelector('.vpi-amount').textContent==='200%' && document.querySelector('.vpi-viewport').scrollHeight>document.querySelector('.vpi-viewport').clientHeight"), "Zoom controls enlarge the photo and allow its details to be explored")
            drag = checks.evaluate("(()=>{const v=document.querySelector('.vpi-viewport'),r=v.getBoundingClientRect();return {x:r.left+r.width*.8,y:r.top+r.height*.5,before:v.scrollTop}})()")
            connection.call("Input.dispatchMouseEvent", {"type": "mousePressed", "button": "left", "clickCount": 1, "x": drag["x"], "y": drag["y"]})
            connection.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "button": "left", "buttons": 1, "x": drag["x"], "y": drag["y"] - 60})
            connection.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "button": "left", "clickCount": 1, "x": drag["x"], "y": drag["y"] - 60})
            checks.check(checks.evaluate("document.querySelector('.vpi-viewport').scrollTop") > drag["before"] + 30, "Mouse drag pans an enlarged photograph")
            checks.click('.vpi-toolbar [aria-label="Zoom out"]')
            checks.check(checks.evaluate("document.querySelector('.vpi-amount').textContent==='150%'"), "Zoom out decreases magnification")
            checks.click(".vpi-fit")
            checks.check(checks.evaluate("document.querySelector('.vpi-amount').textContent==='100%' && document.querySelector('.vpi-fit').disabled"), "Fit photo resets magnification")
            checks.click("#velora-photo-inspector .vpi-marker")
            checks.check(checks.evaluate("!document.querySelector('#velora-photo-inspector .vpi-item-card').hidden && document.querySelector('#velora-photo-inspector .vpi-item-link').href.endsWith('product.html?id=fixture-bag')"), "Accessory price markers remain clickable inside zoom")
            checks.evaluate("document.querySelector('#velora-photo-inspector .vpi-marker').focus()")
            connection.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape"})
            checks.check(checks.evaluate("document.querySelector('#velora-photo-inspector').open && document.querySelector('#velora-photo-inspector .vpi-item-card').hidden"), "Escape closes an item card before closing photo zoom")
            close_zoom()
            checks.check(checks.evaluate("!document.querySelector('#velora-photo-inspector').open && !document.querySelector('.vpi-original').hasAttribute('src') && document.activeElement===document.querySelector('#product-main-photo .vpi-open')"), "Closing zoom releases the original and returns focus")
            checks.click("#product-thumbnails button:nth-child(2)")
            checks.wait("document.querySelector('#product-main-photo').dataset.photoState==='ready'")
            checks.check(checks.evaluate("document.querySelectorAll('#product-main-photo .vpi-marker').length===0"), "Markers from one pose never appear on another photo")
            checks.click("#product-page-colors button:nth-child(2)")
            checks.check(checks.evaluate("document.querySelectorAll('#product-main-photo .vpi-marker').length===0"), "Changing a color also changes the applicable photo markers")
            detail()
            checks.click("#product-main-photo .vpi-marker")
            checks.click("#product-main-photo .vpi-item-link")
            checks.wait("location.search==='?id=fixture-bag' && document.querySelector('#product-page-title').textContent==='The Espresso Bag'")
            checks.check(True, "View item opens the linked accessory product page")
            checks.evaluate("""(()=>{
                const frame=document.createElement('div'),image=document.createElement('img'); frame.id='label-edge-fixture';frame.style.width='220px';
                image.style.width='100%';image.style.height='auto';image.src='assets/style.jpg';frame.append(image);document.body.append(frame);
                const target={id:'fixture-bag',name:'The Exceptionally Long Espresso Top-Handle Bag with a Gold Clasp',price:49};
                const unrelated=Array.from({length:24},()=>({image:'assets/other.jpg',x:.5,y:.5,product:target,label:'Other photo'}));
                const points=[...unrelated,{image:'assets/style.jpg',x:.005,y:.01,product:target,label:target.name},
                    {image:'assets/style.jpg',x:.995,y:.99,product:target,label:''}];
                window.__edgeController=VeloraImageInspector.mount({frame,image});__edgeController.update({src:'assets/style.jpg',hotspots:points});
                frame.scrollIntoView({block:'center',behavior:'instant'});
            })()""")
            checks.wait("document.querySelectorAll('#label-edge-fixture .vpi-marker:not([hidden])').length===2")
            checks.check(labels_fit("#label-edge-fixture", "#label-edge-fixture img"), "Labels flip and clamp inside narrow photos even when their pins sit at opposite corners")
            checks.check(checks.evaluate("[...document.querySelectorAll('#label-edge-fixture .vpi-marker-label')].every(l=>l.textContent==='The Exceptionally Long Espresso Top-Handle Bag with a Gold Clasp' && l.scrollWidth>l.clientWidth) && document.querySelectorAll('#label-edge-fixture .vpi-marker')[1].classList.contains('vpi-label-left') && document.querySelectorAll('#label-edge-fixture .vpi-marker')[1].getAttribute('aria-label').includes('The Exceptionally Long Espresso Top-Handle Bag with a Gold Clasp')"), "Long labels are compactly truncated with full accessible names and product-name fallback")
            checks.check(checks.evaluate("document.querySelectorAll('#label-edge-fixture .vpi-marker').length===2"), "Markers on earlier photographs do not consume another photo's 24-marker allowance")
            checks.evaluate("__edgeController.destroy();document.querySelector('#label-edge-fixture').remove();delete window.__edgeController")
            for width in (390, 320):
                viewport(width, 844); detail()
                actual_click("#product-main-photo .vpi-marker-label")
                checks.check(checks.evaluate(f"innerWidth==={width} && document.documentElement.clientWidth==={width} && document.documentElement.scrollWidth<={width} && (()=>{{const r=document.querySelector('#product-main-photo .vpi-item-card').getBoundingClientRect();return r.left>=0&&r.right<=innerWidth}})()"), f"Photo markers and price cards fit a true {width}px mobile viewport")
                checks.check(labels_fit("#product-main-photo", "#product-page-image"), f"Clickable object labels fit the {width}px mobile photograph")
                if width == 390:
                    checks.evaluate("document.querySelector('#product-main-photo').scrollIntoView({block:'start',behavior:'instant'})")
                    shot("shoppable-product-mobile.png")
                checks.click("#product-main-photo .vpi-open")
                checks.wait("document.querySelector('#velora-photo-inspector').open && !document.querySelector('.vpi-viewport').hidden")
                checks.check(checks.evaluate("(()=>{const d=document.querySelector('#velora-photo-inspector').getBoundingClientRect();return d.left>=0&&d.right<=innerWidth&&d.top>=0&&d.bottom<=innerHeight+1})()"), f"Zoom viewer fits the {width}px mobile screen")
                if width == 390:
                    checks.click("#velora-photo-inspector .vpi-marker"); shot("shoppable-zoom-mobile.png")
                    checks.click('.vpi-toolbar [aria-label="Zoom in"]'); checks.click('.vpi-toolbar [aria-label="Zoom in"]')
                    checks.evaluate("document.querySelector('#velora-photo-inspector .vpi-marker').scrollIntoView({block:'center',inline:'center',behavior:'instant'});new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
                    checks.click("#velora-photo-inspector .vpi-marker")
                    checks.check(checks.evaluate("(()=>{const c=document.querySelector('#velora-photo-inspector .vpi-item-card').getBoundingClientRect(),v=document.querySelector('.vpi-viewport').getBoundingClientRect();return c.left>=v.left&&c.right<=v.right&&c.top>=v.top&&c.bottom<=v.bottom})()"), "An accessory price card stays in view after zooming and panning on mobile")
                    checks.check(labels_fit("#velora-photo-inspector", ".vpi-original", ".vpi-viewport"), "Visible object labels stay inside the zoomed and panned mobile photo viewport")
                close_zoom()
            connection.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
            checks.check(checks.evaluate("getComputedStyle(document.querySelector('.vpi-marker-dot'),'::before').animationName==='none'"), "Reduced-motion preference disables marker animation")
            connection.call("Emulation.setEmulatedMedia", {"features": []})
            viewport(1440)
            checks.navigate("index.html", ready="document.documentElement.dataset.catalogState==='managed'")
            checks.click("#collection-refinements > summary"); checks.fill_search("#collection-search", "The Styling Suit")
            checks.wait("document.querySelectorAll('.look-tile').length===1")
            checks.click(".look-tile .product-size-help")
            checks.wait("document.querySelector('#product-dialog').open && document.querySelectorAll('.product-dialog-gallery .vpi-marker:not([hidden])').length===2")
            checks.click(".product-dialog-gallery .vpi-marker")
            checks.check(checks.evaluate("document.querySelector('.product-dialog-gallery .vpi-item-price').textContent.includes('49')"), "Homepage quick view also shows accessory prices")
            checks.click(".product-zoom-open")
            checks.wait("document.querySelector('#velora-photo-inspector').open && !document.querySelector('.vpi-viewport').hidden")
            close_zoom()
            checks.check(checks.evaluate("document.querySelector('#product-dialog').open && document.activeElement.classList.contains('product-zoom-open')"), "Closing quick-view zoom keeps the product dialog and restores its zoom button")
            checks.click(".product-dialog-close")
            name, value = owner.cookie.split("=", 1)
            assert connection.call("Network.setCookie", {"name": name, "value": value, "url": origin, "path": "/", "httpOnly": True, "sameSite": "Lax"})["success"]
            checks.navigate("admin.html#products", ready="!document.querySelector('#admin-shell').hidden && document.querySelectorAll('#admin-products-body tr').length>0")
            checks.click('[data-edit-product="fixture-look"]')
            checks.wait("document.querySelector('#admin-edit-dialog').open && document.querySelectorAll('.admin-hotspot-row').length===2")
            checks.check(checks.evaluate("document.querySelector('[data-hotspot-control=product]').textContent.includes('€49.00')"), "Admin marker editor offers real published products and their prices")
            checks.click("#admin-edit-close")
            checks.check(checks.evaluate("!document.querySelector('#admin-discard-dialog').open"), "An untouched marker editor closes without a false unsaved-change warning")
            checks.click('[data-edit-product="fixture-look"]')
            checks.evaluate("for(const [key,value] of Object.entries({x:'35',y:'62',product:'fixture-bag',label:'Second bag marker'})){const i=document.querySelector('[data-hotspot-control='+key+']');i.value=value;i.dispatchEvent(new Event('input',{bubbles:true}))}")
            checks.submit("#admin-edit-form")
            checks.check(checks.evaluate("document.querySelector('#admin-edit-dialog').open && document.querySelector('#admin-edit-error').textContent.includes('marker')"), "A pending marker cannot be silently dropped by saving the product")
            checks.click('[data-hotspot-action="save"]')
            checks.check(checks.evaluate("document.querySelectorAll('.admin-hotspot-row').length===3"), "Admin can add an object marker using accessible position fields")
            viewport(390, 844)
            checks.evaluate("document.querySelector('#admin-image-hotspots').scrollIntoView({block:'start',behavior:'instant'})")
            checks.check(checks.evaluate("document.documentElement.scrollWidth<=390 && document.querySelector('#admin-image-hotspots').getBoundingClientRect().right<=390"), "Admin photo-marker controls fit a 390px mobile editor")
            shot("shoppable-admin-mobile.png")
            checks.submit("#admin-edit-form"); checks.wait("!document.querySelector('#admin-edit-dialog').open")
            saved = next(p for p in owner.request("GET", "/api/admin/products")[1]["products"] if p["id"] == "fixture-look")
            checks.check(len(saved["image_hotspots"]) == 3 and saved["image_hotspots"][-1]["label"] == "Second bag marker", "Saving the product persists marker position, label and linked accessory")
            checks.click('[data-edit-product="fixture-look"]')
            checks.wait("document.querySelectorAll('.admin-hotspot-row').length===3")
            checks.click('[data-hotspot-action="remove"]'); checks.click("#admin-edit-close")
            checks.check(checks.evaluate("document.querySelector('#admin-discard-dialog').open"), "Removing a photo marker is protected as an unsaved change")
            checks.click("#admin-discard-confirm")
            assert owner.request("PATCH", "/api/admin/products/fixture-bag", {"price": 55})[0] == 200
            viewport(1440); detail(); checks.click("#product-main-photo .vpi-marker")
            checks.check(checks.evaluate("document.querySelector('#product-main-photo .vpi-item-price').textContent.includes('55')"), "Admin price changes flow through to photo-marker prices")
            saved = next(p for p in owner.request("GET", "/api/admin/products")[1]["products"] if p["id"] == "fixture-look")
            assert owner.request("PATCH", "/api/admin/products/fixture-look", {"item_image": "assets/other.jpg", "image_hotspots": [*saved["image_hotspots"],
                {"image": "assets/navy.jpg", "x": .5, "y": .5, "product_id": "fixture-look", "label": "Suit"},
                {"image": "assets/other.jpg", "x": .5, "y": .5, "product_id": "fixture-look", "label": "Suit"}]})[0] == 200
            detail(); checks.click("#product-page-colors button:nth-child(2)")
            checks.wait("document.querySelector('#product-main-photo').dataset.photoState==='ready' && document.querySelectorAll('#product-main-photo .vpi-marker').length===1")
            actual_click("#product-main-photo .vpi-marker-label")
            checks.check(checks.evaluate("document.querySelector('#product-main-photo .vpi-item-link').getAttribute('href')==='product.html?id=fixture-look&color=Navy'"), "An alternate-color garment label links to the selected color rather than the base-color item photograph")
            checks.click("#product-main-photo .vpi-open")
            checks.wait("document.querySelector('#velora-photo-inspector').open && !document.querySelector('.vpi-viewport').hidden")
            actual_click("#velora-photo-inspector .vpi-marker-label")
            checks.check(checks.evaluate("document.querySelector('#velora-photo-inspector .vpi-item-link').getAttribute('href')==='product.html?id=fixture-look&color=Navy'"), "Zoom preserves the selected-color label link")
            close_zoom(); checks.click("#product-main-photo .vpi-marker-label"); checks.click("#product-main-photo .vpi-item-link")
            checks.wait("new URLSearchParams(location.search).get('color')==='Navy' && document.querySelector('#product-page-image').currentSrc.endsWith('/assets/navy.jpg')")
            checks.check(True, "Opening a garment label retains the chosen color and photograph")
            checks.navigate("index.html", ready="document.documentElement.dataset.catalogState==='managed'")
            checks.click("#collection-refinements > summary"); checks.fill_search("#collection-search", "The Styling Suit")
            checks.wait("document.querySelectorAll('.look-tile').length===1"); checks.click(".look-tile .product-size-help")
            checks.wait("document.querySelector('#product-dialog').open")
            checks.click('.product-dialog-options [data-option-value="Navy"]')
            checks.wait("document.querySelectorAll('.product-dialog-gallery .vpi-marker:not([hidden])').length===1 && document.querySelector('.product-dialog-image').complete && document.querySelector('.product-dialog-image').currentSrc.endsWith('/assets/navy.jpg')")
            checks.evaluate("document.querySelector('.product-dialog-gallery .vpi-marker-label').scrollIntoView({block:'center',behavior:'instant'});new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
            shot("object-label-quickview.png")
            actual_click(".product-dialog-gallery .vpi-marker-label")
            checks.check(checks.evaluate("document.querySelector('.product-dialog-gallery .vpi-item-link').getAttribute('href')==='product.html?id=fixture-look&color=Navy'"), "Homepage quick-view labels also retain the selected garment color")
            checks.click(".product-dialog-close")
            card = '.look-tile[data-product-id="fixture-look"]'
            frame = card + ' .look-tile-image'
            checks.wait(f"document.querySelectorAll({json.dumps(frame + ' .vpi-marker:not([hidden])')}).length===1")
            checks.evaluate(f"document.querySelector({json.dumps(frame)}).scrollIntoView({{block:'center',behavior:'instant'}});new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
            checks.check(checks.evaluate(f"!document.querySelector({json.dumps(frame + ' .vpi-open')}) && [...document.querySelectorAll({json.dumps(frame + ' .vpi-marker')})].every(b=>!b.closest('a'))"), "Collection-card labels sit outside the photo link without adding a zoom control or nested interactive elements")
            actual_click(frame + " .vpi-marker-label")
            checks.check(checks.evaluate(f"location.pathname==='/index.html' && !document.querySelector({json.dumps(frame + ' .vpi-item-card')}).hidden && document.querySelector({json.dumps(frame + ' .vpi-item-link')}).getAttribute('href')==='product.html?id=fixture-look&color=Navy' && !document.querySelector('#product-dialog').open"), "A collection-card label opens its current price and selected-color link without navigating or opening quick view")
            checks.click(card + ' [data-option-value="Brown"]')
            checks.wait(f"document.querySelectorAll({json.dumps(frame + ' .vpi-marker:not([hidden])')}).length===3")
            checks.check(checks.evaluate(f"[...document.querySelectorAll({json.dumps(frame + ' .vpi-marker-label')})].map(l=>l.textContent).join(',')==='Bag,Scarf,Second bag marker'"), "Changing a collection-card color refreshes its own object labels")
            checks.click(frame + ' [data-gallery-index="1"]')
            checks.wait(f"document.querySelectorAll({json.dumps(frame + ' .vpi-marker:not([hidden])')}).length===1 && document.querySelector({json.dumps(frame + ' .vpi-marker-label')}).textContent==='Suit'")
            checks.check(checks.evaluate(f"document.querySelector({json.dumps(frame + ' [data-gallery-main]')}).currentSrc.endsWith('/assets/other.jpg')"), "Selecting a collection-card pose refreshes its exact-photo object label")
            checks.click(frame + ' [data-gallery-index="0"]')
            checks.wait(f"document.querySelectorAll({json.dumps(frame + ' .vpi-marker:not([hidden])')}).length===3")
            before_saved = checks.evaluate(f"document.querySelector({json.dumps(frame + ' .save-look')}).getAttribute('aria-pressed')")
            actual_click(frame + " .save-look")
            checks.check(checks.evaluate(f"document.querySelector({json.dumps(frame + ' .save-look')}).getAttribute('aria-pressed')") != before_saved, "The collection-card wishlist remains physically clickable above label overlays")
            actual_click(frame + ' [data-gallery-action="next"]')
            checks.wait(f"document.querySelector({json.dumps(frame)}).dataset.currentGalleryIndex==='1'")
            checks.check(True, "Collection-card gallery controls remain physically clickable with object labels")
            checks.evaluate(f"window.__previousLabelFrame=document.querySelector({json.dumps(frame)})")
            checks.fill_search("#collection-search", "No matching outfit")
            checks.wait("document.querySelectorAll('.look-tile').length===0")
            checks.check(checks.evaluate("cardPhotoInspectors.size===0 && !__previousLabelFrame.querySelector('.vpi-hotspots')"), "Filtering away cards destroys their label layers and releases their inspector controllers")
            checks.fill_search("#collection-search", "The Styling Suit")
            checks.wait(f"document.querySelectorAll({json.dumps(frame + ' .vpi-marker:not([hidden])')}).length===3")
            checks.check(checks.evaluate("cardPhotoInspectors.size===document.querySelectorAll('#looks-grid .look-tile-image').length && [...cardPhotoInspectors.keys()].every(f=>f.isConnected) && document.querySelectorAll('.look-tile .vpi-hotspots').length===1"), "Re-rendering collection filters creates one current label layer per card without stale controllers")
            checks.evaluate("delete window.__previousLabelFrame")
            for width in (390, 320):
                viewport(width, 844)
                checks.evaluate(f"document.querySelector({json.dumps(frame)}).scrollIntoView({{block:'center',behavior:'instant'}});new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
                checks.check(labels_fit(frame, frame + " [data-gallery-main]"), f"Collection-card object labels fit their compact image at {width}px")
                checks.click(card + ' [data-option-value="Navy"]')
                checks.wait(f"document.querySelectorAll({json.dumps(frame + ' .vpi-marker:not([hidden])')}).length===1")
                checks.evaluate(f"document.querySelector({json.dumps(frame)}).scrollIntoView({{block:'center',behavior:'instant'}});new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
                actual_click(frame + " .vpi-marker-label")
                checks.check(checks.evaluate(f"!document.querySelector({json.dumps(frame + ' .vpi-item-card')}).hidden && document.querySelector({json.dumps(frame + ' .vpi-item-link')}).getAttribute('href')==='product.html?id=fixture-look&color=Navy' && document.querySelector({json.dumps(frame)}).dataset.currentGalleryIndex==='0'"), f"The {width}px garment label stays clickable beside gallery arrows without selecting another photo")
                if width == 390:
                    shot("object-label-cards-mobile.png")
                checks.click(card + ' [data-option-value="Brown"]')
                checks.wait(f"document.querySelectorAll({json.dumps(frame + ' .vpi-marker:not([hidden])')}).length===3")
            viewport(1440)
            checks.evaluate(f"document.querySelector({json.dumps(frame)}).scrollIntoView({{block:'center',behavior:'instant'}});new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
            normal_click = checks.evaluate(f"(()=>{{const r=document.querySelector({json.dumps(frame + ' [data-gallery-main]')}).getBoundingClientRect();return {{x:r.left+r.width*.8,y:r.top+r.height*.25}}}})()")
            connection.call("Input.dispatchMouseEvent", {"type": "mousePressed", "button": "left", "clickCount": 1, **normal_click})
            connection.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "button": "left", "clickCount": 1, **normal_click})
            checks.wait("location.pathname==='/product.html' && new URLSearchParams(location.search).get('id')==='fixture-look'")
            checks.check(True, "Clicking an ordinary collection photograph still opens its product page")
            long_name = ("The Exceptionally Long Espresso Styling Suit with Carefully Considered Tailoring and a Coordinated Wide-Leg Silhouette for Special Occasions " * 2)[:160]
            assert owner.request("PATCH", "/api/admin/products/fixture-look", {"name": long_name})[0] == 200
            viewport(320, 844)
            checks.navigate("index.html", ready="document.documentElement.dataset.catalogState==='managed'")
            checks.click("#collection-refinements > summary"); checks.fill_search("#collection-search", "Exceptionally Long")
            checks.wait("document.querySelectorAll('.look-tile').length===1")
            checks.evaluate("document.querySelector('#looks-grid').style.gridTemplateColumns='repeat(2,minmax(0,1fr))'")
            checks.click(card + ' [data-option-value="Navy"]')
            checks.wait(f"document.querySelectorAll({json.dumps(frame + ' .vpi-marker:not([hidden])')}).length===1")
            checks.evaluate(f"document.querySelector({json.dumps(frame)}).scrollIntoView({{block:'center',behavior:'instant'}});new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
            actual_click(frame + " .vpi-marker-label")
            checks.check(checks.evaluate(f"(()=>{{const c=document.querySelector({json.dumps(frame + ' .vpi-item-card')}),r=c.getBoundingClientRect(),f=document.querySelector({json.dumps(frame)}).getBoundingClientRect();return innerWidth===320 && r.left>=f.left&&r.right<=f.right&&r.top>=f.top&&r.bottom<=f.bottom&&c.scrollHeight>c.clientHeight&&c.scrollWidth<=c.clientWidth}})()"), "A long product name uses a contained scrollable price card within a true 320px two-column photo")
            checks.evaluate(f"document.querySelector({json.dumps(frame + ' .vpi-item-link')}).scrollIntoView({{block:'nearest',behavior:'instant'}});new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
            shot("object-label-long-card-mobile.png")
            actual_click(frame + " .vpi-item-link")
            checks.wait("location.pathname==='/product.html' && new URLSearchParams(location.search).get('color')==='Navy'")
            checks.check(True, "The full-name price card's product link remains physically reachable in a narrow collection card")
            checks.check(checks.evaluate("__photoErrors.length===0"), "Shoppable photos, zoom and admin editing produce no runtime or CSP errors")
            report = {"passed": len(checks.passed), "checks": checks.passed}
            (ROOT / "tmp/shoppable-image-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report))
        finally:
            if connection: connection.socket.close()
            if browser: browser.terminate(); browser.wait(timeout=10)
            app.shutdown(); app.server_close(); serving.join(timeout=5)


if __name__ == "__main__":
    main()
