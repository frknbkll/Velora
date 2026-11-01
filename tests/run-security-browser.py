"""Exercise account security and the admin security center in real Chrome.

All accounts, sessions, recovery codes, keys and downloads are disposable. This
runner never opens the project's saved account database or changes product data.
"""
from __future__ import annotations

import base64
import http.client
import importlib.util
import json
from pathlib import Path
import runpy
import secrets
import sys
import tempfile
import threading
import time
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
helpers = runpy.run_path(str(ROOT / "tests/run-account-browser.py"))
Checks, start_chrome = helpers["Checks"], helpers["start_chrome"]
import security_core


class Client:
    """A second device used only with the disposable server."""
    def __init__(self, app):
        self.app, self.cookie, self.csrf = app, "", ""

    def request(self, method, path, body=None):
        headers = {"User-Agent": "Velora security regression device"}
        if self.cookie:
            headers["Cookie"] = self.cookie
        if method != "GET":
            headers.update({"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.app.server_port}"})
            if self.csrf:
                headers["X-CSRF-Token"] = self.csrf
        connection = http.client.HTTPConnection("127.0.0.1", self.app.server_port, timeout=15)
        try:
            connection.request(method, path, None if method == "GET" else json.dumps(body or {}), headers)
            response = connection.getresponse()
            result = json.loads(response.read())
            cookie = response.getheader("Set-Cookie")
            if cookie:
                self.cookie = cookie.split(";", 1)[0]
            if result.get("csrfToken"):
                self.csrf = result["csrfToken"]
            return response.status, result
        finally:
            connection.close()

    def login(self, email, password, code=None):
        status, result = self.request("POST", "/api/auth/login", {"email": email, "password": password})
        if status == 200 and result.get("requiresTwoFactor") and code:
            return self.request("POST", "/api/auth/verify", {"challenge": result["challenge"], "code": code})
        return status, result


class Clock:
    def __init__(self):
        self.real_time, self.offset = time.time, 0

    def now(self):
        return self.real_time() + self.offset

    def next_code(self, secret):
        self.offset += 31
        return security_core.totp(secret, self.now())


