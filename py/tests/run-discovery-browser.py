"""Read-only checks of live editorial discovery and its existing collection filters."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

import base64
import json
from pathlib import Path
import runpy
import tempfile

helpers = runpy.run_path(str(ROOT / "py/tests/run-account-browser.py"))
Checks, start_chrome = helpers["Checks"], helpers["start_chrome"]
with tempfile.TemporaryDirectory(prefix="discovery-check-", dir=ROOT / "tmp", ignore_cleanup_errors=True) as folder:
    browser = connection = None
    try:
        browser, connection = start_chrome(Path(folder) / "chrome")
        connection.call("Page.enable")
        connection.call("Network.setCacheDisabled", {"cacheDisabled": True})
        connection.call("Page.addScriptToEvaluateOnNewDocument", {"source": "window.__discoveryErrors=[];addEventListener('error',e=>__discoveryErrors.push(e.message));addEventListener('unhandledrejection',e=>__discoveryErrors.push(String(e.reason)));addEventListener('securitypolicyviolation',e=>__discoveryErrors.push('CSP '+e.violatedDirective));"})
        checks = Checks(connection, "http://127.0.0.1:8000")
        for width in (320, 390, 768, 1440):
            checks.viewport(width, 950)
            checks.navigate("index.html", ready="document.documentElement.dataset.catalogState==='managed'")
            checks.evaluate("document.querySelector('#privacy-banner [data-privacy-choice=necessary]')?.click();document.documentElement.style.scrollBehavior='auto';document.querySelector('.discovery').scrollIntoView({block:'start',behavior:'instant'})")
            checks.wait("[...document.querySelectorAll('.discovery-edit:not([hidden]) img')].every(i=>i.complete&&i.naturalWidth>0)")
            checks.check(checks.evaluate("document.documentElement.scrollWidth<=innerWidth"), f"{width}px: discovery does not overflow the page")
            checks.check(checks.evaluate("document.querySelectorAll('.discovery-edit:not([hidden])').length===3 && [...document.querySelectorAll('.discovery-edit')].every(a=>a.querySelector('.discovery-count').textContent.includes('look'))"), f"{width}px: three live edits show current look counts and working photos")
            if width in (390, 1440):
                picture = connection.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
                (ROOT / "tmp" / f"discovery-after-{width}.png").write_bytes(base64.b64decode(picture["data"]))
            categories = checks.evaluate("[...document.querySelectorAll('.discovery-edit')].map(a=>a.dataset.discoverEdit)")
            for index, category in enumerate(categories):
                checks.evaluate("document.querySelector('#collection-search').value='a previous search';document.querySelector('#collection-search').dispatchEvent(new Event('input',{bubbles:true}))")
                selector = f".discovery-edit:nth-child({index + 1})"
                checks.evaluate(f"document.querySelector({json.dumps(selector)}).scrollIntoView({{block:'center',inline:'center',behavior:'instant'}})")
                point = checks.evaluate(f"(()=>{{const r=document.querySelector({json.dumps(selector)}).getBoundingClientRect();return {{x:Math.min(innerWidth-5,Math.max(5,r.left+r.width/2)),y:r.top+r.height/2}}}})()")
                connection.call("Input.dispatchMouseEvent", {"type": "mousePressed", "button": "left", "clickCount": 1, **point})
                connection.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "button": "left", "clickCount": 1, **point})
                checks.wait(f"activeCategory==={json.dumps(category)} && document.querySelector('#collection-search').value==='' && document.querySelectorAll('#looks-grid .look-tile').length>0")
                checks.check(checks.evaluate(f"[...document.querySelectorAll('#looks-grid .look-tile')].every(c=>lookByKey.get('product:'+c.dataset.productId).collection==={json.dumps(category)}) && document.activeElement.id==='collection-title'"), f"{width}px: {category} opens only matching published products and moves keyboard focus")
            checks.check(checks.evaluate("window.__discoveryErrors.length===0"), f"{width}px: no JavaScript or CSP errors")
        connection.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
        checks.check(checks.evaluate("parseFloat(getComputedStyle(document.querySelector('.discovery-image img')).transitionDuration)<.001"), "Reduced-motion preference disables discovery image animation")
        result = {"passed": len(checks.passed), "checks": checks.passed}
        (ROOT / "tmp/discovery-browser-results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result))
    finally:
        if connection:
            connection.socket.close()
        if browser:
            browser.terminate()
            browser.wait(timeout=10)
