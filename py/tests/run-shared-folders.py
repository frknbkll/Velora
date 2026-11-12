"""Exercise department permissions and shared files in real Chrome with disposable accounts."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

import base64
import json
from pathlib import Path
import runpy
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

import server
from test_auth_server import Client, PASSWORD
from test_catalog_server import png

BrowserConnection = runpy.run_path(str(ROOT / "py/tests/run-product-colors.py"))["BrowserConnection"]
CHROME = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")


def main():
    output = ROOT / "tmp"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="shared-folders-check-", dir=output) as temporary:
        temporary = Path(temporary)
        app = server.make_server(port=0, database=temporary / "private" / "accounts.sqlite3",
                                 catalog=ROOT / "json/catalog/product-catalog.json", root=ROOT)
        app.RequestHandlerClass.log_message = lambda *args: None
        password_hash = server.hash_password(PASSWORD)
        with app.connect() as db:
            owner_id = db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,'admin',?)",
                                  ("Folder Test Owner", "folder-owner@example.test", password_hash, server.now_iso())).lastrowid
            staff_id = db.execute("INSERT INTO users(name,email,password_hash,role,created_at,account_type) VALUES(?,?,?,'customer',?,'velora')",
                                  ("Folder Test Colleague", "folder-staff@velora.com", password_hash, server.now_iso())).lastrowid
        serving = threading.Thread(target=app.serve_forever, daemon=True)
        serving.start()
        owner, staff = Client(app), Client(app)
        assert owner.login(email="folder-owner@example.test")[0] == 200
        assert staff.login(email="folder-staff@velora.com")[0] == 200
        base = f"http://127.0.0.1:{app.server_port}"
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            debug_port = reservation.getsockname()[1]
        process = subprocess.Popen([
            str(CHROME), "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
            f"--remote-debugging-port={debug_port}", f"--user-data-dir={temporary / 'chrome'}", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        connection = None
        observations = []
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json", timeout=1) as response:
                        page = next(page for page in json.load(response) if page["type"] == "page")
                    break
                except (OSError, StopIteration):
                    time.sleep(.1)
            else:
                raise RuntimeError("Headless Chrome did not start")
            connection = BrowserConnection(page["webSocketDebuggerUrl"])
            connection.call("Page.enable")
            connection.call("Runtime.enable")
            connection.call("Network.enable")
            connection.call("Network.setCacheDisabled", {"cacheDisabled": True})
            connection.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
              window.__folderTestErrors=[];
              addEventListener('error',e=>{if(e.message)window.__folderTestErrors.push(e.message)});
              addEventListener('unhandledrejection',e=>window.__folderTestErrors.push(String(e.reason)));
              addEventListener('securitypolicyviolation',e=>window.__folderTestErrors.push('CSP '+e.violatedDirective+' '+e.blockedURI));
            """})

            def evaluate(expression):
                result = connection.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
                if "exceptionDetails" in result:
                    raise RuntimeError(result["exceptionDetails"])
                return result.get("result", {}).get("value")

            def until(expression, label, seconds=20):
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    if evaluate(expression):
                        return
                    time.sleep(.1)
                raise AssertionError(label + ": " + str(evaluate("({url:location.href,errors:window.__folderTestErrors,feedback:document.querySelector('#intranet-folder-feedback')?.textContent,writing:document.querySelector('#intranet-upload-button')?.disabled,body:document.body?.innerText.slice(-1800)})")))

            def set_cookie(client):
                connection.call("Network.clearBrowserCookies")
                name, value = client.cookie.split("=", 1)
                result = connection.call("Network.setCookie", {"name": name, "value": value, "url": base,
                                                               "path": "/", "httpOnly": True, "sameSite": "Lax"})
                assert result["success"], "Session fixture cookie was rejected"

            def screenshot(name):
                path = output / f"shared-folders-{name}.png"
                path.write_bytes(base64.b64decode(connection.call("Page.captureScreenshot", {"format": "png"})["data"]))
                return path.name

            def navigate(path, ready):
                connection.call("Page.navigate", {"url": base + path})
                until(ready, "Page did not become ready")
                evaluate("document.documentElement.style.scrollBehavior='auto';document.body.style.scrollBehavior='auto'")

            def no_errors(label):
                errors = evaluate("window.__folderTestErrors || []")
                assert not errors, label + " errors: " + json.dumps(errors)

            def overflow(label):
                assert evaluate("document.documentElement.scrollWidth<=innerWidth"), label + " horizontal overflow"

            connection.call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
            set_cookie(owner)
            navigate("/admin.html#folder-access", "document.querySelectorAll('#admin-folder-access-rows tr[data-colleague-id]').length===1")
            evaluate("document.querySelector('#admin-folder-access-search').value='folder-staff';document.querySelector('#admin-folder-access-search').dispatchEvent(new Event('input',{bubbles:true}))")
            assert evaluate("document.querySelectorAll('#admin-folder-access-rows tr[data-colleague-id]').length===1"), "Colleague search failed"
            evaluate("document.querySelector('.folder-access-edit').click()")
            until("document.querySelector('#admin-folder-access-dialog').open", "Access editor did not open")
            evaluate("""
              document.querySelector('#admin-folder-access-active').checked=true;
              document.querySelector('#admin-folder-access-active').dispatchEvent(new Event('change',{bubbles:true}));
              document.querySelector('#admin-folder-access-department').value='finance';
              document.querySelector('#admin-folder-access-department').dispatchEvent(new Event('change',{bubbles:true}));
              document.querySelector('[data-folder=finance]').value='write';
              document.querySelector('[data-folder=finance]').dispatchEvent(new Event('change',{bubbles:true}));
              document.querySelector('[data-folder=company]').value='write';
              document.querySelector('[data-folder=company]').dispatchEvent(new Event('change',{bubbles:true}));
            """)
            assert evaluate("document.querySelector('[data-folder=people]').disabled && !document.querySelector('[data-folder=finance]').disabled"), "HR restriction missing in Finance editor"
            overflow("Desktop admin editor")
            evaluate("document.querySelector('[data-folder=finance]').scrollIntoView({block:'center'})")
            observations.append(screenshot("admin-editor-desktop"))
            evaluate("document.querySelector('#admin-folder-access-form').requestSubmit()")
            until("!document.querySelector('#admin-folder-access-dialog').open && document.querySelector('#admin-folder-access-message').textContent.includes('Access saved')", "Access save failed")
            result = owner.request("GET", "/api/admin/folder-access")[1]
            colleague = next(item for item in result["colleagues"] if item["id"] == staff_id)
            assert colleague["active"] and colleague["department"] == "finance"
            assert {"folder": "finance", "access": "write"} in colleague["grants"]
            assert staff.request("GET", "/api/auth/me")[1]["user"]["role"] == "customer"
            assert staff.request("GET", "/api/admin/folder-access")[0] == 403
            no_errors("Admin")

            set_cookie(staff)
            navigate("/intranet.html#folders", "document.querySelectorAll('#intranet-folder-grid [data-folder]').length===10")
            assert evaluate("document.querySelectorAll('#intranet-folder-grid button svg.intranet-folder-art').length===10"), "Department folder SVGs missing"
            assert evaluate("!document.querySelector('#intranet-folder-grid [data-folder=finance]').disabled && document.querySelector('#intranet-folder-grid [data-folder=people]').disabled"), "Department folder lock states wrong"
            evaluate("document.querySelector('#folders').scrollIntoView({block:'start'})")
            overflow("Desktop intranet")
            observations.append(screenshot("grid-desktop"))
            evaluate("document.querySelector('#intranet-folder-grid [data-folder=finance]').click()")
            until("!document.querySelector('#intranet-file-browser').hidden && document.querySelector('#intranet-file-list').getAttribute('aria-busy')==='false'", "Finance browser did not open")
            evaluate("document.querySelector('#intranet-new-note').click();document.querySelector('#intranet-note-name').value='Finance browser test';document.querySelector('#intranet-note-text').value='Confidential finance planning. <script>literal text</script>';document.querySelector('#intranet-note-form').requestSubmit()")
            until("!document.querySelector('#intranet-note-dialog').open && document.querySelectorAll('.intranet-file-card').length===1", "Team note did not save")
            until("!document.querySelector('#intranet-upload-button').disabled", "Note did not finish refreshing its folder")
            evaluate("[...document.querySelectorAll('.intranet-file-actions button')].find(button=>button.textContent==='Read note').click()")
            until("document.querySelector('#intranet-read-note-dialog').open", "Read note dialog did not open")
            assert evaluate("document.querySelector('#intranet-read-note-content').textContent.includes('<script>literal text</script>')"), "Note text was not preserved safely"
            evaluate("document.querySelector('#intranet-read-note-dialog [data-intranet-dialog-close]').click()")
            fixture = temporary / "Finance upload.png"
            fixture.write_bytes(png(40, 60))
            document = connection.call("DOM.getDocument")
            upload_input = connection.call("DOM.querySelector", {"nodeId": document["root"]["nodeId"], "selector": "#intranet-upload-input"})
            connection.call("DOM.setFileInputFiles", {"nodeId": upload_input["nodeId"], "files": [str(fixture)]})
            until("[...document.querySelectorAll('.intranet-file-card')].some(card=>card.querySelector('h3').textContent==='Finance upload.png' && card.querySelector('img')?.naturalWidth===40)", "Uploaded raster preview failed")
            until("!document.querySelector('#intranet-upload-button').disabled", "Upload did not finish refreshing its folder")
            evaluate("document.querySelector('#folders').scrollIntoView({block:'start'})")
            observations.append(screenshot("finance-files-desktop"))
            evaluate("[...document.querySelectorAll('.intranet-file-card')].find(card=>card.querySelector('h3').textContent==='Finance upload.png').querySelector('.intranet-file-delete').click()")
            assert evaluate("document.querySelector('#intranet-delete-dialog').open"), "Delete confirmation did not open"
            evaluate("document.querySelector('#intranet-confirm-delete').click()")
            until("!document.querySelector('#intranet-delete-dialog').open && document.querySelectorAll('.intranet-file-card').length===1", "Private file deletion failed")
            assert len(staff.request("GET", "/api/intranet/folders/finance/files")[1]["files"]) == 1
            evaluate("document.querySelector('#intranet-folders-back').click();document.querySelector('#intranet-folder-grid [data-folder=company]').click()")
            until("document.querySelectorAll('.intranet-file-card').length===30 && !document.querySelector('#intranet-show-files').hidden", "Company library pagination missing")
            assert evaluate("[...document.querySelectorAll('.intranet-file-source')].every(item=>item.textContent==='PUBLIC WEBSITE ORIGINAL')"), "Public originals label missing"
            evaluate("document.querySelector('#intranet-show-files').click()")
            assert evaluate("document.querySelectorAll('.intranet-file-card').length===60"), "Show more files failed"
            evaluate("document.querySelector('#intranet-file-search').value='Published product catalog.json';document.querySelector('#intranet-file-search').dispatchEvent(new Event('input',{bubbles:true}))")
            assert evaluate("document.querySelectorAll('.intranet-file-card').length===1 && document.querySelector('.intranet-file-card h3').textContent==='Published product catalog.json' && !document.querySelector('.intranet-file-card .intranet-file-delete')"), "Public catalog search/read-only state failed"
            no_errors("Desktop intranet")

            connection.call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
            evaluate("document.querySelector('#intranet-folders-back').click();document.querySelector('#folders').scrollIntoView({block:'start'})")
            time.sleep(.15)
            overflow("Mobile intranet grid")
            observations.append(screenshot("grid-mobile"))
            evaluate("document.querySelector('#intranet-folder-grid [data-folder=finance]').click()")
            until("document.querySelectorAll('.intranet-file-card').length===1", "Mobile finance browser failed")
            evaluate("document.querySelector('#folders').scrollIntoView({block:'start'})")
            overflow("Mobile files")
            observations.append(screenshot("finance-files-mobile"))
            assert evaluate("document.querySelectorAll('.intranet-file-card').length===1 && !document.querySelector('.intranet-layout').hidden"), "Private file fixture was not visible before history-cache check"
            evaluate("[...document.querySelectorAll('.intranet-file-actions button')].find(button=>button.textContent==='Read note').click()")
            until("document.querySelector('#intranet-read-note-dialog').open && document.querySelector('#intranet-read-note-content').textContent.includes('Confidential finance planning')", "Note fixture did not open before history-cache check")
            evaluate("dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true}))")
            assert evaluate("document.querySelector('.intranet-layout').hidden && getComputedStyle(document.querySelector('.intranet-layout')).display==='none'"), "History-cached workspace remained visible"
            assert evaluate("document.querySelectorAll('.intranet-file-card').length===0 && document.querySelectorAll('#intranet-folder-grid [data-folder]').length===0 && document.querySelector('#intranet-read-note-content').textContent==='' && !document.querySelector('#intranet-read-note-dialog').open"), "Private file or note remained after pagehide"
            evaluate("window.__historyRestoreSentinel=true;dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}))")
            until("!window.__historyRestoreSentinel && document.querySelectorAll('#intranet-folder-grid [data-folder]').length===10 && !document.querySelector('.intranet-layout').hidden", "History restore did not reload and recheck current access")
            evaluate("document.querySelector('#intranet-folder-grid [data-folder=finance]').click()")
            until("document.querySelectorAll('.intranet-file-card').length===1", "Finance files failed to reopen after fresh authorization")
            no_errors("Restored intranet")
            status = owner.request("PATCH", f"/api/admin/folder-access/{staff_id}", {"active": True, "department": "finance", "grants": [{"folder": "company", "access": "write"}]})[0]
            assert status == 200
            evaluate("document.querySelector('#intranet-folder-refresh').click()")
            until("document.querySelector('#intranet-file-browser').hidden && document.querySelector('#intranet-folder-grid [data-folder=finance]').disabled", "Revoked access did not clear file browser")
            assert evaluate("document.querySelectorAll('.intranet-file-card').length===0"), "Revoked file metadata remained in DOM"
            no_errors("Mobile intranet")

            set_cookie(owner)
            navigate("/admin.html#folder-access", "document.querySelectorAll('#admin-folder-access-rows tr[data-colleague-id]').length===1")
            evaluate(f"document.querySelector('[data-colleague-id=\"{staff_id}\"] .folder-access-edit').click()")
            until("document.querySelector('#admin-folder-access-dialog').open", "Mobile access editor failed")
            overflow("Mobile admin editor")
            observations.append(screenshot("admin-editor-mobile"))
            no_errors("Mobile admin")
            result = {"adminAccessEditor": "saved and enforced", "financeAndHR": "department restriction verified", "folderIcons": 10,
                      "note": "saved and read safely", "image": "uploaded and previewed", "delete": "confirmed",
                      "companyLibrary": "read-only originals, catalog search and pagination", "revocation": "immediate in same session",
                      "historyCache": "private content cleared; restored page reloads and reauthorizes", "desktopAndMobile": "no horizontal overflow", "runtimeAndCSP": "no errors", "screenshots": observations}
            (output / "shared-folders-check-results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps(result))
        finally:
            if connection:
                connection.socket.close()
            process.terminate()
            process.wait(timeout=10)
            app.shutdown()
            app.server_close()
            serving.join(timeout=5)


if __name__ == "__main__":
    main()