class SecurityChecks(Checks):
    def section_screenshot(self, name, width, height, selector):
        self.viewport(width, height)
        self.evaluate(f"document.documentElement.style.scrollBehavior='auto';document.querySelector({json.dumps(selector)}).scrollIntoView({{block:'start',behavior:'instant'}})")
        self.evaluate("new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
        screenshot = self.connection.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        (ROOT / "tmp" / name).write_bytes(base64.b64decode(screenshot["data"]))

    def account(self):
        self.navigate("account.html#security", ready="document.querySelector('#security-content') && !document.querySelector('#security-content').hidden")

    def password_login(self, email, password, mfa=False):
        self.navigate("login.html", ready="window.VeloraAuth && document.querySelector('#login-form')")
        self.fill("#login-form", {"email": email, "password": password})
        self.submit("#login-form")
        if mfa:
            self.wait("!document.querySelector('#login-mfa').hidden")
        else:
            self.wait("location.pathname === '/admin.html' && document.querySelector('#admin-shell') && !document.querySelector('#admin-shell').hidden")

    def verify(self, code, recovery=False, success=True):
        self.evaluate(f"document.querySelector('#login-use-recovery').checked = {json.dumps(recovery)}; document.querySelector('#login-use-recovery').dispatchEvent(new Event('change'))")
        self.fill("#login-mfa-form", {"code": code})
        self.submit("#login-mfa-form")
        if success:
            self.wait("location.pathname === '/admin.html' && document.querySelector('#admin-shell') && !document.querySelector('#admin-shell').hidden")
        else:
            self.wait("document.querySelector('#auth-message').classList.contains('is-error')")

    def sign_out(self):
        selector = "#admin-signout" if self.evaluate("location.pathname") == "/admin.html" else "[data-auth-logout]"
        self.click(selector)
        self.wait("location.pathname === '/login.html' && document.querySelector('#login-form')")

    def recovery_codes(self):
        return self.evaluate("Array.from(document.querySelectorAll('#mfa-recovery-codes li'), node => node.textContent)")

    def session_count(self, count):
        self.wait(f"document.querySelectorAll('#security-sessions .security-session').length === {count}")

    def manage(self, password, code, action, success=True):
        self.evaluate("document.querySelector('#mfa-manage').open = true")
        self.fill("#mfa-manage-form", {"password": password, "code": code})
        self.click("#mfa-" + action)
        if success:
            self.wait("document.querySelector('#security-message').classList.contains('is-success')")
        else:
            self.wait("document.querySelector('#security-message').classList.contains('is-error')")


def run_scenarios(checks, app, clock, email, password, customer_email, downloads):
    secondary = Client(app)
    checks.check(secondary.login(email, password)[0] == 200, "A second disposable admin device can sign in before enrollment")
    checks.password_login(email, password)
    checks.account()
    checks.check(checks.evaluate("document.querySelector('#security-mfa-badge').textContent") == "Not enabled", "Existing administrators retain usable accounts before optional enrollment")
    checks.session_count(2)
    checks.check_widths("Account security and sessions")
    checks.fill("#mfa-setup-form", {"password": "An incorrect password for this test"})
    checks.submit("#mfa-setup-form")
    checks.wait("document.querySelector('#security-message').classList.contains('is-error')")
    checks.check(checks.evaluate("document.querySelector('#mfa-enrollment').hidden"), "Authenticator setup rejects an incorrect current password")
    checks.fill("#mfa-setup-form", {"password": password})
    checks.submit("#mfa-setup-form")
    checks.wait("!document.querySelector('#mfa-enrollment').hidden && document.querySelector('#mfa-secret').textContent.length >= 16")
    secret = checks.evaluate("document.querySelector('#mfa-secret').textContent")
    checks.check(checks.evaluate("Boolean(document.querySelector('#mfa-qr svg'))"), "Authenticator setup renders a local QR code")
    checks.check_widths("Authenticator enrollment")
    checks.section_screenshot("security-account-setup-desktop.png", 1366, 900, "#security")
    checks.section_screenshot("security-account-setup-mobile.png", 390, 844, "#mfa-enrollment")
    checks.fill("#mfa-enable-form", {"code": security_core.totp(secret, clock.now())})
    checks.submit("#mfa-enable-form")
    checks.wait("!document.querySelector('#mfa-recovery-panel').hidden && document.querySelectorAll('#mfa-recovery-codes li').length === 10")
    recovery = checks.recovery_codes()
    checks.check(len(set(recovery)) == 10, "Enabling two-factor sign-in shows ten distinct recovery codes once")
    checks.check(secondary.request("GET", "/api/auth/me")[1]["user"] is None, "Enabling two-factor sign-in revokes other existing sessions")
    checks.connection.call("Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": str(downloads)})
    checks.click("#mfa-recovery-download")
    deadline = time.monotonic() + 10
    while not list(downloads.glob("*.txt")) and time.monotonic() < deadline:
        time.sleep(.08)
    saved = list(downloads.glob("*.txt"))
    checks.check(bool(saved) and all(code in saved[0].read_text(encoding="utf-8") for code in recovery), "Recovery codes download only after the explicit save action")
    checks.no_credentials_in_storage(email, password, secret, *recovery)
    checks.click("#mfa-recovery-saved")
    checks.check(checks.evaluate("document.querySelector('#mfa-recovery-panel').hidden && !document.querySelector('#mfa-secret').textContent && !document.querySelector('#mfa-recovery-codes').textContent"), "Acknowledging saved codes clears setup secrets and recovery codes from the page")
    checks.check_widths("Enabled two-factor account")
    checks.sign_out()
    checks.password_login(email, password, mfa=True)
    checks.check(checks.evaluate("fetch('/api/auth/me').then(response => response.json()).then(data => data.user === null)"), "A correct password alone does not establish a two-factor session")
    checks.check(checks.evaluate("fetch('/api/admin/security').then(response => response.status)") == 401, "Pending two-factor verification cannot access administrator APIs")
    checks.check(checks.evaluate("document.querySelector('#login-password').value") == "", "The password is cleared before the verification step")
    checks.check_widths("Two-factor login verification")
    checks.screenshot("security-login-mfa-mobile.png", 390, 844)
    valid_window = {security_core.totp(secret, clock.now() + step) for step in (-30, 0, 30)}
    wrong = next(value for value in ("000000", "111111", "222222", "333333") if value not in valid_window)
    checks.verify(wrong, success=False)
    checks.check(checks.evaluate("location.pathname") == "/login.html", "An invalid authenticator code stays on the verification page")
    accepted_code = clock.next_code(secret)
    checks.verify(accepted_code)
    checks.check(True, "A fresh authenticator code completes administrator sign-in")
    checks.sign_out()
    checks.password_login(email, password, mfa=True)
    checks.verify(accepted_code, success=False)
    checks.check(checks.evaluate("fetch('/api/auth/me').then(response => response.json()).then(data => data.user === null)"), "An already accepted authenticator code cannot be replayed")
    checks.verify(recovery[0], recovery=True)
    checks.check(True, "A saved recovery code can complete the verification form")
    checks.sign_out()
    checks.password_login(email, password, mfa=True)
    checks.verify(recovery[0], recovery=True, success=False)
    checks.check(checks.evaluate("fetch('/api/auth/me').then(response => response.json()).then(data => data.user === null)"), "A recovery code is rejected after it has already been used")
    checks.verify(recovery[1], recovery=True)
    checks.no_credentials_in_storage(email, password, secret, *recovery)

    checks.navigate("admin.html#security", ready="document.querySelector('#admin-security-failed') && document.querySelector('#admin-security-failed').textContent !== '—'")
    checks.check(int(checks.evaluate("document.querySelector('#admin-security-failed').textContent")) >= 2, "Security overview counts actual failed verification events")
    checks.check(checks.evaluate("document.querySelector('#admin-security-mfa').textContent") == "1 / 1", "Admin security overview shows actual two-factor enrollment")
    checks.check(checks.evaluate("document.querySelectorAll('#admin-security-events-body tr').length") > 0, "Administrator security events come from the real API")
    checks.evaluate("document.querySelector('#admin-security-severity').value='warning'; document.querySelector('#admin-security-severity').dispatchEvent(new Event('change'))")
    checks.check(checks.evaluate("document.querySelectorAll('#admin-security-events-body tr').length") > 0, "Security event severity filtering shows actual warning events")
    checks.fill_search("#admin-security-search", "no-events-match-this")
    checks.check(checks.evaluate("!document.querySelector('#admin-security-empty').hidden"), "An unmatched security search has a useful empty state")
    checks.fill_search("#admin-security-search", "")
    checks.evaluate("document.querySelector('#admin-security-severity').value='all'; document.querySelector('#admin-security-severity').dispatchEvent(new Event('change'))")
    checks.check_widths("Real admin Security center")
    checks.screenshot("security-admin-real-desktop.png", 1366, 900)
    checks.screenshot("security-admin-real-mobile.png", 390, 844)
    customer = Client(app)
    checks.check(customer.login(customer_email, password)[0] == 200, "A disposable customer can sign in normally")
    checks.check(customer.request("GET", "/api/admin/security")[0] == 403, "Customers cannot view administrator security events")

    extra = Client(app)
    checks.check(extra.login(email, password, recovery[2])[0] == 200, "A new second device can pass two-factor authentication")
    other_id = next(row["id"] for row in extra.request("GET", "/api/security/sessions")[1]["sessions"] if row["current"])
    checks.account()
    checks.session_count(2)
    checks.click(f'[data-revoke-session="{other_id}"]')
    checks.session_count(1)
    checks.check(extra.request("GET", "/api/auth/me")[1]["user"] is None, "Signing out one device revokes that device's actual server session")
    additional = [Client(app), Client(app)]
    for client, code in zip(additional, recovery[3:5]):
        checks.check(client.login(email, password, code)[0] == 200, "Another disposable device can establish a verified session")
    checks.click("#security-refresh")
    checks.session_count(3)
    checks.click("#security-revoke-others")
    checks.session_count(1)
    checks.check(all(client.request("GET", "/api/auth/me")[1]["user"] is None for client in additional), "Sign out other devices revokes all other sessions while keeping this device")
    checks.check_widths("Session management")
    checks.manage("An incorrect password for this test", recovery[5], "regenerate", success=False)
    checks.check(checks.evaluate("document.querySelector('#mfa-recovery-panel').hidden"), "Replacing recovery codes requires the correct current password")
    checks.manage(password, recovery[5], "regenerate")
    checks.wait("!document.querySelector('#mfa-recovery-panel').hidden && document.querySelectorAll('#mfa-recovery-codes li').length === 10")
    replacement = checks.recovery_codes()
    checks.check(not set(replacement).intersection(recovery), "Replacing recovery codes creates an entirely new set")
    verifier = Client(app)
    verification = verifier.login(email, password)[1]
    checks.check(verifier.request("POST", "/api/auth/verify", {"challenge": verification["challenge"], "code": recovery[6]})[0] == 401, "Replacing recovery codes invalidates an unused code from the old set")
    checks.check(verifier.request("POST", "/api/auth/verify", {"challenge": verification["challenge"], "code": replacement[0]})[0] == 200, "A code from the replacement set works")
    checks.no_credentials_in_storage(email, password, secret, *replacement)
    checks.click("#mfa-recovery-saved")
    checks.manage("An incorrect password for this test", replacement[1], "disable", success=False)
    checks.check(checks.evaluate("document.querySelector('#security-mfa-badge').textContent") == "Enabled", "Disabling two-factor sign-in requires the current password")
    checks.manage(password, replacement[1], "disable")
    checks.wait("document.querySelector('#security-mfa-badge').textContent === 'Not enabled'")
    checks.check(verifier.request("GET", "/api/auth/me")[1]["user"] is None, "Disabling two-factor sign-in revokes other active devices")
    status = checks.evaluate("window.VeloraAuth.request('/api/security/status')")
    checks.check(not status["mfaEnabled"] and status["recoveryCodesRemaining"] == 0, "Disabling two-factor sign-in removes recovery codes on the server")
    checks.sign_out()
    checks.password_login(email, password)
    checks.check(True, "Password sign-in works normally again after an authorized two-factor disable")
    checks.account()
    current_session = checks.evaluate("window.VeloraAuth.request('/api/security/sessions').then(data => data.sessions.find(session => session.current).id)")
    checks.click(f'[data-revoke-session="{current_session}"]')
    checks.wait("location.pathname === '/login.html' && document.querySelector('#login-form')")
    checks.check(checks.evaluate("fetch('/api/auth/me').then(response => response.json()).then(data => data.user === null)"), "Signing out this device revokes its current server session")
    history = checks.connection.call("Page.getNavigationHistory")
    previous = next((entry for entry in reversed(history["entries"][:history["currentIndex"]]) if "/account.html" in entry["url"]), None)
    if previous:
        checks.connection.call("Page.navigateToHistoryEntry", {"entryId": previous["id"]})
        checks.wait("location.pathname === '/login.html' && document.querySelector('#login-form')")
        checks.check(checks.evaluate("!document.querySelector('#account-content') || document.querySelector('#account-content').hidden"), "Browser Back cannot reveal the private account after signing out")


