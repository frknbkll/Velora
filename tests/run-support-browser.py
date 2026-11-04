"""Verify live support in two isolated Chrome profiles and a disposable database.

Run ``python tests/run-support-browser.py``. Live accounts and messages are never
opened or modified. Screenshots and results are written under ignored tmp/.
"""

from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path
import runpy
import secrets
import tempfile
import threading
import time


ROOT = Path(__file__).resolve().parent.parent
helpers = runpy.run_path(str(ROOT / "tests/run-account-browser.py"))
Checks = helpers["Checks"]
start_chrome = helpers["start_chrome"]


class SupportChecks(Checks):
    def wait_value(self, expression, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.evaluate(expression):
                return
            time.sleep(.1)
        raise AssertionError("Support API condition did not become true")

    def input(self, selector, value):
        self.evaluate(f"""(() => {{
            const field=document.querySelector({json.dumps(selector)});
            field.value={json.dumps(value)};
            field.dispatchEvent(new Event('input',{{bubbles:true}}));
            field.dispatchEvent(new Event('change',{{bubbles:true}}));
        }})()""")

    def focus_click(self, selector):
        self.evaluate(f"""(() => {{const button=document.querySelector({json.dumps(selector)});button.focus();button.click();}})()""")

    def screenshot_at(self, filename, width, height, selector=None):
        self.viewport(width, height)
        if selector:
            self.evaluate(f"document.querySelector({json.dumps(selector)}).scrollIntoView({{block:'start',behavior:'instant'}})")
        self.evaluate("new Promise(resolve=>setTimeout(resolve,400))")
        screenshot = self.connection.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        (ROOT / "tmp" / filename).write_bytes(base64.b64decode(screenshot["data"]))

    def support_session(self):
        return self.evaluate("fetch('/api/support/session',{cache:'no-store'}).then(r=>r.json())")

    def conversation(self):
        return self.evaluate("fetch('/api/support/conversation',{cache:'no-store'}).then(r=>r.json())")

    def open_chat(self, selector="#support-launcher"):
        if not self.evaluate("Boolean(document.querySelector('#support-chat')?.open)"):
            self.focus_click(selector)
        self.wait("document.querySelector('#support-chat').open && !document.querySelector('#support-message').disabled")
        self.wait("!document.querySelector('#support-context').textContent.includes('Connecting')")

    def send_customer(self, text):
        self.input("#support-message", text)
        self.submit("#support-form")
        self.wait(f"document.querySelector('#support-message').value === '' && [...document.querySelectorAll('#support-messages .support-message-body')].some(p=>p.textContent === {json.dumps(text)})")

    def send_staff(self, text):
        self.input("#support-reply", text)
        self.submit("#support-reply-form")
        self.wait(f"document.querySelector('#support-reply').value === '' && [...document.querySelectorAll('#support-messages .support-message p')].some(p=>p.textContent === {json.dumps(text)})")

    def login(self, email, password, target="account.html"):
        self.navigate("login.html?next=" + target, ready="window.VeloraAuth && document.querySelector('#login-form')")
        self.fill("#login-form", {"email": email, "password": password})
        self.submit("#login-form")
        self.wait(f"location.pathname === '/{target}' && document.readyState === 'complete'")
        if target == "admin.html":
            self.wait("document.querySelector('#admin-shell') && !document.querySelector('#admin-shell').hidden")


def scenarios(customer, staff, app, account_email, admin_email, password):
    customer.navigate("contact.html", ready="window.VeloraAuth && document.querySelector('#support-launcher')")
    customer.evaluate("window.__supportPageId='original-customer-document';document.querySelector('#privacy-banner [data-privacy-choice=\"necessary\"]')?.click()")
    cookies = customer.connection.call("Network.getCookies", {"urls": [customer.origin + "/api/support/session"]})["cookies"]
    customer.check(not any(cookie["name"] == "velora_support" for cookie in cookies), "Loading a public page does not create a guest chat cookie")
    customer.open_chat("[data-support-open]")
    initial = customer.support_session()
    customer.check(initial["customer"]["guest"] and initial["conversation"] is None and not initial["availability"]["online"], "Guest chat starts empty and accurately reports no available staff")
    customer.check(customer.evaluate("!document.cookie.includes('velora_support')"), "Guest chat session is inaccessible to page JavaScript")
    cookies = customer.connection.call("Network.getCookies", {"urls": [customer.origin + "/api/support/session"]})["cookies"]
    support_cookie = next(cookie for cookie in cookies if cookie["name"] == "velora_support")
    customer.check(support_cookie["httpOnly"] and support_cookie.get("sameSite") == "Strict" and support_cookie["path"] == "/api/support", "Guest cookie is HttpOnly, SameSite Strict and scoped to support")
    customer.input("#support-name", "Guest Browser Tester")
    first = "Hello, I would like some help choosing a size."
    customer.send_customer(first)
    first_state = customer.conversation()
    thread_id = first_state["conversation"]["id"]
    customer.check(first_state["conversation"]["customerName"] == "Guest Browser Tester" and first_state["messages"][-1]["body"] == first, "Guest message is persisted with the optional display name")
    customer.check(customer.evaluate("document.querySelector('#support-status').textContent.toLowerCase().includes('message') || document.querySelector('#support-status').textContent.toLowerCase().includes('offline')"), "Offline chat invites a saved message without pretending staff are online")

    staff.navigate("contact.html", ready="window.VeloraAuth && document.querySelector('#support-launcher')")
    staff.evaluate("document.querySelector('#privacy-banner [data-privacy-choice=\"necessary\"]')?.click()")
    staff.open_chat()
    staff.check(staff.support_session()["conversation"] is None and not staff.evaluate(f"document.querySelector('#support-messages').textContent.includes({json.dumps(first)})"), "A separate guest browser cannot see the first guest's conversation")
    staff.login(admin_email, password, "admin.html")
    staff.focus_click('[data-admin-section="support"]')
    staff.wait("!document.querySelector('#admin-support').hidden && document.querySelector('#support-conversations [data-conversation-id]')")
    staff.wait(f"document.querySelector('#support-conversations [data-conversation-id=\"{thread_id}\"]')")
    staff.focus_click(f'#support-conversations [data-conversation-id="{thread_id}"]')
    staff.wait(f"!document.querySelector('#support-thread').hidden && document.querySelector('#support-messages').textContent.includes({json.dumps(first)})")
    staff.check(staff.evaluate("document.querySelector('#support-thread-name').textContent.includes('Guest Browser Tester')"), "Staff inbox receives the real guest conversation")
    customer.wait("document.querySelector('#support-status').textContent.toLowerCase().includes('online')", timeout=20)
    customer.check(customer.support_session()["availability"]["online"], "Opening an available staff inbox updates the live customer availability status")
    reply = "<img src=x onerror=alert(1)> We can help you compare the size guide."
    staff.send_staff(reply)
    customer.wait(f"[...document.querySelectorAll('#support-messages .support-message-body')].some(p=>p.textContent === {json.dumps(reply)})", timeout=20)
    customer.check(customer.evaluate("window.__supportPageId === 'original-customer-document' && !document.querySelector('#support-messages img')"), "A real staff reply appears without reload and HTML-looking text stays plain text")

    customer.focus_click("#support-close")
    second_reply = "Please tell us which piece you are considering."
    staff.send_staff(second_reply)
    customer.wait("Number(document.querySelector('#support-unread').textContent) > 0", timeout=20)
    customer.check(True, "A reply received while the chat is closed raises the customer unread badge")
    customer.open_chat()
    customer.wait(f"document.querySelector('#support-messages').textContent.includes({json.dumps(second_reply)}) && Number(document.querySelector('#support-unread').textContent || '0') === 0", timeout=20)
    customer.check(True, "Opening the conversation displays and marks the unread reply")

    customer.input("#support-message", "This draft must survive background message polling.")
    customer.evaluate("new Promise(resolve=>setTimeout(resolve,3600))")
    customer.check(customer.evaluate("document.querySelector('#support-message').value === 'This draft must survive background message polling.'"), "Live polling preserves the customer's unsent draft")
    staff.input("#support-reply", "A staff draft that must survive polling.")
    staff.evaluate("new Promise(resolve=>setTimeout(resolve,3600))")
    staff.check(staff.evaluate("document.querySelector('#support-reply').value === 'A staff draft that must survive polling.'"), "Live polling preserves the staff member's unsent reply")
    staff.input("#support-reply", "")
    customer.input("#support-message", "")

    staff.focus_click('[data-admin-section="overview"]')
    customer.wait("!document.querySelector('#support-status').textContent.toLowerCase().includes('online')", timeout=20)
    customer.check(not customer.support_session()["availability"]["online"], "Leaving the staff inbox removes the online availability signal")
    follow_up = "I am considering the ivory set. Thank you."
    customer.send_customer(follow_up)
    unread = staff.evaluate(f"window.VeloraAuth.request('/api/admin/support?status=all').then(data=>data.conversations.find(c=>c.id === {json.dumps(thread_id)}).unreadCount)")
    staff.check(unread >= 1, "Customer follow-up remains unread until staff view the conversation")
    staff.focus_click('[data-admin-section="support"]')
    staff.wait(f"document.querySelector('#support-messages').textContent.includes({json.dumps(follow_up)})")
    staff.evaluate("(() => {const log=document.querySelector('#support-messages');log.scrollIntoView({block:'center',behavior:'instant'});log.scrollTop=log.scrollHeight;log.focus({preventScroll:true});log.dispatchEvent(new Event('scroll'));})()")
    staff.wait_value(f"window.VeloraAuth.request('/api/admin/support?status=all').then(data=>data.conversations.find(c=>c.id === {json.dumps(thread_id)}).unreadCount === 0)")
    staff.check(True, "Visible staff conversation marks the customer's message read")
    staff.focus_click("#support-conversation-status")
    staff.wait("document.querySelector('#support-thread-status').textContent.toLowerCase().includes('closed')")
    customer.wait_value("fetch('/api/support/conversation').then(r=>r.json()).then(d=>d.conversation.status === 'closed')")
    customer.send_customer("I have one more question about the same piece.")
    staff.wait("document.querySelector('#support-thread-status').textContent.toLowerCase().includes('open')", timeout=20)
    staff.check(True, "A customer's new message reopens a closed conversation")

    customer.connection.call("Network.setBlockedURLs", {"urls": ["*/api/support/messages"]})
    try:
        customer.input("#support-message", "Keep this message when sending is temporarily unavailable.")
        customer.submit("#support-form")
        customer.wait("document.querySelector('#support-error').textContent.trim().length > 0 && !document.querySelector('#support-send').disabled")
        customer.check(customer.evaluate("document.querySelector('#support-message').value === 'Keep this message when sending is temporarily unavailable.'"), "A failed send reports an error and preserves the draft")
    finally:
        customer.connection.call("Network.setBlockedURLs", {"urls": []})
    customer.submit("#support-form")
    customer.wait("document.querySelector('#support-message').value === ''")
    customer.check(sum(message["body"] == "Keep this message when sending is temporarily unavailable." for message in customer.conversation()["messages"]) == 1, "Retry saves exactly one copy of the recovered customer message")

    for width in (320, 390, 768, 1366):
        customer.viewport(width, 844 if width < 500 else 900)
        bounds = customer.evaluate("(() => {const d=document.querySelector('#support-chat'),r=d.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,scroll:d.scrollWidth,client:d.clientWidth};})()")
        customer.check(bounds["left"] >= -1 and bounds["right"] <= width + 1 and bounds["scroll"] <= bounds["client"] + 1 and bounds["top"] >= -1, f"Customer chat fits at {width}px")
        staff.viewport(width, 844 if width < 500 else 900)
        staff.check(staff.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), f"Staff support inbox fits at {width}px")
    customer.screenshot_at("support-chat-mobile.png", 390, 844)
    customer.screenshot_at("support-chat-desktop.png", 1366, 900)
    staff.screenshot_at("support-inbox-desktop.png", 1366, 950)
    staff.screenshot_at("support-inbox-mobile.png", 390, 844, "#admin-support")

    customer.focus_click("#support-delete")
    customer.wait("document.querySelector('#support-delete-dialog').open")
    customer.focus_click("#support-delete-cancel")
    customer.check(customer.conversation()["conversation"]["id"] == thread_id, "Cancelling chat deletion retains the conversation")
    customer.focus_click("#support-delete")
    customer.focus_click("#support-delete-confirm")
    customer.wait("!document.querySelector('#support-delete-dialog').open && !document.querySelector('#support-messages .support-message')")
    customer.check(customer.conversation()["conversation"] is None, "Deleting chat removes the guest conversation and messages")

    customer.login(account_email, password)
    customer.wait("document.querySelector('#support-launcher')")
    customer.open_chat()
    account = customer.support_session()
    customer.check(not account["customer"]["guest"] and account["customer"]["name"] == "Support Customer" and customer.evaluate("document.querySelector('#support-guest-fields').hidden"), "Signed-in chat uses the real account name without a guest name field")
    customer.check(account["conversation"] is None, "Signing in does not merge the guest conversation into the account")
    customer.send_customer("This is a private message from the signed-in customer.")
    account_thread = customer.conversation()["conversation"]["id"]
    staff.wait(f"document.querySelector('#support-conversations [data-conversation-id=\"{account_thread}\"]')", timeout=20)
    staff.focus_click(f'#support-conversations [data-conversation-id="{account_thread}"]')
    staff.wait("document.querySelector('#support-thread-name').textContent.includes('Support Customer')")
    staff.check(True, "Staff receive the account conversation with its account-derived customer name")
    staff.send_staff("Thanks for signing in. We can continue helping you here.")
    customer.wait("document.querySelector('#support-messages').textContent.includes('Thanks for signing in.')", timeout=20)
    customer.check(True, "Signed-in customers receive live staff replies")
    customer.navigate("contact.html", ready="document.querySelector('#support-launcher')")
    customer.open_chat()
    customer.wait("document.querySelector('#support-messages').textContent.includes('This is a private message from the signed-in customer.')")
    customer.check(True, "Account chat history persists across page navigation")

    # Larger saved histories should load recent messages first, with an earlier
    # page available on demand rather than losing the beginning of the thread.
    with app.connect() as connection:
        customer_id = connection.execute("SELECT id FROM users WHERE email=?", (account_email,)).fetchone()[0]
        for number in range(55):
            latest = connection.execute("INSERT INTO support_messages(conversation_id,sender,sender_key,author_id,body,client_id,created_at) VALUES(?,'customer',?,?,?,?,?)", (account_thread, f"user:{customer_id}", customer_id, f"Disposable support history fixture {number:02d}", secrets.token_hex(16), "2026-11-04T09:00:00Z")).lastrowid
        connection.execute("UPDATE support_conversations SET last_message_id=?,updated_at=? WHERE id=?", (latest, "2026-11-04T09:00:00Z", account_thread))
    customer.navigate("contact.html", ready="document.querySelector('#support-launcher')")
    customer.open_chat()
    customer.wait("document.querySelectorAll('#support-messages .support-message').length === 50 && !document.querySelector('#support-older').hidden")
    customer.check(True, "Large conversations initially load the newest fifty messages")
    customer.focus_click("#support-older")
    customer.wait("document.querySelectorAll('#support-messages .support-message').length === 57 && document.querySelector('#support-older').hidden")
    customer.check(customer.evaluate("document.querySelector('#support-messages').textContent.includes('This is a private message from the signed-in customer.')"), "Loading earlier messages restores the complete saved conversation")

    protected_draft = "This account draft must never be sent as a guest after sign-out."
    customer.input("#support-message", protected_draft)
    with app.connect() as connection:
        connection.execute("DELETE FROM sessions WHERE user_id=?", (customer_id,))
    customer.submit("#support-form")
    customer.wait("!document.querySelector('#support-guest-fields').hidden && !document.querySelector('#support-messages').textContent.includes('This is a private message from the signed-in customer.')")
    with app.connect() as connection:
        published = connection.execute("SELECT COUNT(*) FROM support_messages WHERE body=?", (protected_draft,)).fetchone()[0]
    customer.check(published == 0 and customer.support_session()["customer"]["guest"], "An expired account session clears private history and does not send the account draft as a guest")
    customer.check(customer.evaluate("window.__supportErrors.length === 0"), "Customer support flows produce no uncaught JavaScript errors")
    staff.check(staff.evaluate("window.__supportErrors.length === 0"), "Staff support flows produce no uncaught JavaScript errors")
    customer.no_credentials_in_storage(account_email, admin_email, password)


