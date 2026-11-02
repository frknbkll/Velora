"""Exercise real account/admin forms in Chrome against a disposable database.

Run from the project root with ``python tests/run-account-browser.py``.
The existing database is never opened. Screenshots and a short report go to tmp/.
"""

from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path
import runpy
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
browser_tools = runpy.run_path(str(ROOT / "tests" / "run-product-colors.py"))
BrowserConnection = browser_tools["BrowserConnection"]
CHROME = browser_tools["CHROME"]
WIDTHS = (320, 390, 768, 1366, 1920)


class Checks:
    def __init__(self, connection, origin):
        self.connection = connection
        self.origin = origin
        self.passed = []

    def evaluate(self, expression):
        result = self.connection.call("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
            "timeout": 10000,
        })
        if "exceptionDetails" in result:
            # Report a useful exception without printing request bodies or form values.
            detail = result["exceptionDetails"]
            raise RuntimeError(detail.get("text", "Browser expression failed"))
        return result.get("result", {}).get("value")

    def wait(self, expression, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if self.evaluate(f"Boolean({expression})"):
                    return
            except RuntimeError:
                # Navigation can replace the execution context between CDP calls.
                pass
            time.sleep(.08)
        path = self.evaluate("location.pathname")
        raise AssertionError(f"Browser condition did not become true on {path}: {expression}")

    def check(self, condition, description):
        if not condition:
            raise AssertionError(description)
        self.passed.append(description)

    def navigate(self, page, expected=None, ready=None):
        self.connection.call("Page.navigate", {"url": f"{self.origin}/{page}"})
        path = "/" + (expected or page).split("?", 1)[0].split("#", 1)[0]
        self.wait(f"location.pathname === {json.dumps(path)} && document.readyState === 'complete'")
        if ready:
            self.wait(ready)

    def fill(self, form, fields):
        values = json.dumps(fields)
        self.evaluate(f"""(() => {{
            const form = document.querySelector({json.dumps(form)});
            for (const [name, value] of Object.entries({values})) {{
                const input = form.elements.namedItem(name);
                if (!input) throw new Error('Form field missing: ' + name);
                if (input.type === 'checkbox') input.checked = value;
                else input.value = value;
                input.dispatchEvent(new Event('input', {{bubbles: true}}));
                input.dispatchEvent(new Event('change', {{bubbles: true}}));
            }}
        }})()""")

    def submit(self, selector):
        self.evaluate(f"document.querySelector({json.dumps(selector)}).requestSubmit()")

    def fill_search(self, selector, value):
        self.evaluate(f"""(() => {{
            const field = document.querySelector({json.dumps(selector)});
            field.value = {json.dumps(value)};
            field.dispatchEvent(new Event('input', {{bubbles: true}}));
        }})()""")

    def click(self, selector):
        self.evaluate(f"document.querySelector({json.dumps(selector)}).click()")

    def viewport(self, width, height=900):
        self.connection.call("Emulation.setDeviceMetricsOverride", {
            "width": width, "height": height, "deviceScaleFactor": 1, "mobile": False,
        })
        # Await layout and two paint opportunities, including responsive style recalculation.
        self.evaluate("new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")

    def check_widths(self, page_name):
        for width in WIDTHS:
            self.viewport(width)
            size = self.evaluate("({viewport: innerWidth, document: document.documentElement.scrollWidth})")
            if size["document"] > size["viewport"] + 1:
                offenders = self.evaluate("""Array.from(document.body.querySelectorAll('*')).filter(node => {
                    const rect = node.getBoundingClientRect(), style = getComputedStyle(node);
                    return rect.width > 0 && (rect.left < -1 || rect.right > innerWidth + 1) && style.display !== 'none';
                }).map(node => ({tag: node.tagName, id: node.id, class: node.className, right: Math.round(node.getBoundingClientRect().right)})).slice(0, 18)""")
                raise AssertionError(f"{page_name}: horizontal overflow at {width}px: {size}; elements={offenders}")
            self.check(True, f"{page_name}: no horizontal overflow at {width}px")

    def screenshot(self, file_name, width, height):
        self.viewport(width, height)
        self.evaluate("""Promise.race([
            Promise.all(Array.from(document.images).filter(image => image.getClientRects().length)
                .map(image => image.decode().catch(() => {}))),
            new Promise(resolve => setTimeout(resolve, 1200))
        ])""")
        self.evaluate("window.scrollTo(0, 0)")
        self.evaluate("new Promise(resolve => setTimeout(resolve, 550))")
        screenshot = self.connection.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        (ROOT / "tmp" / file_name).write_bytes(base64.b64decode(screenshot["data"]))

    def no_credentials_in_storage(self, *credentials):
        stored = self.evaluate("JSON.stringify({local: {...localStorage}, session: {...sessionStorage}})")
        self.check(all(value not in stored for value in credentials), "Passwords and account emails are absent from browser storage")
        self.check("velora_session" not in self.evaluate("document.cookie"), "Session cookie is unavailable to JavaScript")

    def show_all_store_products(self):
        self.wait("window.veloraCatalogReady && document.documentElement.dataset.catalogState === 'managed'")
        self.check(self.evaluate("window.veloraCatalogReady"), "Storefront has loaded the managed catalog before product checks")
        self.wait("document.querySelectorAll('.look-tile').length > 0")
        self.evaluate("""(() => {
            const button = document.querySelector('#show-more-looks');
            for (let count = 0; count < 10 && button && !button.hidden; count++) button.click();
        })()""")

    def check_store_header(self):
        for width in (320, 390, 768, 1024, 1101, 1250, 1251, 1366, 1920):
            self.viewport(width)
            layout = self.evaluate("""(() => {
                const visible = [...document.querySelectorAll('.site-header > .wordmark, .site-header > .menu-toggle, .site-header > .primary-nav, .site-header > .header-shop-actions')]
                    .filter(node => {
                        const style = getComputedStyle(node), box = node.getBoundingClientRect();
                        return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) !== 0 && box.width > 0 && box.height > 0;
                    });
                const overlaps = [];
                for (let i = 0; i < visible.length; i++) {
                    for (let j = i + 1; j < visible.length; j++) {
                        const a = visible[i].getBoundingClientRect(), b = visible[j].getBoundingClientRect();
                        if (a.left < b.right - 1 && a.right > b.left + 1 && a.top < b.bottom - 1 && a.bottom > b.top + 1)
                            overlaps.push([visible[i].className, visible[j].className]);
                    }
                }
                const bounds = Object.fromEntries(visible.map(node => {
                    const box = node.getBoundingClientRect();
                    return [node.className || node.tagName.toLowerCase(), {left: Math.round(box.left), right: Math.round(box.right), width: Math.round(box.width)}];
                }));
                const navigationFontSize = parseFloat(getComputedStyle(document.querySelector('.primary-nav a')).fontSize);
                return {width: innerWidth, document: document.documentElement.scrollWidth, overlaps, bounds, navigationFontSize};
            })()""")
            self.check(layout["document"] <= layout["width"] + 1, f"Storefront: no horizontal overflow at {width}px")
            self.check(not layout["overlaps"], f"Storefront: header account/actions, wordmark, menu and navigation do not overlap at {width}px ({layout['overlaps']}, {layout['bounds']})")
            self.check(10 <= layout["navigationFontSize"] <= 11, f"Storefront: navigation text remains readable at {width}px ({layout['navigationFontSize']}px)")
        for width in (768, 1024):
            self.viewport(width)
            self.click(".menu-toggle")
            self.check(self.evaluate("document.querySelector('.menu-toggle').getAttribute('aria-expanded') === 'true' && document.querySelector('.primary-nav').classList.contains('is-open')"), f"Tablet menu opens at {width}px")
            self.check(self.evaluate("parseFloat(getComputedStyle(document.querySelector('.primary-nav a')).fontSize) >= 11"), f"Tablet navigation uses readable text at {width}px")
            self.click(".menu-toggle")
            self.check(self.evaluate("document.querySelector('.menu-toggle').getAttribute('aria-expanded') === 'false'"), f"Tablet menu closes when toggled at {width}px")
            self.click(".menu-toggle")
            self.connection.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27, "nativeVirtualKeyCode": 27})
            self.connection.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27, "nativeVirtualKeyCode": 27})
            self.check(self.evaluate("document.querySelector('.menu-toggle').getAttribute('aria-expanded') === 'false' && document.activeElement === document.querySelector('.menu-toggle')"), f"Escape closes the tablet menu and restores focus at {width}px")

    def check_sticky_header(self):
        self.viewport(1366)
        self.evaluate("window.scrollTo(0, 0)")
        self.wait("!document.querySelector('.site-header').classList.contains('is-scrolled')")
        self.check(self.evaluate("getComputedStyle(document.querySelector('.site-header')).position === 'fixed'"), "Storefront header is fixed so it remains visible while scrolling")
        self.evaluate("window.scrollTo(0, 500)")
        self.wait("document.querySelector('.site-header').classList.contains('is-scrolled')")
        state = self.evaluate("""(() => {
            const header = document.querySelector('.site-header');
            const nav = document.querySelector('.primary-nav');
            const actions = document.querySelector('.header-shop-actions');
            return {
                top: Math.round(header.getBoundingClientRect().top),
                visible: header.getBoundingClientRect().bottom > 0,
                overHero: header.classList.contains('is-over-hero'),
                textColor: getComputedStyle(document.querySelector('.wordmark')).color,
                headerBackground: getComputedStyle(header).backgroundColor,
                navBackground: getComputedStyle(nav).backgroundColor,
                actionsBackground: getComputedStyle(actions).backgroundColor,
            };
        })()""")
        self.check(state == {
            "top": 0, "visible": True, "overHero": True, "textColor": "rgb(255, 253, 248)",
            "headerBackground": "rgba(0, 0, 0, 0)", "navBackground": "rgba(0, 0, 0, 0)",
            "actionsBackground": "rgba(0, 0, 0, 0)",
        }, "Header stays visible with white text over the hero and transparent backgrounds")
        self.evaluate("window.scrollTo(0, document.querySelector('.hero').offsetHeight + 200)")
        self.wait("!document.querySelector('.site-header').classList.contains('is-over-hero')")
        after_hero = self.evaluate("""(() => {
            const header = document.querySelector('.site-header');
            const textColor = getComputedStyle(document.querySelector('.wordmark')).color;
            return {
                top: Math.round(header.getBoundingClientRect().top),
                visible: header.getBoundingClientRect().bottom > 0,
                darkText: textColor.match(/[0-9]+/g).slice(0, 3).every(value => Number(value) < 150),
                background: getComputedStyle(header).backgroundColor,
            };
        })()""")
        self.check(after_hero == {"top": 0, "visible": True, "darkText": True, "background": "rgba(0, 0, 0, 0)"}, "Header remains visible with dark text after the hero image")
        self.viewport(390)
        self.evaluate("window.scrollTo(0, 500)")
        self.wait("document.querySelector('.site-header').classList.contains('is-over-hero')")
        self.check(self.evaluate("document.querySelector('.site-header').getBoundingClientRect().top === 0 && getComputedStyle(document.querySelector('.wordmark')).color === 'rgb(255, 253, 248)'"), "Mobile header stays above the image with white text while scrolling")
        self.evaluate("window.scrollTo(0, 0)")
        self.wait("!document.querySelector('.site-header').classList.contains('is-scrolled')")


