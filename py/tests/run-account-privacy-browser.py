
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

from pathlib import Path
import importlib.util
import runpy
import secrets
import sys
import tempfile
import threading
import time

import server
import security_core
helpers = runpy.run_path(str(ROOT / 'py/tests/run-account-browser.py'))
Checks, start_chrome = helpers['Checks'], helpers['start_chrome']

server.VeloraHandler.log_message = lambda *args: None
password = secrets.token_urlsafe(24)
owner_email = 'qa-owner@example.test'
with tempfile.TemporaryDirectory(prefix='account-privacy-', dir=ROOT / 'tmp', ignore_cleanup_errors=True) as temporary:
    temporary = Path(temporary)
    app = server.make_server(port=0, database=temporary / 'accounts.sqlite3', catalog=ROOT / 'json/catalog/product-catalog.json', root=ROOT)
    with app.connect() as db:
        db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,'admin',?)", ('QA owner', owner_email, server.hash_password(password), server.now_iso()))
    thread = threading.Thread(target=app.serve_forever, daemon=True)
    thread.start()
    browser = connection = None
    try:
        browser, connection = start_chrome(temporary / 'chrome')
        checks = Checks(connection, f'http://127.0.0.1:{app.server_port}')
        def register(email):
            checks.navigate('register.html', ready="window.VeloraAuth && document.querySelector('#register-form')")
            checks.fill('#register-form', {
                'firstName':'QA', 'lastName':'Member', 'city':'Amsterdam', 'country':'Netherlands',
                'email':email, 'password':password, 'confirmPassword':password, 'terms':True, 'ageConfirmed':False,
            })
            checks.check(not checks.evaluate("document.querySelector('#register-form').checkValidity()"), 'Age confirmation is required')
            checks.fill('#register-form', {'ageConfirmed':True})
            checks.check(checks.evaluate("document.querySelector('#register-form').checkValidity()"), 'Registration is ready with the required customer profile details')
            checks.submit('#register-form')
            checks.wait("location.pathname === '/account.html' && !document.querySelector('#account-content').hidden")
            checks.check(checks.evaluate("document.querySelector('#account-name').textContent")=='QA Member', 'Customer profile name is saved at registration')
        def open_delete():
            checks.click('#privacy-delete-open')
            checks.wait("document.querySelector('#account-delete-dialog').open")
            checks.check(checks.evaluate("document.activeElement.id")=='account-delete-cancel', 'Deletion initially focuses Cancel')
        def confirm_deleted():
            checks.wait("location.pathname === '/login.html' && location.search === '?deleted=1' && document.querySelector('#auth-message').textContent.includes('deleted')")
            checks.check(checks.evaluate("document.querySelector('#auth-message').classList.contains('is-success')"), 'Successful deletion is confirmed on sign in page')
            checks.check(checks.evaluate("window.VeloraAuth.user") is None, 'Account deletion ends authentication')
        register('qa-member@example.test')
        checks.evaluate("localStorage.setItem('velora-shopping-v1','{}')")
        checks.click('#privacy-clear-device')
        checks.wait("document.querySelector('#privacy-message').textContent.includes('cleared')")
        checks.check(checks.evaluate("localStorage.getItem('velora-shopping-v1')") is None, 'Clear device data removes saved shopping data')
        checks.check(checks.evaluate("Boolean(window.VeloraAuth.user)"), 'Clear device data leaves account signed in')
        open_delete()
        checks.check(checks.evaluate("document.querySelector('#account-delete-factor').hidden"), 'Password-only account does not ask for a factor code')
        connection.call('Input.dispatchKeyEvent', {'type':'keyDown','key':'Escape','code':'Escape','windowsVirtualKeyCode':27})
        checks.wait("!document.querySelector('#account-delete-dialog').open")
        checks.check(checks.evaluate("document.activeElement.id")=='privacy-delete-open', 'Escape restores focus to the delete action')
        open_delete()
        checks.fill('#account-delete-form', {'password':'incorrect password'})
        checks.submit('#account-delete-form')
        checks.wait("document.querySelector('#account-delete-message').textContent.length > 0 && !document.querySelector('#account-delete-confirm').disabled")
        checks.check(checks.evaluate("location.pathname === '/account.html' && Boolean(window.VeloraAuth.user)"), 'Wrong password leaves account and dialog available')
        checks.check(checks.evaluate("document.querySelector('#account-delete-password').value === ''"), 'Failed deletion clears the password')
        for width in (320,390,768,1366,1920):
            checks.viewport(width)
            checks.check(checks.evaluate("document.documentElement.scrollWidth<=innerWidth+1 && document.querySelector('#account-delete-dialog').getBoundingClientRect().width<=innerWidth"), f'Deletion dialog fits at {width}px')
        checks.fill('#account-delete-form', {'password':password})
        checks.submit('#account-delete-form')
        confirm_deleted()
        with app.connect() as db:
            checks.check(db.execute("SELECT COUNT(*) FROM users WHERE email='qa-member@example.test'").fetchone()[0]==0, 'Deleted customer is removed from SQLite')
        register('qa-mfa@example.test')
        setup = checks.evaluate(f"window.VeloraAuth.request('/api/security/mfa/setup',{{method:'POST',body:{{password:{password!r}}}}})")
        code = security_core.totp(setup['secret'])
        enabled = checks.evaluate(f"window.VeloraAuth.request('/api/security/mfa/enable',{{method:'POST',body:{{code:{code!r}}}}})")
        open_delete()
        checks.check(checks.evaluate("!document.querySelector('#account-delete-factor').hidden && document.querySelector('#account-delete-code').required"), 'MFA account must provide a fresh factor')
        checks.fill('#account-delete-form', {'password':password,'code':enabled['recoveryCodes'][0]})
        checks.submit('#account-delete-form')
        confirm_deleted()
        checks.fill('#login-form', {'email':owner_email,'password':password})
        checks.submit('#login-form')
        checks.wait("location.pathname === '/admin.html' && window.VeloraAuth.user?.role === 'admin'")
        checks.navigate('account.html', ready="!document.querySelector('#account-content').hidden")
        open_delete()
        checks.fill('#account-delete-form', {'password':password})
        checks.submit('#account-delete-form')
        checks.wait("document.querySelector('#account-delete-message').textContent.length > 0 && !document.querySelector('#account-delete-confirm').disabled")
        checks.check(checks.evaluate("/administrator/i.test(document.querySelector('#account-delete-message').textContent)"), 'Last administrator receives an actionable protection message')
        with app.connect() as db:
            checks.check(db.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0]==1, 'Last administrator remains available')
        checks.click('#account-delete-cancel')
        print(f'PASS: {len(checks.passed)} account privacy browser checks')
        (ROOT / 'tmp/account-privacy-browser-results.txt').write_text('\n'.join(checks.passed), encoding='utf-8')
    finally:
        if connection: connection.socket.close()
        if browser:
            browser.terminate()
            browser.wait(timeout=10)
        app.shutdown()
        app.server_close()
        thread.join(timeout=10)
