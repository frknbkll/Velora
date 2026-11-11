"""Check outfit grouping and item-photo editing using disposable site data."""
import base64
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
fixture_site = runpy.run_path(str(ROOT / "tests/run-admin-auto-color.py"))["fixture_site"]
fixture_picture = runpy.run_path(str(ROOT / "tests/run-outfit-items.py"))["fixture_picture"]


def main():
    (ROOT / "tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="outfit-admin-", dir=ROOT / "tmp", ignore_cleanup_errors=True) as folder:
        directory = Path(folder); root = fixture_site(directory)
        for name, color in [("look", (89, 59, 42)), ("suit", (74, 49, 37)), ("other", (46, 59, 76)),
                            ("bag", (104, 71, 52)), ("bag-detail", (91, 61, 43))]:
            fixture_picture(root / "assets" / (name + ".png"), color)
        products = []
        for identifier, name, source, parent, item_image, photos, price, sizes, stock in [
            ("admin-look-a", "The Espresso Test Outfit", "assets/look.png", "", "assets/suit.png", ["assets/look.png", "assets/suit.png"], 149, ["S", "M"], None),
            ("admin-look-b", "The Navy Test Outfit", "assets/other.png", "", "", ["assets/other.png"], 129, ["M", "L"], None),
            ("admin-bag", "The Standalone Test Bag", "assets/bag.png", "admin-look-a", "assets/bag.png", ["assets/bag.png", "assets/bag-detail.png"], 49, ["One size"], 7),
        ]:
            products.append({"id": identifier, "name": name, "image": source, "images": photos,
                             "parent_product_id": parent, "item_image": item_image, "price": price, "sizes": sizes, "stock": stock,
                             "founder": "Grouped Admin Fixture", "collection": "THE POLISHED EDIT", "base_color": "Brown",
                             "color_hex": "#5b3d2b", "color_key": identifier, "published": True,
                             "description": "A disposable grouped product for browser checks.", "image_hotspots": []})
        (root / "product-catalog.json").write_text(json.dumps({"products": products}), encoding="utf-8")
        app = server.make_server(port=0, database=directory / "accounts.sqlite3", root=root)
        app.RequestHandlerClass.log_message = lambda *args: None
        with app.connect() as db:
            db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,'admin',?)",
                       ("Grouped Browser Owner", "grouped-owner@example.test", server.hash_password(PASSWORD), server.now_iso()))
        serving = threading.Thread(target=app.serve_forever, daemon=True); serving.start()
        owner = Client(app); assert owner.login(email="grouped-owner@example.test")[0] == 200
        browser = connection = None
        try:
            browser, connection = start_chrome(directory / "chrome")
            connection.call("Page.enable"); connection.call("Network.enable")
            connection.call("Network.setCacheDisabled", {"cacheDisabled": True})
            connection.call("Page.addScriptToEvaluateOnNewDocument", {"source": "window.__outfitAdminErrors=[];addEventListener('error',e=>{if(e.message)__outfitAdminErrors.push(e.message)});addEventListener('unhandledrejection',e=>__outfitAdminErrors.push(String(e.reason)));addEventListener('securitypolicyviolation',e=>__outfitAdminErrors.push('CSP '+e.violatedDirective));"})
            origin = f"http://127.0.0.1:{app.server_port}"; checks = Checks(connection, origin)
            errors = []
            def go(path, ready):
                errors.extend(checks.evaluate("window.__outfitAdminErrors || []") or [])
                checks.navigate(path, ready=ready)
            def viewport(width, height=950):
                connection.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": width <= 899})
                checks.evaluate("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
            name, value = owner.cookie.split("=", 1)
            assert connection.call("Network.setCookie", {"name": name, "value": value, "url": origin, "path": "/", "httpOnly": True, "sameSite": "Lax"})["success"]
            viewport(1440)
            go("admin.html?capacity=1#products", "!document.querySelector('#admin-shell').hidden && document.querySelectorAll('#admin-products-body tr').length===3")
            checks.evaluate("document.querySelector('#privacy-banner [data-privacy-choice=necessary]')?.click();document.documentElement.style.scrollBehavior='auto'")
            def open_product(identifier="admin-bag"):
                checks.click(f'[data-edit-product="{identifier}"]')
                checks.wait("document.querySelector('#admin-edit-dialog').open")
            def unchanged_close():
                checks.click("#admin-edit-close")
                checks.check(checks.evaluate("!document.querySelector('#admin-edit-dialog').open && !document.querySelector('#admin-discard-dialog').open"), "Saved grouping and item-photo controls do not create a false unsaved-change warning")
            def saved(identifier="admin-bag"):
                return next(p for p in owner.request("GET", "/api/admin/products")[1]["products"] if p["id"] == identifier)
            def save():
                checks.submit("#admin-edit-form")
                checks.wait("!document.querySelector('#admin-edit-dialog').open")
            def upload():
                checks.evaluate("""(async()=>{
                    const canvas=document.createElement('canvas');canvas.width=100;canvas.height=160;
                    const context=canvas.getContext('2d');context.fillStyle='#eee7da';context.fillRect(0,0,100,160);
                    context.fillStyle='#704f35';context.fillRect(20,30,60,90);
                    const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
                    const transfer=new DataTransfer();transfer.items.add(new File([blob],'extra-item-photo.png',{type:'image/png'}));
                    const input=document.querySelector('#admin-image-files');input.files=transfer.files;input.dispatchEvent(new Event('change',{bubbles:true}));
                })()""")
                checks.wait("!document.querySelector('#admin-image-files').disabled && document.querySelectorAll('#admin-image-gallery .admin-photo-card').length===3")
            checks.check(checks.evaluate("document.querySelector('[data-edit-product=admin-bag]').closest('tr').textContent.includes('Item in The Espresso Test Outfit')"), "Admin product rows identify their parent outfit")
            open_product()
            checks.check(checks.evaluate("document.querySelector('#admin-edit-parent-product').value==='admin-look-a' && document.querySelector('#admin-edit-item-image').value==='assets/bag.png'"), "Opening a separate product loads its saved parent and individual image")
            unchanged_close(); open_product()
            checks.fill("#admin-edit-form", {"parent_product_id": "admin-look-b", "item_image": "assets/bag-detail.png", "price": "55"})
            checks.click('#admin-image-gallery [data-image-action="right"][data-image-index="0"]')
            checks.check(checks.evaluate("document.querySelector('#admin-edit-parent-product').value==='admin-look-b' && document.querySelector('#admin-edit-item-image').value==='assets/bag-detail.png'"), "Reordering photos keeps the selected outfit and individual item image")
            upload()
            checks.check(checks.evaluate("document.querySelector('#admin-edit-parent-product').value==='admin-look-b' && document.querySelector('#admin-edit-item-image').value==='assets/bag-detail.png'"), "Uploading a gallery image does not reset grouping or the selected individual image")
            extra_photo = checks.evaluate("document.querySelector('#admin-edit-item-image').options[3].value")
            save(); product = saved()
            checks.check(product["parent_product_id"] == "admin-look-b" and product["item_image"] == "assets/bag-detail.png" and product["price"] == 55,
                         "Saving persists the changed parent, item image and edited price")
            checks.check(product["stock"] == 7 and product["sizes"] == ["One size"] and product["base_color"] == "Brown", "Grouping edits preserve stock, size and color")
            open_product()
            checks.check(checks.evaluate("document.querySelector('#admin-edit-parent-product').value==='admin-look-b' && document.querySelector('#admin-edit-item-image').value==='assets/bag-detail.png'"), "Saved parent and item image survive refresh and reopening")
            checks.fill("#admin-edit-form", {"item_image": extra_photo})
            checks.click('#admin-image-gallery [data-image-action="remove"][data-image-index="2"]')
            checks.check(checks.evaluate("document.querySelector('#admin-edit-item-image').value==='' && document.querySelector('#admin-edit-parent-product').value==='admin-look-b'"), "Removing the selected item photo clears its reference while retaining the outfit")
            save(); product = saved()
            checks.check(product["item_image"] == "" and extra_photo not in product["images"] and product["price"] == 55 and product["stock"] == 7, "The cleared reference and gallery removal save without losing price or stock")
            open_product()
            checks.fill("#admin-edit-form", {"item_image": "assets/bag.png"})
            checks.click('#admin-image-gallery [data-image-action="remove"][data-image-index="0"]')
            checks.check(checks.evaluate("document.querySelector('#admin-edit-item-image').value==='assets/bag.png'"), "Removing another photo leaves the selected individual image intact")
            save(); product = saved()
            checks.check(product["image"] == "assets/bag.png" and product["item_image"] == "assets/bag.png" and product["parent_product_id"] == "admin-look-b", "A retained item photo remains valid when it becomes the cover")
            open_product(); unchanged_close()
            full_photo = [{"image": "assets/look.png", "x": .4, "y": .5, "product_id": "admin-look-a", "label": f"Object {index + 1}"} for index in range(24)]
            assert owner.request("PATCH", "/api/admin/products/admin-look-a", {"image_hotspots": full_photo})[0] == 200
            # Refresh the list so this editor loads the saved photo capacity.
            go("admin.html#products", "!document.querySelector('#admin-shell').hidden && document.querySelectorAll('#admin-products-body tr').length===3")
            open_product("admin-look-a")
            capacity = checks.evaluate("({rows:document.querySelectorAll('.admin-hotspot-row').length,disabled:document.querySelector('[data-hotspot-action=save]').disabled,count:document.querySelector('.admin-hotspot-list-heading').textContent,photo:document.querySelector('[data-hotspot-control=photo]').value})")
            checks.check(capacity["rows"] == 24 and capacity["disabled"] and "24 of 24 markers on this photo" in capacity["count"], "A photograph with 24 labels prevents adding more on that photograph: " + str(capacity))
            checks.click('[data-hotspot-action="edit"]')
            checks.check(checks.evaluate("!document.querySelector('[data-hotspot-action=save]').disabled"), "An existing label can still be edited when its photograph is full")
            checks.evaluate("(()=>{const i=document.querySelector('[data-hotspot-control=label]');i.value='Edited full-photo label';i.dispatchEvent(new Event('input',{bubbles:true}))})()")
            checks.click('[data-hotspot-action="save"]')
            checks.evaluate("(()=>{const i=document.querySelector('[data-hotspot-control=photo]');i.value='assets/suit.png';i.dispatchEvent(new Event('change',{bubbles:true}))})()")
            checks.check(checks.evaluate("!document.querySelector('[data-hotspot-action=save]').disabled && document.querySelector('.admin-hotspot-list-heading').textContent.includes('0 of 24 markers on this photo')"), "A full first photograph leaves room for labels on another photograph")
            checks.evaluate("for(const [key,value] of Object.entries({product:'admin-look-a',label:'Standalone suit'})){const i=document.querySelector('[data-hotspot-control='+key+']');i.value=value;i.dispatchEvent(new Event('input',{bubbles:true}))}")
            checks.click('[data-hotspot-action="save"]'); save()
            labelled = saved("admin-look-a")["image_hotspots"]
            checks.check(len(labelled) == 25 and labelled[0]["label"] == "Edited full-photo label" and labelled[-1]["image"] == "assets/suit.png", "Saving retains more than 24 labels across photographs without truncating existing edits")
            open_product("admin-look-a")
            checks.check(checks.evaluate("document.querySelectorAll('.admin-hotspot-row').length===25 && document.querySelector('.admin-hotspot-list-heading').textContent.includes('25 of 288 total')"), "Reopening the product preserves every label across its gallery")
            unchanged_close()
            checks.click("#admin-add-product"); checks.wait("document.querySelector('#admin-edit-dialog').open")
            checks.fill("#admin-edit-form", {"name": "The New Grouped Piece", "founder": "Grouped Admin Fixture", "price": "29", "description": "A new individually shoppable test piece.", "base_color": "Ivory", "parent_product_id": "admin-look-a"})
            # This fresh editor has no photos, so a single upload finishes at one card.
            checks.evaluate("""(async()=>{const c=document.createElement('canvas');c.width=100;c.height=160;const x=c.getContext('2d');x.fillStyle='#eee7da';x.fillRect(0,0,100,160);const b=await new Promise(r=>c.toBlob(r,'image/png'));const d=new DataTransfer();d.items.add(new File([b],'new-piece.png',{type:'image/png'}));const i=document.querySelector('#admin-image-files');i.files=d.files;i.dispatchEvent(new Event('change',{bubbles:true}))})()""")
            checks.wait("!document.querySelector('#admin-image-files').disabled && document.querySelectorAll('#admin-image-gallery .admin-photo-card').length===1")
            checks.evaluate("document.querySelectorAll('#admin-size-options input').forEach(i=>i.checked=i.value==='One size')")
            new_source = checks.evaluate("document.querySelector('#admin-edit-item-image').options[1].value")
            checks.fill("#admin-edit-form", {"item_image": new_source})
            for width in (390, 320):
                viewport(width, 844)
                checks.check(checks.evaluate(f"innerWidth==={width} && document.documentElement.clientWidth==={width} && document.documentElement.scrollWidth<={width} && ['admin-edit-parent-product','admin-edit-item-image'].every(id=>{{const r=document.getElementById(id).getBoundingClientRect();return r.width>0&&r.left>=0&&r.right<=innerWidth}})"), f"Outfit and individual-photo controls fit a true {width}px admin editor")
                if width == 390:
                    checks.evaluate("document.querySelector('#admin-edit-parent-product').scrollIntoView({block:'center',behavior:'instant'});new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
                    shot = connection.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
                    (ROOT / "tmp/outfit-admin-mobile.png").write_bytes(base64.b64decode(shot["data"]))
            save()
            created = next(p for p in owner.request("GET", "/api/admin/products")[1]["products"] if p["name"] == "The New Grouped Piece")
            checks.check(created["parent_product_id"] == "admin-look-a" and created["item_image"] == new_source and created["sizes"] == ["One size"], "A new individual product can be created directly inside an existing outfit")
            open_product(created["id"])
            checks.fill("#admin-edit-form", {"parent_product_id": "admin-look-b"})
            checks.click("#admin-edit-close")
            checks.check(checks.evaluate("document.querySelector('#admin-discard-dialog').open"), "Changing the parent outfit is protected as an unsaved edit")
            checks.click("#admin-discard-confirm")
            with app.connect() as db:
                db.execute("UPDATE products SET published=1 WHERE id=?", (created["id"],))
            viewport(1440)
            go("index.html", "document.documentElement.dataset.catalogState==='managed'")
            checks.check(checks.evaluate("document.querySelectorAll('.look-tile').length===2 && !document.querySelector('.look-tile[data-product-id=admin-bag]') && lookByKey.has('product:admin-bag') && lookByKey.has(" + json.dumps("product:" + created["id"]) + ")"), "The collection keeps one card per outfit while both separately saved items remain shoppable")
            errors.extend(checks.evaluate("window.__outfitAdminErrors || []") or [])
            checks.check(not errors, "Grouped admin editing and collection refresh produce no runtime or CSP errors: " + str(errors))
            report = {"passed": len(checks.passed), "checks": checks.passed}
            (ROOT / "tmp/outfit-admin-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report))
        finally:
            if connection: connection.socket.close()
            if browser: browser.terminate(); browser.wait(timeout=10)
            app.shutdown(); app.server_close(); serving.join(timeout=5)


if __name__ == "__main__":
    main()
