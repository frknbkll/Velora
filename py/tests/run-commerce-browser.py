
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

from pathlib import Path
import base64
import json
import runpy
import secrets
import sys
import tempfile
import threading

import server
helpers=runpy.run_path(str(ROOT/'py/tests/run-account-browser.py'))
Checks,start_chrome=helpers['Checks'],helpers['start_chrome']
server.VeloraHandler.log_message=lambda *args:None
password=secrets.token_urlsafe(24)
with tempfile.TemporaryDirectory(prefix='admin-business-',dir=ROOT/'tmp',ignore_cleanup_errors=True) as temporary:
    temporary=Path(temporary)
    app=server.make_server(port=0,database=temporary/'accounts.sqlite3',catalog=ROOT/'json/catalog/product-catalog.json',root=ROOT)
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
        checks.evaluate("document.querySelector('#privacy-banner [data-privacy-choice=necessary]')?.click()")
        checks.click('[data-admin-section="operations"]')
        checks.wait("document.querySelector('#commerce-content form')")
        checks.check(checks.evaluate("['size','color'].every(name=>document.querySelector('#commerce-content form').elements[name].tagName==='SELECT')"),'Inventory options use product-specific dropdowns')
        checks.evaluate("(()=>{const f=document.querySelector('#commerce-content form');f.elements.product.selectedIndex=f.elements.product.options.length-1;f.elements.product.dispatchEvent(new Event('change',{bubbles:true}));})()")
        checks.check(checks.evaluate("window.VeloraAuth.request('/api/admin/commerce').then(data=>{const f=document.querySelector('#commerce-content form'),choices=data.variantOptions[f.elements.product.value];return JSON.stringify([...f.elements.color.options].map(o=>o.value))===JSON.stringify(choices.colors)&&JSON.stringify([...f.elements.size.options].map(o=>o.value))===JSON.stringify(choices.sizes)})"),'Changing the product refreshes sizes and photographed colors')
        checks.fill('#commerce-content form',{'size':'M','color':checks.evaluate("document.querySelector('#commerce-content form [name=color]').options[0].value"),'stock':'12','threshold':'3','target':'20'})
        checks.submit('#commerce-content form')
        checks.wait("document.querySelector('#commerce-message').textContent.includes('Saved')")
        checks.check(checks.evaluate("document.querySelector('#commerce-content').textContent.includes('Edit stock')"),'Variant saves and renders in matrix')
        checks.evaluate("[...document.querySelectorAll('#commerce-content button')].find(b=>b.textContent==='Edit stock').click()")
        checks.check(checks.evaluate("window.VeloraAuth.request('/api/admin/commerce').then(data=>{const f=document.querySelector('#commerce-content form'),v=data.variants[0];return f.elements.product.value===v.product&&f.elements.size.value===v.size&&f.elements.color.value===v.color&&f.elements.stock.value===String(v.stock)})"),'Editing stock selects the saved product options without losing its identity')
        checks.navigate('admin.html#operations',ready="document.querySelector('#commerce-content').textContent.includes('Edit stock')")
        checks.check(True,'Variant persists after reload')
        with app.connect() as db:
            state=json.loads(db.execute('SELECT data FROM commerce_state WHERE id=1').fetchone()[0])
            obsolete={**state['variants'][0],'id':'legacy-invalid-fixture','color':'Legacy typo','stock':4}
            state['variants'].append(obsolete)
            db.execute('UPDATE commerce_state SET data=? WHERE id=1',(json.dumps(state),))
            db.execute('UPDATE products SET stock=stock+4 WHERE id=?',(obsolete['product'],))
        checks.click('#commerce-refresh')
        checks.wait("document.querySelector('#commerce-content').textContent.includes('Clear invalid stock')")
        checks.check(checks.evaluate("document.querySelector('#commerce-content').textContent.includes('allocate verified stock') && [...document.querySelectorAll('#commerce-content button')].some(b=>b.textContent==='Clear invalid stock')"),'Legacy invalid rows remain visible with a deliberate repair action and allocation guidance')
        for name in ('Products','Orders','Returns','Customers','Analytics','Staff','Inventory'):
            checks.evaluate(f"Array.from(document.querySelectorAll('#commerce-tabs button')).find(b=>b.textContent==={json.dumps(name)}).click()")
            checks.check(checks.evaluate("document.querySelector('#commerce-content').children.length>0"),f'{name} tab renders')
            if name=='Staff':
                checks.check(checks.evaluate("Boolean(!document.querySelector('#commerce-content form') && document.querySelector('#commerce-content a[href=\"#folder-access\"]'))"),'Staff access routes to the single Velora Accounts editor')
        for width in (320,390,768,1366,1920):
            checks.viewport(width)
            checks.check(checks.evaluate("document.documentElement.scrollWidth<=innerWidth+1"),f'Operations fits at {width}px')
        checks.screenshot('admin-commerce-desktop.png',1366,900)
        checks.screenshot('admin-commerce-mobile.png',390,844)
        for label,width,height in [('desktop',1366,900),('mobile',390,844)]:
            checks.viewport(width,height);checks.evaluate("document.querySelector('#commerce-content form').scrollIntoView({block:'start',behavior:'instant'})")
            checks.evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
            shot=connection.call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
            (ROOT/'tmp'/f'inventory-options-{label}.png').write_bytes(base64.b64decode(shot['data']))
        print(f'PASS: {len(checks.passed)} commerce browser checks')
    finally:
        if connection:connection.socket.close()
        if browser:browser.terminate();browser.wait(timeout=10)
        app.shutdown();app.server_close();thread.join(timeout=10)
