"""Verify real privacy choices, storage withdrawal and public disclosures in Chrome.

Uses a disposable database; never opens the owner's database or sends email.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

from pathlib import Path
import base64
import json
import runpy
import sys
import tempfile
import threading

import server

helpers = runpy.run_path(str(ROOT / "py/tests/run-account-browser.py"))
Checks, start_chrome = helpers["Checks"], helpers["start_chrome"]
server.VeloraHandler.log_message = lambda *args: None

with tempfile.TemporaryDirectory(prefix="privacy-browser-", dir=ROOT / "tmp", ignore_cleanup_errors=True) as temporary:
    temporary = Path(temporary)
    app = server.make_server(port=0, database=temporary / "accounts.sqlite3", catalog=ROOT / "json/catalog/product-catalog.json", root=ROOT)
    with app.connect() as db:
        db.execute("UPDATE business_settings SET details=? WHERE id=1", (json.dumps({
            "legalName": "QA Example Studio", "country": "Netherlands", "registrationNumber": "QA000000",
            "businessAddress": "Example address\nTest city", "customerServiceEmail": "qa@example.test",
            "returnAddress": "QA return address", "vatNumber": "",
        }),))
    thread = threading.Thread(target=app.serve_forever, daemon=True)
    thread.start()
    browser = connection = None
    try:
        browser, connection = start_chrome(temporary / "chrome")
        checks = Checks(connection, f"http://127.0.0.1:{app.server_port}")
        def store():
            checks.navigate("index.html", ready="window.VeloraPrivacy && window.veloraCatalogReady && document.documentElement.dataset.catalogState==='managed'")
        def settings():
            checks.evaluate("document.querySelector('.legal-links [data-privacy-settings]').focus(); document.querySelector('.legal-links [data-privacy-settings]').click()")
            checks.wait("document.querySelector('#privacy-settings').open")
        def key(name, code):
            for kind in ("rawKeyDown", "keyUp"):
                connection.call("Input.dispatchKeyEvent", {"type":kind,"key":name,"code":name,"windowsVirtualKeyCode":code})
        def shot(name):
            data = connection.call("Page.captureScreenshot", {"format":"png"})
            (ROOT / "tmp" / name).write_bytes(base64.b64decode(data["data"]))

        store()
        checks.check(checks.evaluate("!document.querySelector('#privacy-banner').hidden && !VeloraPrivacy.canSaveLooks() && localStorage.getItem('velora-shopping-v1')===null"), "Optional storage is off before a choice")
        for width in (320,390,768,1366,1920):
            checks.viewport(width,844)
            checks.check(checks.evaluate("document.documentElement.scrollWidth<=innerWidth+1 && Array.from(document.querySelectorAll('#privacy-banner [data-privacy-choice]')).every(b=>{const r=b.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.height>=44})"), f"Banner choices fit and remain usable at {width}px")
        checks.viewport(390,844)
        shot("privacy-banner-mobile.png")
        checks.check(checks.evaluate("(()=>{const b=[...document.querySelectorAll('#privacy-banner [data-privacy-choice]')].map(x=>getComputedStyle(x));return ['backgroundColor','color','fontWeight','borderColor'].every(k=>b[0][k]===b[1][k])})()"), "Accepting and refusing have equal visual emphasis")
        checks.click('#privacy-banner [data-privacy-choice="necessary"]')
        checks.click('.look-tile .save-look')
        checks.click('.look-tile .add-to-bag')
        checks.check(checks.evaluate("localStorage.getItem('velora-shopping-v1')===null && JSON.parse(localStorage.getItem('veloraPrivacyChoice')).savedLooks===false"), "Bag and wishlist work without optional persistence")
        settings()
        checks.check(not checks.evaluate("document.querySelector('#privacy-saved-looks').checked"), "Optional checkbox starts unchecked")
        for _ in range(10):
            key("Tab",9)
            # Native modal dialogs may let Tab visit browser chrome; page controls remain inert.
            checks.check(checks.evaluate("document.activeElement===document.body || document.querySelector('#privacy-settings').contains(document.activeElement)"), "Preferences dialog keeps keyboard focus off background controls")
        key("Escape",27)
        checks.check(checks.evaluate("!document.querySelector('#privacy-settings').open && document.activeElement.matches('.legal-links [data-privacy-settings]')"), "Escape closes preferences and restores focus")
        settings()
        checks.click('#privacy-saved-looks')
        checks.click('#privacy-settings button[type="submit"]')
        checks.check(checks.evaluate("VeloraPrivacy.canSaveLooks() && Boolean(localStorage.getItem('velora-shopping-v1'))"), "Explicit permission enables persistence")
        store()
        checks.check(checks.evaluate("Number(document.querySelector('#wishlist-count').textContent)>0 && Number(document.querySelector('#cart-count').textContent)>0"), "Opted-in bag and wishlist survive navigation")
        settings()
        checks.click('#privacy-settings [data-privacy-choice="necessary"]')
        checks.check(checks.evaluate("!VeloraPrivacy.canSaveLooks() && localStorage.getItem('velora-shopping-v1')===null"), "Withdrawing permission removes saved shopping data immediately")
        store()
        checks.check(checks.evaluate("document.querySelector('#wishlist-count').textContent==='0' && Number(document.querySelector('#cart-count').textContent)>0 && sessionStorage.getItem('velora-session-bag-v1')!==null"), "Withdrawing optional saving removes wishlist persistence while retaining the active session bag")
        checks.evaluate("localStorage.setItem('veloraPrivacyChoice',JSON.stringify({version:1,savedLooks:true,updatedAt:Date.now()-180*86400000-2000,expiresAt:Date.now()-2000}));localStorage.setItem('velora-shopping-v1','{}')")
        store()
        checks.check(checks.evaluate("!VeloraPrivacy.canSaveLooks() && !document.querySelector('#privacy-banner').hidden && localStorage.getItem('velora-shopping-v1')===null"), "Expired choice cannot authorize persistence")
        checks.click('#privacy-banner [data-privacy-choice="necessary"]')
        checks.check(checks.evaluate("document.querySelectorAll('.product-rating,.product-rating-stars,[aria-label^=\"Customer rating\"]').length===0"), "No fabricated product ratings are displayed")
        checks.check(checks.evaluate("document.querySelectorAll('.newsletter input[type=email]').length===0"), "Inactive newsletter does not collect email addresses")
        checks.click('.look-tile .add-to-bag')
        checks.click('[data-shop-view="cart"]')
        checks.check(checks.evaluate("document.querySelector('#shop-dialog-footer').textContent.includes('No order is placed') && document.querySelector('#shop-dialog-footer').textContent.includes('payment are not configured')"), "Bag explains preview pricing and absence of charges")
        checks.evaluate("document.querySelector('#shop-dialog').close()")
        checks.evaluate("localStorage.setItem('unrelated-test-key','keep'); VeloraPrivacy.clearDeviceData()")
        checks.check(checks.evaluate("localStorage.getItem('unrelated-test-key')==='keep' && localStorage.getItem('veloraPrivacyChoice')===null && sessionStorage.getItem('velora-session-bag-v1')===null && document.querySelector('#cart-count').textContent==='0'"), "Clear device data removes only Velora state and updates the UI")
        checks.click('#privacy-banner [data-privacy-choice="necessary"]')

        for page in ("privacy.html","terms.html","refund-policy.html","cookie-policy.html","business-details.html","unsubscribe.html","register.html","login.html","team.html","founders.html"):
            checks.navigate(page, ready="window.VeloraPrivacy")
            checks.check(checks.evaluate("document.querySelectorAll('.legal-links a').length===6 && document.querySelector('.legal-links [data-privacy-settings]') && document.querySelector('main[id][tabindex=\"-1\"]') && Array.from(document.images).every(i=>i.hasAttribute('alt'))"), page+": policies, skip target and image alternatives present")
            for width in (320,390,768,1366,1920):
                checks.viewport(width,900)
                checks.check(checks.evaluate("document.documentElement.scrollWidth<=innerWidth+1"), page+f": fits {width}px")
            checks.evaluate("document.fonts.ready")
            checks.check(checks.evaluate("document.fonts.check('16px \"DM Sans\"') && document.fonts.check('16px \"Playfair Display\"') && performance.getEntriesByType('resource').every(e=>new URL(e.name).origin===location.origin)"), page+": fonts load locally without third-party resource requests")
            if page=="business-details.html":
                checks.wait("document.querySelector('[data-business-field=legalName]').textContent==='QA Example Studio'")
                checks.check(checks.evaluate("document.querySelector('[data-business-field=customerServiceEmail]').textContent==='qa@example.test' && document.querySelector('[data-business-field=vatNumber]').textContent==='Not yet provided'"), "Published business fields hydrate from saved settings and missing fields stay honest")
            if page=="register.html":
                checks.check(checks.evaluate("!document.querySelector('#register-terms').checked && !document.querySelector('[name=ageConfirmed]').checked && !document.querySelector('[type=date]')"), "Registration requires explicit age and terms choices without collecting a birth date")
        checks.navigate("cookie-policy.html", ready="window.VeloraPrivacy")
        checks.viewport(1440,900)
        settings()
        shot("privacy-preferences-desktop.png")
        report=f"PASS: {len(checks.passed)} privacy browser checks\n"+'\n'.join(checks.passed)+'\n'
        (ROOT / "tmp/privacy-browser-results.txt").write_text(report,encoding="utf-8")
        print(report.splitlines()[0])
    finally:
        if connection: connection.socket.close()
        if browser:
            browser.terminate()
            browser.wait(timeout=10)
        app.shutdown()
        app.server_close()
        thread.join(timeout=10)
