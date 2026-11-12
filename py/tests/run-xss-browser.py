"""Exercise stored-text XSS and credentialed-request boundaries in isolated Chrome.

Uses temporary accounts, business settings and a disposable database only.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

from pathlib import Path
import json
import runpy
import secrets
import sys
import tempfile
import threading
from urllib.parse import urlsplit

import server

helpers = runpy.run_path(str(ROOT / "py/tests/run-account-browser.py"))
Checks, start_chrome = helpers["Checks"], helpers["start_chrome"]


class AuditHandler(server.VeloraHandler):
    """Test-only redirect endpoints; the application has neither endpoint."""
    followed_redirects = 0

    def log_message(self, *args):
        pass

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/audit-redirect":
            self.send_response(307)
            self.send_header("Location", "/api/audit-redirect-target")
            self.send_header("Content-Length", "0")
            self.common_headers()
            self.end_headers()
        elif path == "/api/audit-redirect-target":
            type(self).followed_redirects += 1
            self.send_json(200, {})
        else:
            super().do_GET()


def main():
    (ROOT / "tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="xss-browser-", dir=ROOT / "tmp", ignore_cleanup_errors=True) as temporary:
        temporary = Path(temporary)
        app = server.make_server(port=0, database=temporary / "accounts.sqlite3", catalog=ROOT / "json/catalog/product-catalog.json", root=ROOT)
        app.RequestHandlerClass = AuditHandler
        password = secrets.token_urlsafe(24)
        account_payload = '<img src=x onerror="window.__auditXss=1">'
        product_payload = '<svg onload="window.__auditXss=1">'
        description_payload = '<script>window.__auditXss=1</script><a href="javascript:window.__auditXss=1">A look</a>'
        business_payload = '\"><img src=x onerror="window.__auditXss=1">'
        with app.connect() as database:
            database.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,'admin',?)", (
                "Audit administrator", "audit-owner@example.test", server.hash_password(password), server.now_iso(),
            ))
        thread = threading.Thread(target=app.serve_forever, daemon=True)
        thread.start()
        browser = connection = None
        try:
            browser, connection = start_chrome(temporary / "chrome")
            checks = Checks(connection, f"http://127.0.0.1:{app.server_port}")

            def no_injection(selector, label):
                checks.check(checks.evaluate(f"typeof window.__auditXss==='undefined' && !document.querySelector({json.dumps(selector)}).querySelector('[onerror],[onload],script')"), label)

            checks.navigate("register.html", ready="window.VeloraAuth && document.querySelector('#register-form')")
            checks.fill("#register-form", {
                "firstName": account_payload, "lastName": "Member", "city": "Amsterdam", "country": "Netherlands",
                "email": "audit-member@example.test", "password": password,
                "confirmPassword": password, "terms": True, "ageConfirmed": True,
            })
            checks.submit("#register-form")
            checks.wait("location.pathname==='/account.html' && !document.querySelector('#account-content').hidden")
            checks.check(checks.evaluate("document.querySelector('#account-name').textContent") == f"{account_payload} Member", "Account profile names remain literal text")
            no_injection("#account-content", "Stored account text does not create executable DOM")

            checks.navigate("index.html", ready="window.veloraCatalogReady && document.documentElement.dataset.catalogState==='managed' && window.VeloraAuth.user")
            boundary = checks.evaluate("""(async () => {
                const originalFetch = window.fetch;
                const calls = [];
                window.fetch = async (path, options) => {
                    calls.push({path, method: options.method, redirect: options.redirect,
                        credentials: options.credentials, csrf: options.headers.get('X-CSRF-Token'),
                        contentType: options.headers.get('Content-Type')});
                    return new Response('{}', {status: 200, headers: {'Content-Type':'application/json'}});
                };
                const invalidPaths = ['https://example.invalid/api/auth/me', '//example.invalid/api/auth/me',
                    '/api/../privacy.html', '/api/%2e%2e/privacy.html', '/api/./../../privacy.html',
                    '/api/\\\\privacy.html', '/api/auth/me#fragment', '/api/auth/me\\n', '/api/\\u0000',
                    null, {}, 'api/auth/me'];
                let rejectedPaths=0, rejectedMethods=0;
                try {
                    for (const path of invalidPaths) {
                        try { await VeloraAuth.request(path); } catch { rejectedPaths++; }
                    }
                    for (const method of ['TRACE','CONNECT','HEAD','OPTIONS',{},false]) {
                        try { await VeloraAuth.request('/api/auth/me', {method}); } catch { rejectedMethods++; }
                    }
                    const noInvalidNetwork=calls.length===0;
                    await VeloraAuth.request('/api/account', {method:'PATCH',body:{name:'An ordinary display name'},headers:{'x-csrf-token':'ignored-test-value'}});
                    const accepted=calls[0];
                    return {rejectedPaths,rejectedMethods,noInvalidNetwork,validCall: calls.length===1 &&
                        accepted.path==='/api/account' && accepted.method==='PATCH' && accepted.redirect==='error' &&
                        accepted.credentials==='same-origin' && accepted.csrf===VeloraAuth.csrfToken && accepted.contentType==='application/json'};
                } finally { window.fetch = originalFetch; }
            })()""")
            checks.check(boundary["rejectedPaths"] == 12, "Absolute URLs, normalized traversal, fragments and malformed API paths are rejected")
            checks.check(boundary["rejectedMethods"] == 6, "Unsupported request methods are rejected")
            checks.check(boundary["noInvalidNetwork"], "Invalid credentialed requests are rejected before network access")
            checks.check(boundary["validCall"], "Valid mutations use same-origin credentials, current CSRF and redirect rejection")
            rejected_redirect = checks.evaluate("VeloraAuth.request('/api/audit-redirect').then(()=>false,()=>true)")
            checks.check(rejected_redirect and AuditHandler.followed_redirects == 0, "Credentialed API requests do not follow HTTP redirects")

            checks.navigate("account.html", ready="window.VeloraAuth.user && !document.querySelector('#account-content').hidden")
            checks.click("[data-auth-logout]")
            checks.wait("location.pathname==='/login.html'")
            checks.fill("#login-form", {"email":"audit-owner@example.test", "password":password})
            checks.submit("#login-form")
            checks.wait("location.pathname==='/admin.html' && !document.querySelector('#admin-shell').hidden && document.querySelectorAll('#admin-products-body tr').length>0")
            checks.click('[data-admin-section="customers"]')
            checks.wait("document.querySelector('#admin-customers-body').textContent.includes('audit-member@example.test')")
            checks.check(account_payload in checks.evaluate("document.querySelector('#admin-customers-body').textContent"), "Customer list preserves literal user-supplied display names")
            no_injection("#admin-customers-body", "Customer list does not interpret names as markup")

            image = json.loads((ROOT / "json/catalog/product-catalog.json").read_text(encoding="utf-8"))["products"][0]["image"]
            product = {"name":product_payload,"description":description_payload,"founder":account_payload,"collection":"THE EVERYDAY EDIT","price":19.95,"images":[image],"published":True,"stock":None,"sizes":["M"],"base_color":product_payload,"color_hex":"#c0b8ac"}
            result = checks.evaluate(f"VeloraAuth.request('/api/admin/products', {{method:'POST',body:{json.dumps(product)}}})")
            product_id = result["product"]["id"]
            checks.navigate("admin.html?audit=products#products", ready=f"window.VeloraAuth.user && document.querySelector('[data-edit-product=\"{product_id}\"]')")
            checks.check(product_payload in checks.evaluate("document.querySelector('#admin-products-body').textContent"), "Admin product table preserves literal product text")
            no_injection("#admin-products-body", "Admin product table does not create payload elements")
            checks.click(f'[data-edit-product="{product_id}"]')
            checks.wait("document.querySelector('#admin-edit-dialog').open")
            checks.check(checks.evaluate("document.querySelector('#admin-edit-description').value") == description_payload, "Product editor preserves description text without HTML interpretation")
            no_injection("#admin-edit-dialog", "Product editor displays untrusted content through text/value properties")

            details = {"legalName":business_payload,"country":product_payload,"registrationNumber":account_payload,"businessAddress":description_payload,"customerServiceEmail":"audit-support@example.test","returnAddress":business_payload}
            checks.evaluate(f"VeloraAuth.request('/api/admin/business-details', {{method:'PATCH',body:{json.dumps(details)}}})")
            checks.navigate("business-details.html", ready="window.VeloraPrivacy")
            checks.wait(f"document.querySelector('[data-business-field=legalName]').textContent==={json.dumps(business_payload)}")
            checks.check(checks.evaluate("Array.from(document.querySelectorAll('[data-business-field]')).every(node=>node.childElementCount===0)"), "Public business details render exclusively as text")
            no_injection("main", "Public business fields cannot create active HTML")

            checks.navigate("index.html", ready="window.veloraCatalogReady && document.documentElement.dataset.catalogState==='managed'")
            checks.show_all_store_products()
            selector = f'.look-tile[data-product-id="{product_id}"]'
            checks.check(product_payload in checks.evaluate(f"document.querySelector({json.dumps(selector)}).textContent"), "Storefront keeps product titles literal")
            checks.check(description_payload in checks.evaluate(f"document.querySelector({json.dumps(selector)}).textContent"), "Storefront keeps product descriptions literal")
            no_injection(selector, "Stored product markup does not execute or create attacker elements")
            checks.click(selector + " .look-quick-view")
            checks.wait("document.querySelector('#product-dialog').open")
            checks.check(description_payload in checks.evaluate("document.querySelector('#product-dialog').textContent"), "Quick view keeps stored descriptions literal")
            no_injection("#product-dialog", "Quick view does not interpret stored HTML")
            checks.evaluate("document.querySelector('#product-dialog').close()")
            checks.click(selector + " .add-to-bag")
            checks.click('[data-shop-view="cart"]')
            no_injection("#shop-dialog", "Shopping bag preserves safe rendering of stored product names")

            checks.evaluate("VeloraAuth.logout()")
            checks.wait("location.pathname==='/login.html' && document.querySelector('#login-form')")
            checks.navigate("login.html?next=https%3A%2F%2Fexample.invalid%2F%3Csvg%20onload%3Dwindow.__auditXss%3D1%3E", ready="window.VeloraAuth")
            checks.check(checks.evaluate("location.origin===new URL(document.querySelector('link[rel=stylesheet]').href).origin && typeof window.__auditXss==='undefined' && !document.querySelector('[onload],[onerror]')"), "Untrusted return-path query is neither executed nor used as an external destination")
            checks.fill("#login-form", {"email":"audit-owner@example.test", "password":password})
            checks.submit("#login-form")
            checks.wait("location.pathname==='/admin.html' && window.VeloraAuth.user?.role==='admin'")
            checks.check(checks.evaluate("location.origin") == checks.origin, "Successful sign-in ignores an untrusted external return destination")
            report = f"PASS: {len(checks.passed)} XSS/request-boundary browser checks\n" + "\n".join(checks.passed) + "\n"
            (ROOT / "tmp/xss-browser-results.txt").write_text(report, encoding="utf-8")
            print(report.splitlines()[0])
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
