from pathlib import Path
import base64
import json
import runpy
import secrets
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import server
helpers=runpy.run_path(str(ROOT/'tests/run-account-browser.py'))
Checks,start_chrome=helpers['Checks'],helpers['start_chrome']
server.VeloraHandler.log_message=lambda *args:None
password=secrets.token_urlsafe(24)
with tempfile.TemporaryDirectory(prefix='admin-business-',dir=ROOT/'tmp',ignore_cleanup_errors=True) as temporary:
    temporary=Path(temporary)
    app=server.make_server(port=0,database=temporary/'accounts.sqlite3',catalog=ROOT/'product-catalog.json',root=ROOT)
    with app.connect() as db:
        db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,'admin',?)",('QA Owner','qa-owner@example.test',server.hash_password(password),server.now_iso()))
    thread=threading.Thread(target=app.serve_forever,daemon=True);thread.start()
    browser=connection=None
    try:
        browser,connection=start_chrome(temporary/'chrome')
        checks=Checks(connection,f'http://127.0.0.1:{app.server_port}')
        checks.navigate('login.html',ready="window.VeloraAuth && document.querySelector('#login-form')")
        checks.fill('#login-form',{'email':'qa-owner@example.test','password':password})
        checks.submit('#login-form')
        checks.wait("location.pathname === '/admin.html' && !document.querySelector('#admin-shell').hidden")
        checks.check(checks.evaluate("document.querySelector('#admin-business-form').hidden"),'Business data is loaded on demand')
        checks.click('[data-admin-section="business"]')
        checks.wait("!document.querySelector('#admin-business-form').hidden")
        checks.check(checks.evaluate("document.querySelector('#admin-breadcrumb').textContent")=='Business details','Business navigation and breadcrumb work')
        checks.check(checks.evaluate("Boolean(document.querySelector('#admin-business').compareDocumentPosition(document.querySelector('.admin-footer')) & Node.DOCUMENT_POSITION_FOLLOWING)"),'Studio footer follows the business editor')
        checks.check(checks.evaluate("Array.from(document.querySelectorAll('#admin-business-form input, #admin-business-form textarea')).every(x=>x.value===''&&!x.required)"),'Unknown business details are blank and optional')
        details={'legalName':'Studio QA BV','country':'Netherlands','registrationNumber':'QA-12345678','vatNumber':'','businessAddress':'Example 1\n1234 AA Example city\nNetherlands','customerServiceEmail':'studio@example.test','returnAddress':''}
        checks.fill('#admin-business-form',details)
        checks.check(checks.evaluate("!document.querySelector('#admin-business-discard').disabled"),'Editing enables draft discard')
        checks.submit('#admin-business-form')
        checks.wait("document.querySelector('#admin-business-message').classList.contains('is-success') && !document.querySelector('#admin-business-save').disabled")
        result=checks.evaluate("window.VeloraAuth.request('/api/business-details')")
        checks.check(result['businessDetails']==details,'Saved business details match public API')
        checks.check(checks.evaluate("document.querySelector('#admin-business-discard').disabled"),'Saved form has no pending draft changes')
        checks.fill('#admin-business-form',{'legalName':'Discard this draft'})
        checks.click('#admin-business-discard')
        checks.check(checks.evaluate("document.querySelector('#admin-business-legal-name').value")=='Studio QA BV','Discard restores saved details without publishing the draft')
        checks.fill('#admin-business-form',{'customerServiceEmail':'invalid address'})
        checks.check(not checks.evaluate("document.querySelector('#admin-business-form').checkValidity()"),'Malformed email is caught before submission')
        checks.click('#admin-business-discard')
        for width in (320,390,768,1366,1920):
            checks.viewport(width)
            checks.check(checks.evaluate("document.documentElement.scrollWidth<=innerWidth+1 && Array.from(document.querySelectorAll('#admin-business-form input,#admin-business-form textarea')).every(x=>x.getBoundingClientRect().width<=innerWidth)"),f'Business form fits at {width}px')
        checks.screenshot('admin-business-desktop.png',1366,900)
        checks.screenshot('admin-business-mobile.png',390,844)
        checks.navigate('admin.html#business',ready="!document.querySelector('#admin-business-form').hidden")
        checks.check(checks.evaluate("document.querySelector('#admin-business-legal-name').value")=='Studio QA BV','Business details persist across a page reload')
        checks.fill('#admin-business-form',dict.fromkeys(details,''))
        checks.submit('#admin-business-form')
        checks.wait("document.querySelector('#admin-business-message').classList.contains('is-success') && !document.querySelector('#admin-business-save').disabled")
        result=checks.evaluate("window.VeloraAuth.request('/api/business-details')")
        checks.check(all(v==''for v in result['businessDetails'].values()),'Clearing optional fields removes them from public details')
        print(f'PASS: {len(checks.passed)} admin business browser checks')
        (ROOT/'tmp/admin-business-browser-results.txt').write_text('\n'.join(checks.passed),encoding='utf-8')
    finally:
        if connection:connection.socket.close()
        if browser:browser.terminate();browser.wait(timeout=10)
        app.shutdown();app.server_close();thread.join(timeout=10)
