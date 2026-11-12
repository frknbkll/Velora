"""Exercise customer reviews in Chrome against an isolated database and profile.

Run ``python py/tests/run-reviews-browser.py`` from the project root. All accounts,
review photos and pagination fixtures are disposable; live data is never opened.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file


import base64
import importlib.util
import json
from pathlib import Path
import runpy
import secrets
import struct
import tempfile
import threading
import zlib


helpers = runpy.run_path(str(ROOT / "py/tests" / "run-account-browser.py"))
Checks = helpers["Checks"]
start_chrome = helpers["start_chrome"]
WIDTHS = (320, 390, 768, 1366, 1920)


def sample_png(width=96, height=128):
    def chunk(kind, data):
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data))
    pixels = b"".join(b"\0" + b"\xa6\x4e\x37" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))


class ReviewChecks(Checks):
    def upload(self, path):
        document = self.connection.call("DOM.getDocument")
        node = self.connection.call("DOM.querySelector", {"nodeId": document["root"]["nodeId"], "selector": "#review-image"})
        self.connection.call("DOM.setFileInputFiles", {"nodeId": node["nodeId"], "files": [str(path)]})

    def rating(self, value):
        self.click(f".review-rating-options label:nth-child({value})")

    def focus_click(self, selector):
        self.evaluate(f"(() => {{ const node=document.querySelector({json.dumps(selector)}); node.focus(); node.click(); }})()")

    def escape(self):
        for kind in ("keyDown", "keyUp"):
            self.connection.call("Input.dispatchKeyEvent", {"type": kind, "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})

    def store_ready(self, signed_in=False, count=None):
        conditions = ["document.querySelector('#reviews-state')", "!document.querySelector('#reviews-state').textContent.includes('Loading')", "document.querySelector('#review-distribution').children.length === 5"]
        if signed_in:
            conditions.append("!document.querySelector('#review-form').hidden")
        if count is not None:
            conditions.append(f"document.querySelector('#review-total').textContent === {json.dumps('No reviews yet' if count == 0 else str(count) + (' review' if count == 1 else ' reviews'))}")
        self.wait(" && ".join(conditions))

    def screenshot_at(self, filename, width, height, selector=None):
        self.viewport(width, height)
        if selector:
            self.evaluate(f"document.querySelector({json.dumps(selector)}).scrollIntoView({{block:'start',behavior:'instant'}})")
        else:
            self.evaluate("window.scrollTo({top:0,behavior:'instant'})")
        self.evaluate("new Promise(resolve => setTimeout(resolve, 550))")
        screenshot = self.connection.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        (ROOT / "tmp" / filename).write_bytes(base64.b64decode(screenshot["data"]))

    def public_api(self):
        return self.evaluate("fetch('/api/reviews').then(response=>response.json())")

    def register(self, email, password, first, last):
        self.fill("#register-form", {"firstName": first, "lastName": last, "city": "Amsterdam", "country": "Netherlands", "email": email, "password": password, "confirmPassword": password, "terms": True, "ageConfirmed": True})
        self.submit("#register-form")
        self.wait("location.pathname === '/reviews.html' && document.querySelector('#review-form') && !document.querySelector('#review-form').hidden")
        self.store_ready(signed_in=True)

    def login(self, email, password):
        self.navigate("login.html?next=reviews.html", ready="window.VeloraAuth && document.querySelector('#login-form')")
        self.fill("#login-form", {"email": email, "password": password})
        self.submit("#login-form")
        self.wait("location.pathname === '/reviews.html' && document.querySelector('#review-form') && !document.querySelector('#review-form').hidden")
        self.store_ready(signed_in=True)

    def logout(self):
        self.evaluate("window.VeloraAuth.request('/api/auth/logout',{method:'POST',body:{}})")


def scenarios(checks, app, module, temporary):
    first_email = f"qa-review-{secrets.token_hex(5)}@example.test"
    second_email = f"qa-review-{secrets.token_hex(5)}@example.test"
    password = secrets.token_urlsafe(24)
    first_name = "Review First Customer"
    second_name = "Review Second Customer"
    image = temporary / "customer-photo.png"
    image.write_bytes(sample_png())
    invalid = temporary / "not-a-photo.txt"
    invalid.write_text("Not a photograph", encoding="utf-8")

    checks.navigate("reviews.html", ready="window.VeloraAuth && document.querySelector('#review-form')")
    checks.store_ready(count=0)
    checks.evaluate("document.querySelector('#privacy-banner [data-privacy-choice=\"necessary\"]')?.click()")
    checks.check(checks.evaluate("!document.querySelector('#reviews-empty').hidden && document.querySelector('#review-form').hidden && !document.querySelector('#review-signin').hidden && document.querySelector('#review-average').textContent === '—'"), "Empty public page has no fabricated ratings and invites account sign-in")
    checks.check(checks.evaluate("document.querySelector('#review-signin .review-primary').getAttribute('href') === 'login.html?next=reviews.html' && document.querySelector('#review-signin .review-signin-register a').getAttribute('href') === 'register.html?next=reviews.html'"), "Review sign-in and registration links retain the review return destination")
    checks.check_widths("Empty review page")
    checks.screenshot_at("reviews-empty-desktop.png", 1366, 950)
    checks.screenshot_at("reviews-empty-mobile.png", 390, 844)

    checks.click("#review-signin .review-primary")
    checks.wait("location.pathname === '/login.html' && document.querySelector('.auth-switch a')?.getAttribute('href') === 'register.html?next=reviews.html'")
    checks.check(True, "Sign-in page retains reviews when switching to account creation")
    checks.click(".auth-switch a")
    checks.wait("location.pathname === '/register.html' && new URLSearchParams(location.search).get('next') === 'reviews.html' && document.readyState === 'complete' && window.VeloraAuth")
    checks.check(checks.evaluate("document.querySelector('.auth-switch a').getAttribute('href') === 'login.html?next=reviews.html'"), "Account creation retains reviews when switching back to sign-in")
    checks.register(first_email, password, "Review", "First Customer")
    checks.check(checks.evaluate(f"document.querySelector('#review-account-name').textContent === {json.dumps(first_name)} && !document.querySelector('#review-anonymous').checked && document.querySelector('#review-author-preview').textContent.includes({json.dumps(first_name)})"), "New review uses the authenticated account name by default")
    checks.fill("#review-form", {"title": "A thoughtful first impression", "body": "I enjoyed exploring the collection and its useful product details."})
    checks.check(not checks.evaluate("document.querySelector('#review-form').checkValidity()"), "A star rating is required before publishing")
    for value in range(1, 6):
        checks.rating(value)
        checks.check(checks.evaluate(f"document.querySelector('input[name=rating]:checked').value === '{value}'"), f"Selecting the {value}-star label sets its native radio")
    checks.rating(4)
    checks.upload(invalid)
    checks.wait("document.querySelector('#review-form-message').textContent.includes('JPG')")
    checks.check(checks.evaluate("document.querySelector('#review-image-preview').hidden && !document.querySelector('#review-submit').disabled"), "Unsupported upload reports an error without blocking the rest of the form")
    checks.upload(image)
    checks.wait("!document.querySelector('#review-image-preview').hidden && document.querySelector('#review-image-preview').complete && !document.querySelector('#review-submit').disabled")
    checks.check(checks.evaluate("document.querySelector('#review-image-preview').src.startsWith('data:image/jpeg')"), "Selected PNG is prepared as a metadata-free photo preview")
    checks.screenshot_at("reviews-composer-named-mobile.png", 390, 844, "#review-composer")
    checks.submit("#review-form")
    checks.wait("document.querySelector('#review-form-message').classList.contains('is-success') && document.querySelector('.review-card') && !document.querySelector('#review-submit').disabled")
    checks.store_ready(signed_in=True, count=1)
    first = checks.public_api()["reviews"][0]
    checks.check(first["authorName"] == first_name and first["rating"] == 4 and not first["anonymous"] and first["image"].startswith("/api/reviews/images/"), "Publishing saves four stars, account-derived name and the optional photo")
    saved_photo = first["image"]
    first_id = first["id"]
    checks.check(checks.evaluate("document.querySelector('#review-average').textContent === '4.0' && document.querySelectorAll('.review-card-actions').length === 1"), "Rating average and own edit/delete actions reflect the saved review")
    checks.focus_click(".review-photo")
    checks.wait("document.querySelector('#review-photo-dialog').open && document.querySelector('#review-photo-image').complete && document.querySelector('#review-photo-image').naturalWidth > 0")
    checks.check(True, "Published customer photo opens in the review image dialog")
    checks.escape()
    checks.wait("!document.querySelector('#review-photo-dialog').open && document.activeElement.classList.contains('review-photo')")
    checks.check(True, "Escape closes the photo and restores the photo button focus")
    checks.focus_click(".review-card-actions button:first-child")
    checks.check(checks.evaluate("document.activeElement.id === 'review-title' && document.querySelector('#review-title').value === 'A thoughtful first impression'"), "Edit restores the published review to the composer")
    checks.click("#review-anonymous")
    checks.check(checks.evaluate("document.querySelector('#review-author-preview').textContent.includes('Anonymous')"), "Anonymous posting updates the public-name preview")
    checks.fill("#review-form", {"title": "An anonymous note", "body": "I enjoyed exploring the collection and its useful product details. This is my updated review."})
    checks.submit("#review-form")
    checks.wait("document.querySelector('#review-form-message').textContent.includes('updated') && document.querySelector('.review-author').textContent === 'Anonymous' && !document.querySelector('#review-submit').disabled")
    edited = checks.public_api()
    checks.check(edited["summary"]["count"] == 1 and edited["reviews"][0]["id"] == first_id and edited["reviews"][0]["image"] == saved_photo and edited["reviews"][0]["anonymous"], "Editing to anonymous preserves the photo and updates the existing review")
    checks.navigate("reviews.html", ready="document.querySelector('#review-form')")
    checks.store_ready(signed_in=True, count=1)
    checks.check(checks.evaluate("document.querySelector('#review-anonymous').checked && document.querySelector('#review-title').value === 'An anonymous note' && !document.querySelector('#review-image-preview').hidden"), "Anonymous preference, words and photo persist after reloading")
    checks.screenshot_at("reviews-anonymous-mobile.png", 390, 844, "#reviews-feed-title")
    checks.logout()
    checks.navigate("reviews.html", ready="document.querySelector('#review-signin')")
    checks.store_ready(count=1)
    public = checks.public_api()
    serialized = json.dumps(public)
    checks.check(first_name not in serialized and first_email not in serialized and public["reviews"][0]["authorName"] == "Anonymous" and not any(key in public["reviews"][0] for key in ("user_id", "userId", "email", "account_name")), "Public anonymous API excludes account name, email and account identifiers")
    checks.check(checks.evaluate("document.querySelectorAll('.review-card-actions').length === 0 && document.querySelector('#review-form').hidden"), "Signed-out visitors cannot edit or delete reviews")

    checks.navigate("register.html?next=reviews.html", ready="document.querySelector('#register-form')")
    checks.register(second_email, password, "Review", "Second Customer")
    checks.check(checks.evaluate("document.querySelectorAll('.review-card-actions').length === 0 && document.querySelector('#review-title').value === ''"), "A second account cannot edit the first customer's review")
    checks.rating(5)
    checks.fill("#review-form", {"title": "<img src=x onerror=alert(1)>", "body": "A welcoming website with clear navigation. I am sharing my own experience."})
    checks.submit("#review-form")
    checks.wait("document.querySelector('#review-form-message').classList.contains('is-success') && document.querySelectorAll('.review-card').length === 2 && !document.querySelector('#review-submit').disabled")
    checks.store_ready(signed_in=True, count=2)
    checks.check(checks.evaluate("document.querySelector('#review-average').textContent === '4.5' && document.querySelectorAll('.review-card-actions').length === 1 && document.querySelectorAll('.review-card-title img').length === 0 && document.querySelector('.review-card-title').textContent.includes('<img')"), "Two real reviews produce a 4.5 average while review titles remain plain text")
    checks.check(checks.evaluate(f"document.querySelector('.review-author').textContent === {json.dumps(second_name)} && document.querySelectorAll('.review-card')[1].querySelector('.review-card-actions') === null"), "Only the second customer's own review exposes edit/delete actions")
    denied = checks.evaluate(f"window.VeloraAuth.request('/api/reviews/{first_id}',{{method:'DELETE',body:{{}}}}).then(()=>0).catch(e=>e.status)")
    checks.check(denied == 404, "The server rejects deleting another account's review")
    checks.check_widths("Populated reviews and signed-in composer")
    for width in WIDTHS:
        checks.viewport(width)
        checks.check(checks.evaluate("[...document.querySelectorAll('.review-rating-options label')].every(n=>n.getBoundingClientRect().width>=44 && n.getBoundingClientRect().height>=44)"), f"Star rating targets are at least 44px at {width}px")
    checks.screenshot_at("reviews-populated-desktop.png", 1366, 1000)
    checks.screenshot_at("reviews-populated-mobile.png", 390, 844, "#reviews-feed-title")
    checks.screenshot_at("reviews-composer-mobile.png", 390, 844, "#review-composer")
    checks.focus_click("#review-delete-own")
    checks.wait("document.querySelector('#review-delete-dialog').open")
    checks.click("#review-delete-cancel")
    checks.check(checks.evaluate("!document.querySelector('#review-delete-dialog').open && document.activeElement.id === 'review-delete-own' && document.querySelector('#review-total').textContent === '2 reviews'"), "Cancelling deletion retains the review and restores the composer action")
    checks.focus_click("#review-delete-own")
    checks.click("#review-delete-confirm")
    checks.wait("!document.querySelector('#review-delete-dialog').open && document.querySelector('#review-total').textContent === '1 review' && !document.querySelector('#review-submit').disabled")
    checks.check(checks.evaluate("document.querySelector('#review-average').textContent === '4.0' && document.querySelector('#review-edit-note').hidden && document.querySelector('#review-delete-own').hidden"), "Confirming deletion removes the review and recalculates the real average")
    checks.check(checks.evaluate("document.activeElement.id === 'review-title'"), "Deleting a review restores keyboard focus to the newly empty composer")
    checks.logout()
    checks.login(first_email, password)
    checks.check(checks.evaluate("document.querySelector('#review-anonymous').checked && document.querySelector('#review-title').value === 'An anonymous note'"), "Signing in returns to reviews and restores the existing anonymous review")

    # Add disposable, clearly labelled fixture accounts to exercise pagination and
    # allow the owner's oldest review to be deleted without appearing on page one.
    with app.connect() as connection:
        password_hash = connection.execute("SELECT password_hash FROM users WHERE email=?", (first_email,)).fetchone()[0]
        for number in range(13):
            user_id = connection.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,'customer',?)", (f"Pagination Fixture {number}", f"page-{number}@example.test", password_hash, module.now_iso())).lastrowid
            connection.execute("INSERT INTO customer_reviews(id,user_id,rating,title,body,anonymous,created_at,updated_at) VALUES(?,?,3,?,?,1,?,?)", (secrets.token_hex(16), user_id, f"Disposable page fixture {number}", "This is temporary browser verification data only.", module.now_iso(), module.now_iso()))
    checks.navigate("reviews.html", ready="document.querySelector('#review-form')")
    checks.store_ready(signed_in=True, count=14)
    checks.check(checks.evaluate(f"document.querySelectorAll('.review-card').length===12 && !document.querySelector('#reviews-load-more').hidden && !document.querySelector('#review-delete-own').hidden && !document.querySelector('[data-review-id=\"{first_id}\"]')"), "An owner can manage their review even when it is beyond the first review page")
    checks.click("#reviews-load-more")
    checks.wait("document.querySelectorAll('.review-card').length === 14 && document.querySelector('#reviews-load-more').hidden")
    checks.check(checks.evaluate("new Set([...document.querySelectorAll('.review-card')].map(n=>n.dataset.reviewId)).size===14"), "Load more appends the next review page without duplicates")
    checks.navigate("reviews.html", ready="document.querySelector('#review-form')")
    checks.store_ready(signed_in=True, count=14)
    checks.focus_click("#review-delete-own")
    checks.click("#review-delete-confirm")
    checks.wait("document.querySelector('#review-total').textContent === '13 reviews' && !document.querySelector('#review-delete-dialog').open")
    status = checks.evaluate(f"fetch({json.dumps(saved_photo)},{{cache:'no-store'}}).then(r=>r.status)")
    checks.check(status == 404, "Deleting the original review makes its stored photo unavailable")
    checks.check(checks.evaluate("window.__reviewErrors.length === 0"), "Review flows produce no uncaught JavaScript errors")
    checks.no_credentials_in_storage(first_email, second_email, password)
    checks.connection.call("Network.setBlockedURLs", {"urls": ["*/api/reviews?*"]})
    try:
        checks.navigate("reviews.html", ready="document.querySelector('#reviews-state')")
        checks.wait("document.querySelector('#reviews-state').textContent.includes(\"couldn't be loaded\")")
        checks.check(checks.evaluate("document.querySelector('#review-total').textContent === 'Ratings unavailable' && document.querySelector('#reviews-empty').hidden && document.querySelector('#review-average').textContent === '—'"), "A failed review request reports unavailable ratings instead of a false empty review count")
    finally:
        checks.connection.call("Network.setBlockedURLs", {"urls": []})


def main():
    (ROOT / "tmp").mkdir(exist_ok=True)
    spec = importlib.util.spec_from_file_location("velora_review_browser_server", ROOT / "py/app/server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.VeloraHandler.log_message = lambda *args: None
    with tempfile.TemporaryDirectory(prefix="reviews-browser-", dir=ROOT / "tmp", ignore_cleanup_errors=True) as directory:
        temporary = Path(directory)
        app = module.make_server(host="127.0.0.1", port=0, database=temporary / "accounts.sqlite3", catalog=ROOT / "json/catalog/product-catalog.json", root=ROOT)
        thread = threading.Thread(target=app.serve_forever, daemon=True)
        thread.start()
        browser = connection = checks = None
        try:
            browser, connection = start_chrome(temporary / "chrome-profile")
            connection.call("Page.enable")
            connection.call("Page.addScriptToEvaluateOnNewDocument", {"source": "window.__reviewErrors=[];window.addEventListener('error',e=>window.__reviewErrors.push(e.message));window.addEventListener('unhandledrejection',()=>window.__reviewErrors.push('unhandled rejection'));"})
            checks = ReviewChecks(connection, f"http://127.0.0.1:{app.server_port}")
            scenarios(checks, app, module, temporary)
            report = f"PASS: {len(checks.passed)} customer review browser checks\n" + "\n".join(checks.passed) + "\n"
            (ROOT / "tmp/reviews-browser-results.txt").write_text(report, encoding="utf-8")
            print(report.splitlines()[0])
        except BaseException as error:
            report = f"FAIL: {type(error).__name__}: {error}\nCompleted checks: {len(checks.passed) if checks else 0}\n"
            (ROOT / "tmp/reviews-browser-results.txt").write_text(report, encoding="utf-8")
            print(report)
            if checks:
                print("UI state:", checks.evaluate("({path:location.pathname,status:document.querySelector('#reviews-state')?.textContent,message:document.querySelector('#review-form-message')?.textContent,auth:document.querySelector('#auth-message')?.textContent,errors:window.__reviewErrors})"))
                checks.screenshot_at("reviews-browser-failure.png", 390, 844)
            raise
        finally:
            if connection:
                connection.socket.close()
            if browser:
                browser.terminate()
                browser.wait(timeout=10)
            app.shutdown()
            app.server_close()
            thread.join(timeout=10)


if __name__ == "__main__":
    main()
