"""Check account recovery from a static preview without opening the real database.

Run ``python py/tests/run-account-connection.py`` from the project root. Chrome is
required, as with the main account browser checks. No requests are sent to the
user's running account server; recovery links are inspected, never followed.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file


from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
from pathlib import Path
import runpy
import secrets
import tempfile
import threading


browser = runpy.run_path(str(ROOT / "py/tests" / "run-account-browser.py"))
Checks = browser["Checks"]
start_chrome = browser["start_chrome"]


class StaticPreview(SimpleHTTPRequestHandler):
    """Represent an IDE preview: assets work, but no account API exists."""

    def do_GET(self):
        if self.path.startswith("/api/"):
            self.send_error(404, "Not Found")
            return
        super().do_GET()

    def log_message(self, *args):
        pass


def assert_recovery(checks, expected_path="/login.html", expected_next=None):
    checks.wait("document.querySelector('#account-server-link') && document.querySelector('#account-connection-help')?.getClientRects().length > 0")
    link = checks.evaluate("(() => { const link = document.querySelector('#account-server-link'); const url = new URL(link.href); return {origin: url.origin, path: url.pathname, query: [...url.searchParams.entries()], text: Array.from(document.querySelectorAll('#auth-message, #account-loading, #admin-access-message, #account-connection-help'), node => node.textContent).join(' ')}; })()")
    checks.check(link["origin"] == "http://127.0.0.1:8000", "Local recovery points to the account server without changing API origins")
    checks.check(link["path"] == expected_path, f"Recovery opens {expected_path}")
    checks.check(all(key == "next" and value in {"account.html", "admin.html"} for key, value in link["query"]), "Recovery forwards only an approved destination")
    if expected_next is not None:
        checks.check(link["query"] == [["next", expected_next]], f"Recovery retains the {expected_next} destination")
    checks.check(any(word in link["text"].lower() for word in ("server", "preview", "python")), "Connection recovery explains the local server requirement")
    return link


def run_scenarios(checks, static_origin, real_origin):
    checks.origin = static_origin
    checks.navigate("login.html", ready="window.VeloraAuth")
    checks.check(checks.evaluate("location.origin") == static_origin, "Static login stays on its original page until the recovery link is selected")
    link = assert_recovery(checks)
    checks.check(not link["query"], "Ordinary sign-in recovery has no extra query values")
    checks.fill("#login-form", {"email": "connection-check@example.test", "password": "Temporary form value only"})
    checks.check(checks.evaluate("!document.querySelector('#account-server-link').href.includes('connection-check') && !document.querySelector('#account-server-link').href.includes('Temporary')"), "Recovery links never contain entered account details")
    checks.viewport(320)
    checks.check(checks.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "Recovery guidance fits a 320px phone")

    checks.navigate("login.html?next=admin.html", ready="window.VeloraAuth")
    assert_recovery(checks, expected_next="admin.html")
    checks.navigate("login.html?next=account.html", ready="window.VeloraAuth")
    assert_recovery(checks, expected_next="account.html")
    checks.navigate("login.html?next=https%3A%2F%2Fexample.test%2F&email=never-forward@example.test", ready="window.VeloraAuth")
    link = assert_recovery(checks)
    checks.check(not link["query"], "Recovery discards an external destination and unrelated query fields")

    checks.navigate("register.html", ready="window.VeloraAuth")
    assert_recovery(checks, expected_path="/register.html")
    checks.navigate("account.html", ready="window.VeloraAuth")
    assert_recovery(checks, expected_next="account.html")
    checks.check(checks.evaluate("document.querySelector('#account-content').hidden"), "A disconnected account page does not reveal private profile content")
    checks.navigate("admin.html", ready="window.VeloraAuth")
    assert_recovery(checks, expected_next="admin.html")
    checks.check(checks.evaluate("document.querySelector('#admin-shell').hidden"), "A disconnected admin page does not reveal its protected dashboard")

    checks.navigate("index.html", ready="window.VeloraAuth")
    checks.wait("Array.from(document.querySelectorAll('[data-auth-link]')).every(link => link.href === 'http://127.0.0.1:8000/login.html')")
    checks.check(checks.evaluate("document.querySelectorAll('[data-auth-link]').length > 0"), "Static storefront account links open the real account server")

    checks.connection.call("Page.navigate", {"url": (ROOT / "html/login.html").as_uri()})
    checks.wait("location.protocol === 'file:' && document.readyState === 'complete' && window.VeloraAuth")
    assert_recovery(checks)
    checks.check(checks.evaluate("location.protocol === 'file:'"), "Directly opened HTML explains recovery without an automatic redirect")

    checks.origin = real_origin
    checks.navigate("login.html", ready="window.VeloraAuth")
    checks.check(checks.evaluate("window.VeloraAuth.ready.then(user => user === null)"), "The real account API correctly recognizes an anonymous visitor")
    checks.check(checks.evaluate("!document.querySelector('#account-connection-help') || !document.querySelector('#account-connection-help').getClientRects().length"), "A working account server shows no connection warning")
    checks.fill("#login-form", {"email": f"no-such-member-{secrets.token_hex(5)}@example.test", "password": secrets.token_urlsafe(24)})
    checks.submit("#login-form")
    checks.wait("document.querySelector('#auth-message').classList.contains('is-error')")
    checks.check("incorrect" in checks.evaluate("document.querySelector('#auth-message').textContent").lower(), "Invalid credentials retain the server's sign-in error")
    checks.check(checks.evaluate("!document.querySelector('#account-connection-help') || !document.querySelector('#account-connection-help').getClientRects().length"), "An invalid password is not misreported as a connection failure")


def main():
    (ROOT / "tmp").mkdir(exist_ok=True)
    spec = importlib.util.spec_from_file_location("velora_connection_test_server", ROOT / "py/app/server.py")
    server_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server_module)
    server_module.VeloraHandler.log_message = lambda *args: None
    with tempfile.TemporaryDirectory(prefix="account-connection-", dir=ROOT / "tmp", ignore_cleanup_errors=True) as temporary:
        temporary = Path(temporary)
        static = ThreadingHTTPServer(("127.0.0.1", 0), partial(StaticPreview, directory=str(ROOT)))
        static.daemon_threads = True
        real = server_module.make_server(host="127.0.0.1", port=0, database=temporary / "test.sqlite3", catalog=ROOT / "json/catalog/product-catalog.json", root=ROOT)
        threads = [threading.Thread(target=app.serve_forever, daemon=True) for app in (static, real)]
        for thread in threads:
            thread.start()
        process = connection = checks = None
        try:
            process, connection = start_chrome(temporary / "chrome-profile")
            checks = Checks(connection, f"http://127.0.0.1:{static.server_port}")
            run_scenarios(checks, f"http://127.0.0.1:{static.server_port}", f"http://127.0.0.1:{real.server_port}")
            report = f"PASS: {len(checks.passed)} account connection browser checks\n" + "\n".join(checks.passed) + "\n"
            (ROOT / "tmp" / "account-connection-results.txt").write_text(report, encoding="utf-8")
            print(report.splitlines()[0])
        except BaseException as error:
            report = f"FAIL: {type(error).__name__}: {error}\nCompleted checks: {len(checks.passed) if checks else 0}\n"
            (ROOT / "tmp" / "account-connection-results.txt").write_text(report, encoding="utf-8")
            raise
        finally:
            if connection:
                connection.socket.close()
            if process:
                process.terminate()
                process.wait(timeout=10)
            for app in (static, real):
                app.shutdown()
                app.server_close()
            for thread in threads:
                thread.join(timeout=10)


if __name__ == "__main__":
    main()
