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
        checks.click('[data-admin-section="operations"]')
        checks.wait("document.querySelector('#commerce-content form')")
        checks.fill('#commerce-content form',{'size':'M','color':'Original','stock':'12','threshold':'3','target':'20'})
        checks.submit('#commerce-content form')
        checks.wait("document.querySelector('#commerce-message').textContent.includes('Saved')")
        checks.check(checks.evaluate("document.querySelector('#commerce-content').textContent.includes('Edit stock')"),'Variant saves and renders in matrix')
        checks.navigate('admin.html#operations',ready="document.querySelector('#commerce-content').textContent.includes('Edit stock')")
        checks.check(True,'Variant persists after reload')
        for name in ('Products','Orders','Returns','Customers','Analytics','Staff','Inventory'):
            checks.evaluate(f"Array.from(document.querySelectorAll('#commerce-tabs button')).find(b=>b.textContent==={json.dumps(name)}).click()")
            checks.check(checks.evaluate("document.querySelector('#commerce-content').children.length>0"),f'{name} tab renders')
        for width in (320,390,768,1366,1920):
            checks.viewport(width)
            checks.check(checks.evaluate("document.documentElement.scrollWidth<=innerWidth+1"),f'Operations fits at {width}px')
        checks.screenshot('admin-commerce-desktop.png',1366,900)
        checks.screenshot('admin-commerce-mobile.png',390,844)
        print(f'PASS: {len(checks.passed)} commerce browser checks')
    finally:
        if connection:connection.socket.close()
        if browser:browser.terminate();browser.wait(timeout=10)
        app.shutdown();app.server_close();thread.join(timeout=10)