def main():
    (ROOT / "tmp").mkdir(exist_ok=True)
    spec = importlib.util.spec_from_file_location("security_browser_server", ROOT / "server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.VeloraHandler.log_message = lambda *args: None
    clock = Clock()
    with tempfile.TemporaryDirectory(prefix="security-browser-", dir=ROOT / "tmp", ignore_cleanup_errors=True) as directory, mock.patch("time.time", clock.now):
        temporary = Path(directory)
        app = module.make_server(host="127.0.0.1", port=0, database=temporary / "accounts.sqlite3", catalog=ROOT / "product-catalog.json", root=ROOT)
        email, customer_email = f"security-admin-{secrets.token_hex(5)}@example.test", f"security-member-{secrets.token_hex(5)}@example.test"
        password = secrets.token_urlsafe(24)
        with app.connect() as connection:
            for name, address, role in (("Security Test Administrator", email, "admin"), ("Security Test Member", customer_email, "customer")):
                connection.execute("INSERT INTO users (name,email,password_hash,role,created_at) VALUES (?,?,?,?,?)", (name,address,module.hash_password(password),role,module.now_iso()))
        thread = threading.Thread(target=app.serve_forever, daemon=True)
        thread.start()
        browser = connection = checks = None
        try:
            browser, connection = start_chrome(temporary / "chrome-profile")
            checks = SecurityChecks(connection, f"http://127.0.0.1:{app.server_port}")
            downloads = temporary / "downloads"
            downloads.mkdir()
            run_scenarios(checks, app, clock, email, password, customer_email, downloads)
            report = f"PASS: {len(checks.passed)} security browser checks\n" + "\n".join(checks.passed) + "\n"
            (ROOT / "tmp/security-browser-results.txt").write_text(report,encoding="utf-8")
            print(report.splitlines()[0])
        except BaseException as error:
            report = f"FAIL: {type(error).__name__}: {error}\nCompleted checks: {len(checks.passed) if checks else 0}\n"
            (ROOT / "tmp/security-browser-results.txt").write_text(report,encoding="utf-8")
            if checks:
                try:
                    viewport = checks.evaluate("({width:innerWidth,height:innerHeight})")
                    checks.screenshot("security-browser-failure.png",viewport["width"],viewport["height"])
                except Exception:
                    pass
            raise
        finally:
            if connection:
                connection.socket.close()
            if browser:
                browser.terminate()
                browser.wait(timeout=10)
            app.shutdown()
            app.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    main()
