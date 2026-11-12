"""Check optimized image downloads and deliberate original-photo zoom."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

import json
from pathlib import Path
import runpy
import sys
import tempfile
import threading
from urllib.parse import urlsplit

import server

helpers = runpy.run_path(str(ROOT / "py/tests/run-account-browser.py"))
Checks, start_chrome = helpers["Checks"], helpers["start_chrome"]


def main():
    (ROOT / "tmp").mkdir(exist_ok=True)
    catalog = json.loads((ROOT / "json/catalog/product-catalog.json").read_text(encoding="utf-8"))["products"]
    source = (ROOT / "js/product-responsive-images.js").read_text(encoding="utf-8")
    manifest, _ = json.JSONDecoder().raw_decode(source.split("window.VeloraResponsiveImages =", 1)[1].lstrip())
    original = max((p for p in manifest if p.startswith(("assets/gallery/", "assets/uploads/"))), key=lambda p: (ROOT / p).stat().st_size)
    selected = {**catalog[0], "id": "image-delivery-large-fixture", "name": "Large image delivery fixture", "image": original, "images": [original], "base_color": "Original", "color_variants": [], "published": True}
    selected.pop("color_key", None)
    browser = connection = None
    with tempfile.TemporaryDirectory(prefix="image-delivery-", dir=ROOT / "tmp", ignore_cleanup_errors=True) as folder:
        directory = Path(folder)
        fixture_catalog = directory / "catalog.json"
        fixture_catalog.write_text(json.dumps({"products": [*catalog, selected]}), encoding="utf-8")
        app = server.make_server(port=0, database=directory / "test.sqlite3", catalog=fixture_catalog, root=ROOT)
        app.RequestHandlerClass.log_message = lambda *args: None
        serving = threading.Thread(target=app.serve_forever, daemon=True)
        serving.start()
        try:
            browser, connection = start_chrome(directory / "chrome")
            connection.call("Page.enable")
            connection.call("Network.setCacheDisabled", {"cacheDisabled": True})
            connection.call("Page.addScriptToEvaluateOnNewDocument", {"source": "performance.setResourceTimingBufferSize(2000);window.__deliveryErrors=[];addEventListener('error',e=>{if(e.message)__deliveryErrors.push(e.message)});addEventListener('unhandledrejection',e=>__deliveryErrors.push(String(e.reason)));addEventListener('securitypolicyviolation',e=>__deliveryErrors.push('CSP '+e.violatedDirective))"})
            checks = Checks(connection, f"http://127.0.0.1:{app.server_port}")
            measurements = []

            def viewport(width, height, ratio=1):
                connection.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": ratio, "mobile": width <= 650})
                checks.evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")

            def downloads():
                return checks.evaluate("performance.getEntriesByType('resource').filter(r=>/\\.(?:jpe?g|png|webp)(?:[?#]|$)/i.test(r.name)).map(r=>({url:r.name,bytes:r.encodedBodySize,initiator:r.initiatorType}))")

            def no_original_downloads(label):
                records = downloads()
                originals = [r for r in records if "/assets/responsive/" not in r["url"] and "/assets/brand/" not in r["url"] and r["bytes"] > 0]
                checks.check(not originals, label + ": no original photo downloaded before explicit zoom: " + str(originals))
                return records

            for width, height, ratio in ((1920, 1080, 2), (390, 844, 2)):
                viewport(width, height, ratio)
                checks.navigate("index.html", ready="document.documentElement.dataset.catalogState==='managed' && document.querySelector('.hero-image').complete && document.querySelector('.hero-image').naturalWidth>0")
                checks.evaluate("document.querySelector('#privacy-banner [data-privacy-choice=necessary]')?.click()")
                checks.evaluate("new Promise(resolve=>setTimeout(resolve,350))")
                hero = checks.evaluate("(()=>{const i=document.querySelector('.hero-image');return {source:i.currentSrc,width:i.getBoundingClientRect().width,candidate:Number(new URL(i.currentSrc).pathname.match(/-(\\d+)\\.webp$/)?.[1]),ratio:devicePixelRatio}})()")
                checks.check("/assets/responsive/" in hero["source"] and hero["source"].endswith(".webp"), f"{width}px hero downloads an optimized WebP")
                checks.check(hero["candidate"] >= min(3840, hero["width"] * ratio) - 1, f"{width}px hero has enough pixels for its display density")
                records = no_original_downloads(f"{width}px homepage")
                measurements.append({"page": "homepage", "viewport": width, "density": ratio, "heroCandidate": hero["candidate"], "imageBytes": sum(r["bytes"] for r in records)})

            viewport(1440, 1000)
            checks.navigate("product.html?id=" + selected["id"], ready="!document.querySelector('#product-page-content').hidden && document.querySelector('#product-page-image').complete && document.querySelector('#product-page-image').naturalWidth>0")
            image = checks.evaluate("(()=>{const i=document.querySelector('#product-page-image');return {source:i.currentSrc,original:i.dataset.originalSrc}})()")
            checks.check(image["original"] == original and image["source"].endswith(".webp") and "/assets/responsive/" in image["source"], "Product detail retains its original identity and downloads WebP")
            records = no_original_downloads("Product detail")
            measurements.append({"page": "product detail", "originalBytes": (ROOT / original).stat().st_size, "imageBytes": sum(r["bytes"] for r in records)})
            checks.check(checks.evaluate("[...document.querySelectorAll('#product-thumbnails img')].every(i=>i.dataset.originalSrc && i.srcset.includes('assets/responsive/'))"), "Product thumbnails use optimized sources with original identifiers")

            checks.navigate("index.html", ready="document.documentElement.dataset.catalogState==='managed'")
            checks.click("#collection-refinements > summary")
            checks.fill_search("#collection-search", selected["name"])
            checks.wait("document.querySelectorAll('.look-tile').length===1")
            checks.click(".look-tile .product-size-help")
            checks.wait("document.querySelector('#product-dialog').open && document.querySelector('.product-dialog-image').complete && document.querySelector('.product-dialog-image').naturalWidth>0")
            checks.check(checks.evaluate("document.querySelector('.product-dialog-image').currentSrc.endsWith('.webp')"), "Quick-view photograph stays optimized")
            no_original_downloads("Quick view")
            checks.click(".product-zoom-open")
            checks.wait("document.querySelector('#velora-photo-inspector')?.open && document.querySelector('.vpi-original').complete && document.querySelector('.vpi-original').naturalWidth>0")
            zoom = checks.evaluate("document.querySelector('.vpi-original').currentSrc")
            checks.check(urlsplit(zoom).path == "/" + original, "Explicit zoom downloads the untouched original")
            checks.check(any(urlsplit(r["url"]).path == "/" + original and r["bytes"] > 0 for r in downloads()), "Original photo appears in download measurements only after zoom")
            checks.check(checks.evaluate("window.__deliveryErrors.length===0"), "Image delivery has no runtime or CSP errors")
            result = {"passed": len(checks.passed), "checks": checks.passed, "measurements": measurements}
            (ROOT / "tmp/image-delivery-results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps(result))
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
