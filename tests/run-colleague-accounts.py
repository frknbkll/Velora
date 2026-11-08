"""Verify colleague creation, Full control and revocation in real Chrome."""
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

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
import server
from test_auth_server import Client, PASSWORD

BrowserConnection = runpy.run_path(str(ROOT / "tests/run-product-colors.py"))["BrowserConnection"]


def main():
    output = ROOT / "tmp"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="colleague-browser-", dir=output) as temporary:
        temporary = Path(temporary)
        app = server.make_server(port=0, database=temporary / "private/accounts.sqlite3", catalog=ROOT / "product-catalog.json", root=ROOT)
        app.RequestHandlerClass.log_message = lambda *args: None
        with app.connect() as db:
            db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,'admin',?)",
                       ("Legacy Owner", "owner@example.test", server.hash_password(PASSWORD), server.now_iso()))
        serving = threading.Thread(target=app.serve_forever, daemon=True)
        serving.start()
        owner, gmail, work_customer = Client(app), Client(app), Client(app)
        assert owner.login(email="owner@example.test")[0] == 200
        assert gmail.register(email="ordinary.customer@gmail.com")[0] == 201
        assert work_customer.register(email="public.customer@velora.com")[0] == 201
        assert owner.request("GET", "/api/admin/folder-access")[1]["colleagues"] == []
        assert owner.request("GET", "/api/admin/overview")[1]["totalCustomers"] == 2
        base = f"http://127.0.0.1:{app.server_port}"
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            debug_port = reservation.getsockname()[1]
        process = subprocess.Popen([
            "C:/Program Files/Google/Chrome/Application/chrome.exe", "--headless", "--disable-gpu", "--no-first-run",
            "--no-default-browser-check", f"--remote-debugging-port={debug_port}", f"--user-data-dir={temporary / 'chrome'}", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        connection = None
        screenshots = []
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json", timeout=1) as response:
                        page = next(item for item in json.load(response) if item["type"] == "page")
                    break
                except (OSError, StopIteration):
                    time.sleep(.1)
            else:
                raise RuntimeError("Chrome did not start")
            connection = BrowserConnection(page["webSocketDebuggerUrl"])
            connection.call("Page.enable")
            connection.call("Runtime.enable")
            connection.call("Network.enable")
            connection.call("Network.setCacheDisabled", {"cacheDisabled": True})
            connection.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
                window.__colleagueErrors=[];
                addEventListener('error',e=>{if(e.message)window.__colleagueErrors.push(e.message)});
                addEventListener('unhandledrejection',e=>window.__colleagueErrors.push(String(e.reason)));
                addEventListener('securitypolicyviolation',e=>window.__colleagueErrors.push('CSP '+e.violatedDirective+' '+e.blockedURI));
            """})

            def evaluate(expression):
                result = connection.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
                if "exceptionDetails" in result:
                    raise RuntimeError(result["exceptionDetails"])
                return result.get("result", {}).get("value")

            def until(expression, description):
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    if evaluate(expression):
                        return
                    time.sleep(.1)
                raise AssertionError(description + ": " + str(evaluate("({url:location.href,errors:window.__colleagueErrors,message:document.querySelector('#admin-folder-access-message')?.textContent,editor:document.querySelector('#admin-folder-access-edit-message')?.textContent,intranet:document.querySelector('#intranet-folder-feedback')?.textContent})")))

            def navigate(path, ready):
                same_page = evaluate("location.href") == base + path
                evaluate("window.__colleagueNavigationPending=true")
                connection.call("Page.reload", {"ignoreCache": True}) if same_page else connection.call("Page.navigate", {"url": base + path})
                until("!window.__colleagueNavigationPending && (" + ready + ")", "Page did not become ready")
                evaluate("document.documentElement.style.scrollBehavior='auto';document.body.style.scrollBehavior='auto'")

            def set_cookie(client):
                connection.call("Network.clearBrowserCookies")
                name, value = client.cookie.split("=", 1)
                assert connection.call("Network.setCookie", {"name": name, "value": value, "url": base, "path": "/", "httpOnly": True, "sameSite": "Lax"})["success"]

            def no_errors(description):
                assert not evaluate("window.__colleagueErrors || []"), description + ": runtime/CSP errors"

            def no_overflow(description):
                assert evaluate("document.documentElement.scrollWidth<=innerWidth"), description + ": page overflow"
                if evaluate("document.querySelector('#admin-folder-access-dialog')?.open"):
                    assert evaluate("(()=>{const d=document.querySelector('#admin-folder-access-dialog');return d.scrollWidth<=d.clientWidth && d.getBoundingClientRect().width<=innerWidth})()"), description + ": dialog overflow"

            def screenshot(name):
                path = output / f"colleague-accounts-{name}.png"
                path.write_bytes(base64.b64decode(connection.call("Page.captureScreenshot", {"format": "png"})["data"]))
                screenshots.append(path.name)

            connection.call("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
            set_cookie(owner)
            navigate("/admin.html#folder-access", "document.querySelector('#admin-colleague-create') && !document.querySelector('#admin-colleague-create').disabled")
            assert evaluate("document.querySelectorAll('#admin-folder-access-rows [data-colleague-id]').length===0"), "Customer accounts appeared in colleague table"
            assert evaluate("!document.querySelector('#admin-folder-access-rows').textContent.includes('ordinary.customer@gmail.com') && !document.querySelector('#admin-folder-access-rows').textContent.includes('public.customer@velora.com')")
            evaluate("document.querySelector('#admin-colleague-create').click()")
            until("document.querySelector('#admin-folder-access-dialog').open", "Create dialog did not open")
            evaluate(f"""
              document.querySelector('#admin-colleague-first-name').value='New';
              document.querySelector('#admin-colleague-last-name').value='Colleague Owner';
              document.querySelector('#admin-colleague-email').value='newowner@velora.com';
              document.querySelector('#admin-colleague-email').dispatchEvent(new Event('input',{{bubbles:true}}));
              document.querySelector('#admin-colleague-password').value={json.dumps(PASSWORD)};
              document.querySelector('#admin-folder-access-role').value='owner';
              document.querySelector('#admin-folder-access-role').dispatchEvent(new Event('change',{{bubbles:true}}));
              document.querySelector('#admin-folder-access-department').value='leadership';
              document.querySelector('#admin-folder-access-department').dispatchEvent(new Event('change',{{bubbles:true}}));
            """)
            assert evaluate("!document.querySelector('#admin-folder-access-full-control').hidden && [...document.querySelectorAll('#admin-folder-access-permissions select')].every(s=>s.disabled && s.value==='write')"), "Full control folder permissions were not clear"
            no_overflow("Desktop create")
            evaluate("document.querySelector('#admin-folder-access-dialog').scrollTop=0")
            screenshot("create-desktop")
            evaluate("document.querySelector('#admin-folder-access-form').requestSubmit()")
            until("!document.querySelector('#admin-folder-access-dialog').open && document.querySelectorAll('#admin-folder-access-rows tr[data-colleague-id]').length===1", "Colleague creation failed")
            assert evaluate("document.querySelector('#admin-colleague-password').value===''")
            assert evaluate("document.querySelector('#admin-folder-access-rows').textContent.includes('All shared folders') && document.querySelector('#admin-folder-access-rows').textContent.includes('newowner@velora.com')")
            no_overflow("Desktop colleague list")
            screenshot("list-desktop")
            no_errors("Desktop create")
            colleague = owner.request("GET", "/api/admin/folder-access")[1]["colleagues"][0]
            assert colleague["role"] == "owner" and colleague["fullControl"]
            assert owner.request("GET", "/api/admin/overview")[1]["totalCustomers"] == 2
            customer_emails = {item["email"] for item in owner.request("GET", "/api/admin/customers")[1]["customers"]}
            assert customer_emails == {"ordinary.customer@gmail.com", "public.customer@velora.com"}

            full = Client(app)
            assert full.login(email="newowner@velora.com")[0] == 200
            set_cookie(full)
            navigate("/intranet.html#folders", "document.querySelectorAll('#intranet-folder-grid [data-folder]').length===10")
            assert evaluate("[...document.querySelectorAll('#intranet-folder-grid button')].every(b=>!b.disabled && b.textContent.includes('Manage'))"), "Full control did not expose management of every folder"
            private_urls = []
            for folder in ("finance", "people"):
                evaluate(f"document.querySelector('#intranet-folder-grid [data-folder={folder}]').click()")
                until("document.querySelector('#intranet-file-list').getAttribute('aria-busy')==='false' && !document.querySelector('#intranet-file-write-actions').hidden", "Restricted department did not open with write access")
                evaluate("document.querySelector('#intranet-new-note').click()")
                until("document.querySelector('#intranet-note-dialog').open", "Note editor did not open")
                evaluate(f"document.querySelector('#intranet-note-name').value='Full control {folder} fixture';document.querySelector('#intranet-note-text').value='Disposable full control browser fixture';document.querySelector('#intranet-note-form').requestSubmit()")
                until("!document.querySelector('#intranet-note-dialog').open && document.querySelectorAll('.intranet-file-card').length===1 && !document.querySelector('#intranet-upload-button').disabled", "Full control note write failed")
                files = full.request("GET", f"/api/intranet/folders/{folder}/files")[1]["files"]
                assert len(files) == 1
                private_urls.append(files[0]["downloadUrl"])
                evaluate("document.querySelector('#intranet-folders-back').click()")
            no_errors("Full control intranet")

            set_cookie(owner)
            navigate("/admin.html#folder-access", "document.querySelectorAll('#admin-folder-access-rows tr[data-colleague-id]').length===1")
            evaluate("document.querySelector('.folder-access-edit').click()")
            until("document.querySelector('#admin-folder-access-dialog').open", "Account editor failed")
            evaluate("""
              document.querySelector('#admin-folder-access-role').value='colleague';
              document.querySelector('#admin-folder-access-role').dispatchEvent(new Event('change',{bubbles:true}));
              document.querySelector('#admin-folder-access-department').value='creative';
              document.querySelector('#admin-folder-access-department').dispatchEvent(new Event('change',{bubbles:true}));
              document.querySelector('#admin-folder-access-permissions [data-folder=creative]').value='read';
              document.querySelector('#admin-folder-access-permissions [data-folder=creative]').dispatchEvent(new Event('change',{bubbles:true}));
            """)
            assert evaluate("document.querySelector('#admin-folder-access-permissions [data-folder=finance]').disabled && document.querySelector('#admin-folder-access-permissions [data-folder=people]').disabled"), "Restricted department controls did not return after removing Full control"
            evaluate("document.querySelector('#admin-folder-access-form').requestSubmit()")
            until("!document.querySelector('#admin-folder-access-dialog').open && document.querySelector('#admin-folder-access-message').textContent.includes('Access saved')", "Role edit failed")
            assert full.request("GET", "/api/auth/me")[1]["user"] is None, "Role change retained privileged session"
            assert full.login(email="newowner@velora.com")[0] == 200
            assert full.request("GET", "/api/admin/folder-access")[0] == 403
            assert full.request("GET", "/api/intranet/folders/creative/files")[0] == 200
            for path in private_urls:
                assert full.request("GET", path)[0] == 403
            assert owner.request("GET", "/api/admin/overview")[1]["totalCustomers"] == 2
            no_errors("Role edit")

            connection.call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
            navigate("/admin.html#folder-access", "document.querySelectorAll('#admin-folder-access-rows tr[data-colleague-id]').length===1")
            before_mobile = evaluate("({inner:innerWidth,client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,banner:document.querySelector('#privacy-banner')?.getBoundingClientRect().width})")
            evaluate("document.querySelector('#privacy-banner').style.width='calc(100vw - 24px)';document.querySelector('#privacy-banner').style.maxWidth='calc(100vw - 24px)'")
            time.sleep(.2)
            print({'beforeMobile':before_mobile,'afterBannerWidth':evaluate("({inner:innerWidth,client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,banner:document.querySelector('#privacy-banner')?.getBoundingClientRect().width})")},flush=True)
            print(evaluate("[...document.querySelectorAll('body > *, .admin-shell > *, .admin-sidebar > *, .admin-main > *, #admin-folder-access > *')].map(e=>({tag:e.tagName,id:e.id,c:String(e.className),x:e.getBoundingClientRect().x,r:e.getBoundingClientRect().right,w:e.getBoundingClientRect().width,overflow:getComputedStyle(e).overflowX,min:getComputedStyle(e).minWidth,grid:getComputedStyle(e).gridTemplateColumns})).filter(e=>e.w>0)"),flush=True)
            for selector in ['.privacy-banner','.folder-access-table-scroll','.admin-nav','.admin-sidebar-bottom','.admin-sidebar']:
                print(evaluate("(()=>{const e=document.querySelector("+json.dumps(selector)+");e.style.display='none';return {hidden:"+json.dumps(selector)+",inner:innerWidth,scroll:document.documentElement.scrollWidth}})()"),flush=True)
            assert evaluate("innerWidth===390"), "Mobile layout viewport was wider than the device: " + str(evaluate("({inner:innerWidth,client:document.documentElement.clientWidth,visual:visualViewport.width,scale:visualViewport.scale,wide:[...document.querySelectorAll('body *')].map(e=>({tag:e.tagName,id:e.id,c:e.className,r:e.getBoundingClientRect().right,w:e.getBoundingClientRect().width})).filter(e=>e.w>390).slice(0,16)})"))
            evaluate("document.querySelector('#admin-colleague-create').click()")
            until("document.querySelector('#admin-folder-access-dialog').open", "Mobile account creation did not open")
            no_overflow("Mobile create")
            screenshot("create-mobile")
            evaluate("document.querySelector('#admin-colleague-password').value='a temporary test-only password';document.querySelector('#admin-folder-access-cancel').click()")
            assert evaluate("document.querySelector('#admin-colleague-password').value===''")
            evaluate("document.querySelector('.folder-access-edit').click()")
            until("document.querySelector('#admin-folder-access-dialog').open", "Mobile account editor failed")
            no_overflow("Mobile edit")
            screenshot("edit-mobile")
            evaluate("document.querySelector('#admin-folder-access-cancel').click()")
            no_errors("Mobile")
            result = {"customerSeparation": "gmail and public company-email customers excluded", "createAccount": "saved @velora.com colleague",
                      "fullControl": "all ten folders manageable; Finance and HR writes verified", "roleEdit": "intranet-only role applied and privileged session revoked",
                      "passwordClearing": "save and close verified", "customerOverview": "colleagues excluded", "desktopAndMobile": "no horizontal overflow",
                      "runtimeAndCSP": "no errors", "screenshots": screenshots}
            (output / "colleague-accounts-check-results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
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
