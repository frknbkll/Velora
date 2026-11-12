"""Exercise automatic product colors using a disposable site, uploads and database.

Run with ``python py/tests/run-admin-auto-color.py``. Only public app resources are
copied into the fixture. No live account, product, upload or API key is used.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file


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

import server
from test_auth_server import Client, PASSWORD

helpers = runpy.run_path(str(ROOT / "py/tests/run-account-browser.py"))
Checks, start_chrome = helpers["Checks"], helpers["start_chrome"]


def fixture_site(directory):
    root = directory / "site"
    root.mkdir()
    for pattern in ("*.html", "*.css", "*.js"):
        for source in (ROOT / pattern.removeprefix("*.")).glob(pattern):
            shutil.copy2(source, root / source.name)
    for name in ("brand", "fonts"):
        source = ROOT / "assets" / name
        if source.is_dir():
            shutil.copytree(source, root / "assets" / name)
    (root / "assets").mkdir(exist_ok=True)
    width, height = 100, 160
    pixels = b"".join(b"\0" + bytes((70, 70, 70)) * width for _ in range(height))
    def chunk(kind, data):
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))
    (root / "assets/fixture.png").write_bytes(
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!2I5B", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))
    (root / "product-catalog.json").write_text(json.dumps({"products": [{
        "id": "auto-color-fixture", "name": "The Fixture Maxi Dress", "image": "assets/fixture.png",
        "founder": "Studio Fixture", "collection": "THE EVENING EDIT", "price": 89,
        "description": "A disposable product for automatic color checks.", "published": True,
        "base_color": "Fixture Grey", "color_hex": "#464646",
    }]}), encoding="utf-8")
    return root


def main():
    (ROOT / "tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="admin-auto-color-", dir=ROOT / "tmp", ignore_cleanup_errors=True) as folder:
        directory = Path(folder)
        root = fixture_site(directory)
        app = server.make_server(port=0, database=directory / "accounts.sqlite3", root=root)
        app.RequestHandlerClass.log_message = lambda *args: None
        with app.connect() as db:
            db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,'admin',?)", (
                "Color Fixture Owner", "color-owner@example.test", server.hash_password(PASSWORD), server.now_iso()))
        serving = threading.Thread(target=app.serve_forever, daemon=True)
        serving.start()
        owner = Client(app)
        assert owner.login(email="color-owner@example.test")[0] == 200
        browser = connection = None
        try:
            browser, connection = start_chrome(directory / "chrome")
            connection.call("Page.enable")
            connection.call("Network.enable")
            connection.call("Network.setCacheDisabled", {"cacheDisabled": True})
            connection.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
                window.__colorErrors=[]; window.__colorRequests=[];
                addEventListener('error',e=>{if(e.message)__colorErrors.push(e.message)});
                addEventListener('unhandledrejection',e=>__colorErrors.push(String(e.reason)));
                addEventListener('securitypolicyviolation',e=>__colorErrors.push('CSP '+e.violatedDirective));
                const fetchBeforeColor=window.fetch;
                window.fetch=function(input,options){
                  const url=new URL(input instanceof Request?input.url:input,location.href);
                  __colorRequests.push(url.origin===location.origin?url.pathname:url.href);
                  if(url.origin!==location.origin) throw new Error('Unexpected external request');
                  return fetchBeforeColor.call(this,input,options);
                };
            """})
            origin = f"http://127.0.0.1:{app.server_port}"
            checks = Checks(connection, origin)
            name, value = owner.cookie.split("=", 1)
            assert connection.call("Network.setCookie", {
                "name": name, "value": value, "url": origin, "path": "/", "httpOnly": True, "sameSite": "Lax",
            })["success"]

            def navigate():
                checks.navigate("admin.html#products", ready="!document.querySelector('#admin-shell').hidden && document.querySelectorAll('#admin-products-body tr').length>0")
                checks.evaluate("document.querySelector('#privacy-banner [data-privacy-choice=necessary]')?.click();document.documentElement.style.scrollBehavior='auto'")
                checks.wait("window.VeloraProductColor && typeof window.VeloraProductColor.detect==='function'")

            def new_product():
                checks.click("#admin-add-product")
                checks.wait("document.querySelector('#admin-edit-dialog').open")
                checks.fill("#admin-edit-form", {"name": "Color Test Maxi Dress"})

            def discard():
                checks.click("#admin-edit-close")
                if checks.evaluate("document.querySelector('#admin-discard-dialog').open"):
                    checks.click("#admin-discard-confirm")
                checks.wait("!document.querySelector('#admin-edit-dialog').open")

            def upload(selector, color, filename="garment.png", blank=False):
                checks.evaluate(f"""(async()=>{{
                    const canvas=document.createElement('canvas');canvas.width=320;canvas.height=480;
                    const c=canvas.getContext('2d');c.fillStyle='#ffffff';c.fillRect(0,0,320,480);
                    if(!{str(blank).lower()}){{
                      c.fillStyle='#d9a17e';c.beginPath();c.arc(160,63,23,0,Math.PI*2);c.fill();
                      c.fillRect(91,132,23,150);c.fillRect(206,132,23,150);
                      c.fillStyle='#322824';c.fillRect(138,34,44,13);
                      c.fillStyle={json.dumps(color)};c.beginPath();c.moveTo(113,106);c.lineTo(207,106);
                      c.lineTo(236,441);c.lineTo(84,441);c.closePath();c.fill();
                    }}
                    const blob=await new Promise(r=>canvas.toBlob(r,'image/png'));
                    const files=new DataTransfer();files.items.add(new File([blob],{json.dumps(filename)},{{type:'image/png'}}));
                    const input=document.querySelector({json.dumps(selector)});input.files=files.files;
                    input.dispatchEvent(new Event('change',{{bubbles:true}}));
                }})()""")

            def upload_ready(selector="#admin-image-files"):
                checks.wait(f"!document.querySelector({json.dumps(selector)}).disabled")

            def values(alternate=False):
                ids = ("admin-color-name", "admin-color-hex") if alternate else ("admin-edit-base-color", "admin-edit-color-hex")
                return checks.evaluate("[" + ",".join(f"document.getElementById({json.dumps(i)}).value" for i in ids) + "]")

            def mobile_photo(filename, selector):
                connection.call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
                checks.evaluate(f"document.querySelector({json.dumps(selector)}).scrollIntoView({{block:'center',behavior:'instant'}})")
                checks.evaluate("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
                screenshot = connection.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
                (ROOT / "tmp" / filename).write_bytes(base64.b64decode(screenshot["data"]))
                checks.check(checks.evaluate("innerWidth===390 && document.documentElement.clientWidth===390 && document.documentElement.scrollWidth<=390"), "Automatic color controls fit a true 390px mobile viewport")
                connection.call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 950, "deviceScaleFactor": 1, "mobile": False})

            navigate()
            new_product()
            upload("#admin-image-files", "#7b233b")
            checks.wait("document.querySelector('#admin-image-count').textContent.startsWith('1 of') && document.querySelector('#admin-edit-base-color').value!=='Original'")
            upload_ready()
            detected = values()
            checks.check(detected[0] == "Burgundy" and detected[1] != "#ffffff", "First uploaded garment photo fills its color name and swatch automatically")
            checks.check(checks.evaluate("document.querySelector('#admin-auto-color-status').textContent.length>0 && !document.querySelector('#admin-edit-base-color').disabled && !document.querySelector('#admin-edit-color-hex').disabled"), "Detected color is announced and remains editable")
            mobile_photo("admin-auto-color-primary-mobile.png", "#admin-auto-color-status")
            upload("#admin-image-files", "#172b4d", "cover-alternate.png")
            checks.wait("document.querySelector('#admin-image-count').textContent.startsWith('2 of')")
            upload_ready()
            checks.click('#admin-image-gallery [data-image-action="cover"][data-image-index="1"]')
            checks.wait("document.querySelector('#admin-edit-base-color').value==='Navy' && !document.querySelector('#admin-edit-save').disabled")
            checks.check(True, "Choosing a different cover on a new product updates its automatically detected primary color")
            checks.fill("#admin-edit-form", {"base_color": "Custom Plum", "color_hex": "#663355"})
            upload("#admin-image-files", "#172b4d", "second.png")
            checks.wait("document.querySelector('#admin-image-count').textContent.startsWith('3 of')")
            upload_ready()
            checks.check(values() == ["Custom Plum", "#663355"], "Adding another gallery photo preserves the chosen primary color")
            checks.click('#admin-image-gallery [data-image-action="cover"][data-image-index="1"]')
            checks.check(values() == ["Custom Plum", "#663355"], "Changing the cover also preserves an explicit manual color correction")
            checks.fill("#admin-edit-form", {
                "name": "Automatic Color Browser Dress", "founder": "Studio Fixture", "price": 89,
                "description": "A disposable dress used to verify saved image colors.", "published": True,
            })
            checks.submit("#admin-edit-form")
            checks.wait("!document.querySelector('#admin-edit-dialog').open")
            saved = next(p for p in owner.request("GET", "/api/admin/products")[1]["products"] if p["name"] == "Automatic Color Browser Dress")
            product_id = saved["id"]
            checks.check(saved["base_color"] == "Custom Plum" and saved["color_hex"] == "#663355", "A corrected automatic color persists when the product is saved")
            published = next(p for p in owner.request("GET", "/api/catalog")[1]["products"] if p["id"] == product_id)
            checks.check(published["base_color"] == "Custom Plum" and published["color_hex"] == "#663355", "The public product catalog receives the saved color and swatch")
            navigate()
            checks.click(f'[data-edit-product="{product_id}"]')
            checks.check(values() == ["Custom Plum", "#663355"], "The saved color survives a page reload and reopening the editor")
            upload("#admin-image-files", "#172b4d", "existing-extra.png")
            checks.wait("document.querySelector('#admin-image-count').textContent.startsWith('4 of')")
            upload_ready()
            checks.check(values() == ["Custom Plum", "#663355"], "Extra photos on an existing product never silently change its saved primary color")
            checks.evaluate("window.__realColorDetector=window.VeloraProductColor;window.__pendingColor=null;window.VeloraProductColor={detect:()=>new Promise(resolve=>{window.__pendingColor=resolve})}")
            checks.click("#admin-detect-color")
            checks.wait("typeof window.__pendingColor==='function'")
            checks.check(checks.evaluate("document.querySelector('#admin-image-files').disabled && document.querySelector('#admin-edit-save').disabled"), "Explicit color analysis keeps photo selection and saving disabled until it finishes")
            checks.evaluate("window.__pendingColor({name:'Burgundy',hex:'#7b233b',confidence:.95})")
            checks.wait("document.querySelector('#admin-edit-base-color').value==='Burgundy' && !document.querySelector('#admin-edit-save').disabled")
            checks.check(True, "The explicit Detect from cover photo button lets an existing product be rechecked")
            checks.check(not checks.evaluate("document.querySelector('#admin-image-files').disabled"), "Photo selection becomes available again after explicit analysis")
            checks.evaluate("window.VeloraProductColor=window.__realColorDetector")
            discard()

            checks.click("#admin-add-color")
            checks.fill("#admin-color-form", {"productId": product_id})
            upload("#admin-color-image-file", "#172b4d", "navy.png")
            checks.wait("!document.querySelector('#admin-color-image-preview').hidden && document.querySelector('#admin-color-name').value.length>0")
            upload_ready("#admin-color-image-file")
            alternate = values(True)
            checks.check(alternate[0] == "Navy" and alternate[1] != "#ffffff", "Alternate-color photo upload detects the garment color automatically")
            mobile_photo("admin-auto-color-alternate-mobile.png", "#admin-color-image-preview")
            checks.submit("#admin-color-form")
            checks.wait("!document.querySelector('#admin-color-dialog').open")
            saved = next(p for p in owner.request("GET", "/api/admin/products")[1]["products"] if p["id"] == product_id)
            checks.check(any(c["name"] == "Navy" and c["hex"] == alternate[1] for c in saved["color_variants"]), "The detected alternate color and its photo persist together")
            published = next(p for p in owner.request("GET", "/api/catalog")[1]["products"] if p["id"] == product_id)
            checks.check(any(c["name"] == "Navy" for c in published["color_variants"]), "The public product catalog exposes the detected alternate color")

            checks.evaluate("window.__realColorDetector=window.VeloraProductColor;window.VeloraProductColor={detect:()=>new Promise(resolve=>{window.__pendingColor=resolve})}")
            new_product()
            upload("#admin-image-files", "#7b233b", "pending.png")
            checks.wait("typeof window.__pendingColor==='function'")
            checks.fill("#admin-edit-form", {"base_color": "My Berry", "color_hex": "#58354a"})
            checks.evaluate("window.__pendingColor({name:'Burgundy',hex:'#7b233b',confidence:.95})")
            upload_ready()
            checks.check(values() == ["My Berry", "#58354a"], "A delayed detection result cannot overwrite a manual edit made during analysis")
            discard()

            checks.evaluate("window.__pendingColor=null;window.VeloraProductColor={detect:()=>new Promise(resolve=>{window.__pendingColor=resolve})}")
            new_product()
            upload("#admin-image-files", "#7b233b", "closed-editor.png")
            checks.wait("typeof window.__pendingColor==='function'")
            discard()
            new_product()
            checks.evaluate("window.__pendingColor({name:'Burgundy',hex:'#7b233b',confidence:.95})")
            checks.evaluate("new Promise(r=>setTimeout(r,80))")
            checks.check(values()[0] == "" and checks.evaluate("document.querySelector('#admin-image-count').textContent.startsWith('0 of') && !document.querySelector('#admin-image-files').disabled && !document.querySelector('#admin-edit-save').disabled"), "A detection from a discarded editor cannot modify or block the next product")
            discard()

            checks.evaluate("window.__pendingColor=null;window.VeloraProductColor={detect:()=>new Promise(resolve=>{window.__pendingColor=resolve})}")
            checks.click("#admin-add-color")
            checks.fill("#admin-color-form", {"productId": product_id})
            upload("#admin-color-image-file", "#172b4d", "pending-alternate.png")
            checks.wait("typeof window.__pendingColor==='function'")
            checks.check(checks.evaluate("document.querySelector('#admin-color-product').disabled"), "Alternate-color analysis locks the selected product until its result returns")
            checks.fill("#admin-color-form", {"name": "My Midnight", "hex": "#16273e"})
            checks.evaluate("window.__pendingColor({name:'Navy',hex:'#172b4d',confidence:.95})")
            upload_ready("#admin-color-image-file")
            checks.check(values(True) == ["My Midnight", "#16273e"], "A delayed alternate-color result also preserves a manual name and swatch")
            checks.check(not checks.evaluate("document.querySelector('#admin-color-product').disabled"), "The selected-product control is restored after alternate-color analysis")
            checks.click("#admin-color-cancel")

            checks.evaluate("window.VeloraProductColor=window.__realColorDetector")
            new_product()
            upload("#admin-image-files", "#7b233b", "before-unclear-cover.png")
            checks.wait("document.querySelector('#admin-edit-base-color').value==='Burgundy'")
            upload_ready()
            upload("#admin-image-files", "#ffffff", "unclear-cover.png", blank=True)
            checks.wait("document.querySelector('#admin-image-count').textContent.startsWith('2 of')")
            upload_ready()
            checks.click('#admin-image-gallery [data-image-action="cover"][data-image-index="1"]')
            checks.wait("document.querySelector('#admin-auto-color-status').textContent.includes('unclear') && !document.querySelector('#admin-image-files').disabled")
            checks.check(values()[0] == "" and checks.evaluate("document.querySelector('#admin-edit-base-color').validity.valueMissing"), "An ambiguous replacement cover clears the previous automatic color and requires a manual name")
            discard()

            checks.click("#admin-add-color")
            checks.fill("#admin-color-form", {"productId": product_id})
            upload("#admin-color-image-file", "#172b4d", "before-unclear-alternate.png")
            checks.wait("document.querySelector('#admin-color-name').value==='Navy'")
            upload_ready("#admin-color-image-file")
            upload("#admin-color-image-file", "#ffffff", "unclear-alternate.png", blank=True)
            upload_ready("#admin-color-image-file")
            checks.check(values(True)[0] == "" and checks.evaluate("document.querySelector('#admin-color-name').validity.valueMissing"), "An ambiguous alternate photo clears the previous photo's automatic color")
            checks.fill("#admin-color-form", {"name": "Confirmed Ivory", "hex": "#eee5d4"})
            upload("#admin-color-image-file", "#ffffff", "manual-unclear-alternate.png", blank=True)
            upload_ready("#admin-color-image-file")
            checks.check(values(True) == ["Confirmed Ivory", "#eee5d4"], "Ambiguous replacement images preserve an explicit manual alternate-color correction")
            checks.click("#admin-color-cancel")

            checks.click(f'[data-edit-product="{product_id}"]')
            checks.click("#admin-add-color-editor")
            checks.check(checks.evaluate("document.querySelector('#admin-color-product').disabled"), "Opening an alternate from a product editor locks its product selection")
            upload("#admin-color-image-file", "#172b4d", "locked-product.png")
            checks.wait("document.querySelector('#admin-color-name').value==='Navy'")
            upload_ready("#admin-color-image-file")
            checks.check(checks.evaluate("document.querySelector('#admin-color-product').disabled"), "Analysis preserves the product-selection lock when opened from its editor")
            checks.click("#admin-color-cancel")
            discard()

            new_product()
            upload("#admin-image-files", "#ffffff", "blank.png", blank=True)
            checks.wait("document.querySelector('#admin-image-count').textContent.startsWith('1 of')")
            upload_ready()
            checks.check(values()[0] in ("Original", ""), "An empty white image does not become a confidently detected garment color")
            checks.check(checks.evaluate("document.querySelector('#admin-auto-color-status').textContent.length>0"), "An uncertain photo explains that a color can be entered manually")
            discard()

            checks.evaluate("window.VeloraProductColor={detect:async()=>{throw new Error('Fixture analysis failed')}}")
            new_product()
            upload("#admin-image-files", "#7b233b", "analysis-failure.png")
            checks.wait("document.querySelector('#admin-image-count').textContent.startsWith('1 of')")
            upload_ready()
            checks.check(checks.evaluate("document.querySelector('#admin-edit-error').hidden && !document.querySelector('#admin-edit-save').disabled"), "A color-analysis failure does not block a valid image upload or manual saving")
            discard()
            checks.evaluate("window.VeloraProductColor=window.__realColorDetector")
            checks.check(checks.evaluate("!__colorRequests.some(p=>/product-draft|product-description|openai/i.test(p))"), "Automatic color detection never calls a paid AI generation endpoint")
            checks.check(checks.evaluate("__colorErrors.length===0"), "Automatic color uploads and correction flows produce no runtime or CSP errors")
            checks.check((root / "assets/uploads").is_dir() and any((root / "assets/uploads").iterdir()), "All uploaded test photos stay inside the disposable site")
            report = {"passed": len(checks.passed), "checks": checks.passed}
            (ROOT / "tmp/admin-auto-color-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report))
        finally:
            if connection:
                connection.socket.close()
            if browser:
                browser.terminate()
                browser.wait(timeout=10)
            app.shutdown()
            app.server_close()
            serving.join(timeout=5)


if __name__ == "__main__":
    main()
