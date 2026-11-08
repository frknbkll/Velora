"""Check collection discovery and filtering at desktop and true mobile sizes."""
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

helpers = runpy.run_path(str(ROOT / "tests/run-account-browser.py"))
Checks, start_chrome = helpers["Checks"], helpers["start_chrome"]


def main():
    (ROOT / "tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="collection-layout-", dir=ROOT / "tmp", ignore_cleanup_errors=True) as folder:
        directory = Path(folder)
        app = server.make_server(port=0, database=directory / "test.sqlite3", root=ROOT)
        app.RequestHandlerClass.log_message = lambda *args: None
        serving = threading.Thread(target=app.serve_forever, daemon=True)
        serving.start()
        browser = connection = None
        try:
            browser, connection = start_chrome(directory / "chrome")
            connection.call("Page.enable")
            connection.call("Page.addScriptToEvaluateOnNewDocument", {"source": "window.__layoutErrors=[];addEventListener('error',e=>__layoutErrors.push(e.message));addEventListener('unhandledrejection',e=>__layoutErrors.push(String(e.reason)));addEventListener('securitypolicyviolation',e=>__layoutErrors.push('CSP '+e.violatedDirective))"})
            checks = Checks(connection, f"http://127.0.0.1:{app.server_port}")
            def viewport(width, height):
                connection.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": width <= 650})
                checks.evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
            checks.viewport = viewport
            measurements = []
            for width, height in ((1440, 1000), (390, 844), (320, 844)):
                viewport(width, height)
                checks.navigate("index.html", ready="window.veloraCatalogReady && document.documentElement.dataset.catalogState==='managed'")
                checks.evaluate("document.querySelector('#privacy-banner [data-privacy-choice=necessary]')?.click()")
                checks.evaluate("document.fonts.ready")
                checks.check(checks.evaluate("!document.querySelector('#collection-refinements').open"), f"{width}px: advanced filters start collapsed")
                checks.check(checks.evaluate(f"innerWidth==={width} && document.documentElement.scrollWidth<=document.documentElement.clientWidth" + (f" && document.documentElement.clientWidth==={width}" if width <= 650 else "")), f"{width}px: page fits without shrink-to-fit")
                geometry = checks.evaluate("(()=>{const section=document.querySelector('#collection').getBoundingClientRect(),card=document.querySelector('.look-tile').getBoundingClientRect();return {firstProductOffset:Math.round(card.top-section.top),categories:[...document.querySelectorAll('[data-filter-group=category] button')].map(b=>b.textContent)}})()")
                measurements.append({"width": width, **geometry})
                checks.check(geometry["firstProductOffset"] < height, f"{width}px: products begin within one screen of collection")
                checks.check("Layering" in geometry["categories"] and "THE LAYERING EDIT" not in geometry["categories"], f"{width}px: category names are readable")
                checks.check(checks.evaluate("document.querySelector('#collection-filter-status').getClientRects().length>0"), f"{width}px: result count remains visible with filters closed")
                if width in (1440, 390):
                    checks.evaluate("(async()=>{const images=[...document.querySelectorAll('.look-tile-image img')].slice(0,4);await Promise.all(images.map(image=>{image.loading='eager';return image.decode().catch(()=>{})}));document.querySelector('#collection').scrollIntoView({block:'start',behavior:'instant'});await new Promise(resolve=>setTimeout(resolve,900))})()")
                    capture = connection.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
                    (ROOT / "tmp" / f"collection-layout-{'desktop' if width == 1440 else 'mobile'}.png").write_bytes(base64.b64decode(capture["data"]))
                checks.click("#collection-refinements > summary")
                checks.fill_search("#collection-search", "no-match-qa-collection-unique")
                checks.wait("document.querySelector('.collection-empty')")
                checks.click("#clear-collection-filters")
                checks.wait("document.querySelectorAll('.look-tile').length>0 && !document.querySelector('.collection-empty')")
                checks.check(True, f"{width}px: search, empty state and clear filters work")
                checks.click("#collection-refinements > summary")
                checks.check(checks.evaluate("document.querySelectorAll('#collection-filter-status').length===1 && window.__layoutErrors.length===0"), f"{width}px: no duplicate status or runtime errors")
            result = {"passed": len(checks.passed), "checks": checks.passed, "measurements": measurements}
            (ROOT / "tmp/collection-layout-results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
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