def main():
    (ROOT / "tmp").mkdir(exist_ok=True)
    spec = importlib.util.spec_from_file_location("velora_support_browser_server", ROOT / "server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.VeloraHandler.log_message = lambda *args: None
    with tempfile.TemporaryDirectory(prefix="support-browser-", dir=ROOT / "tmp", ignore_cleanup_errors=True) as directory:
        temporary = Path(directory)
        app = module.make_server(host="127.0.0.1", port=0, database=temporary / "accounts.sqlite3", catalog=ROOT / "product-catalog.json", root=ROOT)
        password = secrets.token_urlsafe(24)
        admin_email = "support-admin-" + secrets.token_hex(5) + "@example.test"
        account_email = "support-customer-" + secrets.token_hex(5) + "@example.test"
        password_hash = module.hash_password(password)
        with app.connect() as connection:
            connection.execute("INSERT INTO users(name,first_name,last_name,email,password_hash,role,created_at) VALUES(?,?,?,?,?,'admin',?)", ("Support Staff", "Support", "Staff", admin_email, password_hash, module.now_iso()))
            connection.execute("INSERT INTO users(name,first_name,last_name,email,password_hash,role,created_at) VALUES(?,?,?,?,?,'customer',?)", ("Support Customer", "Support", "Customer", account_email, password_hash, module.now_iso()))
        thread = threading.Thread(target=app.serve_forever, daemon=True)
        thread.start()
        browsers, connections, checks = [], [], []
        try:
            for label in ("customer", "staff"):
                browser, connection = start_chrome(temporary / (label + "-profile"))
                browsers.append(browser)
                connections.append(connection)
                connection.call("Page.enable")
                # Each profile represents a separate customer/staff device.
                connection.call("Emulation.setFocusEmulationEnabled", {"enabled": True})
                connection.call("Page.addScriptToEvaluateOnNewDocument", {"source": "window.__supportErrors=[];window.addEventListener('error',e=>window.__supportErrors.push(e.message));window.addEventListener('unhandledrejection',()=>window.__supportErrors.push('unhandled rejection'));"})
                checks.append(SupportChecks(connection, f"http://127.0.0.1:{app.server_port}"))
            scenarios(checks[0], checks[1], app, account_email, admin_email, password)
            passed = checks[0].passed + checks[1].passed
            report = f"PASS: {len(passed)} live support browser checks\n" + "\n".join(passed) + "\n"
            (ROOT / "tmp/support-browser-results.txt").write_text(report, encoding="utf-8")
            print(report.splitlines()[0])
        except BaseException as error:
            passed = [description for check in checks for description in check.passed]
            report = f"FAIL: {type(error).__name__}: {error}\nCompleted checks: {len(passed)}\n"
            (ROOT / "tmp/support-browser-results.txt").write_text(report, encoding="utf-8")
            print(report)
            for label, check in zip(("customer", "staff"), checks):
                print(label, check.evaluate("({path:location.pathname,chat:document.querySelector('#support-chat')?.open,status:document.querySelector('#support-status')?.textContent,error:document.querySelector('#support-error')?.textContent,inbox:document.querySelector('#support-inbox-state')?.textContent,reply:document.querySelector('#support-reply-message')?.textContent,errors:window.__supportErrors})"))
                check.screenshot_at("support-failure-" + label + ".png", 390, 844)
            raise
        finally:
            for connection in connections:
                connection.socket.close()
            for browser in browsers:
                browser.terminate()
                browser.wait(timeout=10)
            app.shutdown()
            app.server_close()
            thread.join(timeout=10)


if __name__ == "__main__":
    main()