def start_chrome(profile):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    process = subprocess.Popen([
        str(CHROME), "--headless", "--disable-gpu", "--no-first-run",
        "--no-default-browser-check", f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=1) as response:
                    page = next(page for page in json.load(response) if page["type"] == "page")
                connection = BrowserConnection(page["webSocketDebuggerUrl"])
                connection.call("Network.enable")
                connection.call("Network.setBlockedURLs", {"urls": ["*fonts.googleapis.com*", "*fonts.gstatic.com*"]})
                return process, connection
            except (OSError, StopIteration):
                time.sleep(.1)
        raise RuntimeError("Chrome did not start")
    except BaseException:
        process.terminate()
        process.wait(timeout=10)
        raise


def run_scenarios(checks, admin_email, admin_password, customer_email, customer_password, new_password, product):
    checks.navigate("admin.html", expected="login.html", ready="document.querySelector('#login-form') && window.VeloraAuth")
    checks.check(checks.evaluate("new URLSearchParams(location.search).get('next')") == "admin.html", "Anonymous admin visit redirects to sign-in with the correct destination")
    checks.check_widths("Login")
    checks.screenshot("account-login-desktop.png", 1366, 900)
    checks.screenshot("account-login-mobile.png", 390, 844)
    checks.click('[data-toggle-password="login-password"]')
    checks.check(checks.evaluate("document.querySelector('#login-password').type") == "text", "Password reveal control shows the password")
    checks.click('[data-toggle-password="login-password"]')
    checks.check(checks.evaluate("document.querySelector('#login-password').type") == "password", "Password reveal control hides the password again")

    checks.navigate("register.html", ready="window.VeloraAuth && document.querySelector('#register-form')")
    checks.check_widths("Registration")
    checks.fill("#register-form", {
        "firstName": "Browser", "lastName": "Test Member", "city": "London", "country": "United Kingdom",
        "email": customer_email, "password": customer_password,
        "confirmPassword": "A different password 123", "terms": True, "ageConfirmed": True,
    })
    checks.submit("#register-form")
    checks.check(checks.evaluate("document.querySelector('#register-confirm-password').validity.customError"), "Registration catches a mismatched password confirmation")
    checks.check(checks.evaluate("location.pathname") == "/register.html", "Invalid registration stays on the form")
    checks.fill("#register-form", {"confirmPassword": customer_password})
    checks.submit("#register-form")
    checks.wait("location.pathname === '/account.html' && document.querySelector('#account-content') && !document.querySelector('#account-content').hidden")
    checks.check(checks.evaluate("document.querySelector('#account-name').textContent") == "Browser Test Member", "Registration creates an account and opens the personalized account page")
    checks.check(checks.evaluate("document.querySelector('#profile-city').value") == "London", "Registration saves and displays the customer profile details")
    checks.check(checks.evaluate("window.VeloraAuth.user.role") == "customer", "Public registration creates a customer role")
    checks.check(checks.evaluate("document.querySelector('[data-admin-link]').hidden"), "Customer account hides the admin link")
    checks.check_widths("Account")

    updated_name = "Browser Updated Member"
    checks.fill("#profile-form", {"firstName": "Browser", "lastName": "Updated Member", "city": "Paris", "country": "France"})
    checks.submit("#profile-form")
    checks.wait("document.querySelector('#auth-message').classList.contains('is-success')")
    checks.check(checks.evaluate("document.querySelector('#account-name').textContent") == updated_name, "Profile changes save to the server and update the displayed name")
    checks.fill("#profile-form", {"currentPassword": "An incorrect password 123", "newPassword": new_password})
    checks.submit("#profile-form")
    checks.wait("document.querySelector('#auth-message').classList.contains('is-error')")
    checks.check("current password" in checks.evaluate("document.querySelector('#auth-message').textContent").lower(), "Password changes require the correct current password")
    checks.fill("#profile-form", {"currentPassword": customer_password, "newPassword": new_password})
    checks.submit("#profile-form")
    checks.wait("document.querySelector('#auth-message').classList.contains('is-success') && !document.querySelector('#profile-new-password').value")
    checks.check(True, "Customer changes password through the profile form")
    checks.no_credentials_in_storage(admin_email, admin_password, customer_email, customer_password, new_password)

    denied_page = checks.evaluate("fetch('/admin.html', {cache:'no-store'}).then(async response => ({status:response.status,body:await response.text()}))")
    checks.check(denied_page["status"] == 403 and 'id="admin-shell"' not in denied_page["body"], "Server refuses to send the admin page to a customer")
    forbidden = checks.evaluate("fetch('/api/admin/products').then(response => response.status)")
    checks.check(forbidden == 403, "The server rejects customer access to admin data")
    checks.click("[data-auth-logout]")
    checks.wait("location.pathname === '/login.html' && document.querySelector('#login-form')")
    checks.check(checks.evaluate("window.VeloraAuth.ready.then(user => user === null)"), "Signing out invalidates the server session")
    checks.fill("#login-form", {"email": customer_email, "password": customer_password})
    checks.submit("#login-form")
    checks.wait("document.querySelector('#auth-message').classList.contains('is-error')")
    checks.check("incorrect" in checks.evaluate("document.querySelector('#auth-message').textContent").lower(), "Old password is rejected after a password change")
    checks.fill("#login-form", {"password": new_password, "remember": True})
    checks.submit("#login-form")
    checks.wait("location.pathname === '/account.html' && document.querySelector('#account-content') && !document.querySelector('#account-content').hidden")
    checks.check(checks.evaluate("document.querySelector('#account-name').textContent") == updated_name, "Customer can sign in with the new password and retained profile")
    checks.navigate("index.html", ready="window.VeloraAuth && window.VeloraAuth.ready.then(user => user && user.firstName === 'Browser')")
    checks.check(checks.evaluate("document.querySelector('[data-auth-label]').textContent") == updated_name, "The signed-in customer's full name appears in the storefront header")
    checks.viewport(390)
    checks.check(checks.evaluate("getComputedStyle(document.querySelector('[data-auth-compact-label]')).display !== 'none' && document.querySelector('[data-auth-compact-label]').textContent === 'Browser'"), "The signed-in customer's name remains visible in the compact header")
    checks.check_store_header()
    checks.check_sticky_header()
    checks.navigate("account.html", ready="document.querySelector('#account-content') && !document.querySelector('#account-content').hidden")
    checks.click("[data-auth-logout]")
    checks.wait("location.pathname === '/login.html' && document.querySelector('#login-form')")

    checks.fill("#login-form", {"email": admin_email, "password": admin_password})
    checks.submit("#login-form")
    checks.wait("location.pathname === '/admin.html' && document.querySelector('#admin-shell') && !document.querySelector('#admin-shell').hidden && document.querySelector('#admin-total-products').textContent !== '—'")
    checks.check(checks.evaluate("window.VeloraAuth.user.role") == "admin", "Administrator sign-in opens the admin portal by default")
    checks.check(checks.evaluate("Number(document.querySelector('#admin-total-products').textContent)") > 0, "Admin overview displays real catalog totals")
    checks.check(checks.evaluate("Number(document.querySelector('#admin-total-customers').textContent)") == 1, "Admin overview counts the real registered customer")
    checks.check_widths("Admin overview")
    checks.screenshot("account-admin-desktop.png", 1366, 900)
    checks.screenshot("account-admin-mobile.png", 390, 844)
    checks.click('[data-admin-section="customers"]')
    checks.wait("!document.querySelector('#admin-customers').hidden")
    checks.fill_search("#admin-customer-search", updated_name)
    checks.check(checks.evaluate("document.querySelectorAll('#admin-customers-body tr').length") == 1, "Customer search finds the registered profile")
    checks.check(customer_email in checks.evaluate("document.querySelector('#admin-customers-body').textContent"), "Customers table uses the real account email")
    checks.check_widths("Admin customers")

    checks.click('[data-admin-section="products"]')
    checks.wait("!document.querySelector('#admin-products').hidden")
    checks.fill_search("#admin-product-search", product["name"])
    checks.check(checks.evaluate("document.querySelectorAll('#admin-products-body tr').length") == 1, "Product search filters to the selected piece")
    checks.check_widths("Admin products")
    checks.viewport(1366)
    checks.click(f'[data-edit-product="{product["id"]}"]')
    checks.wait("document.querySelector('#admin-edit-dialog').open")
    price = int(product["price"]) + .99
    description = "A considered piece updated through the browser verification workflow."
    checks.fill("#admin-edit-form", {"price": price, "description": description, "published": False})
    checks.submit("#admin-edit-form")
    checks.wait("!document.querySelector('#admin-edit-dialog').open")
    checks.check("Draft" in checks.evaluate("document.querySelector('#admin-products-body').textContent"), "Saving product visibility updates the admin row")
    published_ids = checks.evaluate("fetch('/api/catalog').then(response => response.json()).then(data => data.products.map(product => product.id))")
    checks.check(product["id"] not in published_ids, "Draft products are excluded from the public catalog API")
    checks.navigate("index.html", ready="document.querySelector('#looks-grid') && document.querySelectorAll('.look-tile').length > 0")
    checks.show_all_store_products()
    checks.check_store_header()
    names = checks.evaluate("Array.from(document.querySelectorAll('.look-tile-caption strong'), node => node.textContent)")
    checks.check(product["name"] not in names, "Unpublishing a product removes it from the actual storefront")

    checks.navigate("admin.html#products", ready="document.querySelector('#admin-shell') && !document.querySelector('#admin-shell').hidden && document.querySelectorAll('#admin-products-body tr').length > 0")
    checks.fill_search("#admin-product-search", product["name"])
    checks.click(f'[data-edit-product="{product["id"]}"]')
    checks.wait("document.querySelector('#admin-edit-dialog').open")
    checks.check(checks.evaluate("Number(document.querySelector('#admin-edit-price').value)") == price, "Decimal product price persists after reloading the portal")
    checks.check(checks.evaluate("document.querySelector('#admin-edit-description').value") == description, "Product description persists after reloading the portal")
    checks.fill("#admin-edit-form", {"published": True})
    checks.submit("#admin-edit-form")
    checks.wait("!document.querySelector('#admin-edit-dialog').open")
    checks.navigate("index.html", ready="document.querySelector('#looks-grid') && document.querySelectorAll('.look-tile').length > 0")
    checks.show_all_store_products()
    rendered = checks.evaluate(f"""Array.from(document.querySelectorAll('.look-tile')).find(card =>
        card.querySelector('.look-tile-caption strong')?.textContent === {json.dumps(product['name'])})?.textContent || ''""")
    checks.check(description in rendered, "Republishing restores the product with the edited description")
    checks.check(f"{price:.2f}" in rendered, "Storefront preserves and displays cents in edited prices")
    checks.no_credentials_in_storage(admin_email, admin_password, customer_email, customer_password, new_password)


def main():
    (ROOT / "tmp").mkdir(exist_ok=True)
    spec = importlib.util.spec_from_file_location("velora_test_server", ROOT / "server.py")
    server_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server_module)
    server_module.VeloraHandler.log_message = lambda *args: None
    with tempfile.TemporaryDirectory(prefix="account-browser-", dir=ROOT / "tmp", ignore_cleanup_errors=True) as temporary:
        temporary = Path(temporary)
        app = server_module.make_server(host="127.0.0.1", port=0, database=temporary / "accounts.sqlite3", catalog=ROOT / "product-catalog.json", root=ROOT)
        admin_email = f"qa-admin-{secrets.token_hex(5)}@example.test"
        customer_email = f"qa-member-{secrets.token_hex(5)}@example.test"
        admin_password = secrets.token_urlsafe(24)
        customer_password = secrets.token_urlsafe(24)
        new_password = secrets.token_urlsafe(24)
        with app.connect() as connection:
            connection.execute("INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?, ?, ?, 'admin', ?)", ("Studio Test Administrator", admin_email, server_module.hash_password(admin_password), server_module.now_iso()))
        serving = threading.Thread(target=app.serve_forever, daemon=True)
        serving.start()
        browser = connection = None
        checks = None
        try:
            browser, connection = start_chrome(temporary / "chrome-profile")
            checks = Checks(connection, f"http://127.0.0.1:{app.server_port}")
            products = json.loads((ROOT / "product-catalog.json").read_text(encoding="utf-8"))["products"]
            run_scenarios(checks, admin_email, admin_password, customer_email, customer_password, new_password, products[0])
            report = f"PASS: {len(checks.passed)} account/admin browser checks\n" + "\n".join(checks.passed) + "\n"
            (ROOT / "tmp" / "account-browser-results.txt").write_text(report, encoding="utf-8")
            print(report.splitlines()[0])
        except BaseException as error:
            report = f"FAIL: {type(error).__name__}: {error}\nCompleted checks: {len(checks.passed) if checks else 0}\n"
            (ROOT / "tmp" / "account-browser-results.txt").write_text(report, encoding="utf-8")
            if checks:
                try:
                    dimensions = checks.evaluate("({width: innerWidth, height: innerHeight})")
                    checks.screenshot("account-browser-failure.png", dimensions["width"], dimensions["height"])
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
            serving.join(timeout=10)


if __name__ == "__main__":
    main()
