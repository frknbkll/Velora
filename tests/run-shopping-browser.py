"""Exercise collection filters, product advice and zoom with disposable data.

Run ``python tests/run-shopping-browser.py``. No live accounts are opened.
"""

from __future__ import annotations

import importlib.util
import base64
import json
from pathlib import Path
import runpy
import tempfile
import threading


ROOT = Path(__file__).resolve().parent.parent
helpers = runpy.run_path(str(ROOT / "tests" / "run-account-browser.py"))
Checks = helpers["Checks"]
start_chrome = helpers["start_chrome"]


class ShoppingChecks(Checks):
    def screenshot_at(self, filename, width, height, selector):
        self.viewport(width, height)
        self.evaluate(f"document.querySelector({json.dumps(selector)}).scrollIntoView({{block:'start',behavior:'instant'}})")
        self.evaluate("new Promise(resolve => setTimeout(resolve, 600))")
        screenshot = self.connection.call('Page.captureScreenshot', {'format': 'png', 'captureBeyondViewport': False})
        (ROOT / 'tmp' / filename).write_bytes(base64.b64decode(screenshot['data']))

    def choose(self, key, value):
        self.evaluate(f"""(() => {{
            const input = document.querySelector('#collection-' + {json.dumps(key)});
            input.value = {json.dumps(value)};
            input.dispatchEvent(new Event({json.dumps('input' if key == 'search' else 'change')}, {{bubbles:true}}));
        }})()""")

    def escape(self):
        for kind in ("keyDown", "keyUp"):
            self.connection.call("Input.dispatchKeyEvent", {"type": kind, "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27})


def scenarios(checks):
    checks.navigate("index.html", ready="window.veloraCatalogReady && document.documentElement.dataset.catalogState === 'managed'")
    checks.evaluate("document.querySelector('#privacy-banner [data-privacy-choice=\"necessary\"]')?.click()")
    checks.click('#collection-refinements > summary')
    checks.check(checks.evaluate("document.querySelector('#collection-refinements').open"), "Advanced filters open on request")
    checks.check(checks.evaluate("document.querySelectorAll('#collection-color option').length > 2 && document.querySelectorAll('#collection-size option').length > 2"), "Catalog supplies color and size filter choices")
    checks.choose("size", "XS")
    checks.choose("color", "Ivory")
    checks.choose("price", "100-200")
    checks.choose("occasion", "everyday")
    checks.choose("search", "The Ivory Linen Set")
    checks.check(checks.evaluate("document.querySelectorAll('.look-tile').length === 1 && document.querySelector('.look-tile-caption strong').textContent === 'The Ivory Linen Set'"), "Size, color, price, occasion and search combine to find the intended piece")
    checks.check(checks.evaluate("document.querySelector('.look-tile .product-size-option[aria-pressed=true]').textContent === 'XS' && document.querySelector('.look-tile .product-color-option[aria-pressed=true]').dataset.optionValue === 'Ivory'"), "Matched size and color carry into product selections")
    checks.check(checks.evaluate("document.querySelector('#refinement-count').textContent === '5 active' && document.querySelector('#collection-filter-status').textContent.includes('1 of 1')"), "Active filters and result count are announced")
    checks.evaluate("document.querySelector('.look-tile-image').scrollIntoView({block:'center',behavior:'instant'})")
    checks.wait("document.querySelector('.look-photo-trigger img').complete && document.querySelector('.look-photo-trigger img').naturalWidth > 0")
    checks.check(checks.evaluate("document.querySelector('.look-photo-trigger img').srcset.includes('assets/responsive/')"), "Product cards offer real responsive image candidates")
    checks.choose("search", "No matching garment 4728")
    checks.check(checks.evaluate("document.querySelectorAll('.look-tile').length === 0 && !!document.querySelector('.collection-empty button') && document.querySelector('#show-more-looks').hidden"), "An empty result has an accessible reset action")
    checks.click(".collection-empty button")
    checks.check(checks.evaluate("document.querySelectorAll('.look-tile').length === 15 && document.querySelector('#collection-search').value === '' && document.activeElement.id === 'collection-search'"), "Reset restores collection and keyboard focus")
    checks.choose("price", "under-100")
    checks.check(checks.evaluate("[...document.querySelectorAll('.look-tile > .product-price')].every(p => Number(p.textContent.replace(/[^0-9.]/g,'')) < 100) && document.querySelectorAll('.look-tile').length > 0"), "Under-100 price filter excludes higher priced pieces")
    checks.choose("price", "all")
    checks.choose("sort", "price-asc")
    checks.check(checks.evaluate("(() => { const prices=[...document.querySelectorAll('.look-tile > .product-price')].map(p=>Number(p.textContent.replace(/[^0-9.]/g,''))); return prices.every((p,i)=>!i || p>=prices[i-1]); })()"), "Ascending price order is reflected in visible products")
    checks.click('#show-more-looks')
    checks.check(checks.evaluate("document.querySelectorAll('.look-tile').length === 30"), "Pagination continues to work with sorting")
    checks.click('#clear-collection-filters')
    checks.click('.look-filter[data-category="THE TAILORED EDIT"]')
    checks.choose('occasion', 'everyday')
    checks.check(checks.evaluate("!!document.querySelector('.collection-empty')"), "Existing category and new occasion filters intersect")
    checks.click('#clear-collection-filters')
    checks.check(checks.evaluate("document.querySelector('.look-filter[data-category=all]').getAttribute('aria-pressed') === 'true'"), "Clear resets the existing category buttons too")

    for width in (320, 390, 768, 1366):
        checks.viewport(width)
        checks.evaluate("document.querySelector('#collection-refinements').scrollIntoView({block:'start'})")
        checks.check(checks.evaluate("document.documentElement.scrollWidth <= innerWidth + 1 && [...document.querySelectorAll('.refinement-fields input,.refinement-fields select')].every(n=>n.getBoundingClientRect().width <= document.querySelector('.refinement-fields').clientWidth)"), f"Filters fit at {width}px")
        checks.check(checks.evaluate("[...document.querySelectorAll('.look-tile .product-size-option,.look-tile .product-color-option')].every(n=>n.getBoundingClientRect().width >= 44 && n.getBoundingClientRect().height >= 44)"), f"Size and color touch targets are at least 44px at {width}px")
    checks.screenshot_at('shopping-filters-desktop.png', 1366, 900, '#collection-refinements')
    checks.screenshot_at('shopping-filters-mobile.png', 390, 844, '#collection-refinements')
    checks.choose('search', 'The Ivory Linen Set')
    checks.click('.look-tile .product-size-help')
    checks.check(checks.evaluate("document.querySelector('#product-dialog').open && document.querySelector('[data-size-fit]').open && document.querySelector('[data-size-fit]').textContent.includes('measure around')"), "Size help opens product-specific fit advice and measuring instructions")
    checks.check(checks.evaluate("document.querySelector('.product-information').textContent.includes('Fabric weight') && document.querySelector('.product-information').textContent.includes('Not supplied yet')"), "Specifications identify missing product facts explicitly")
    checks.check(checks.evaluate("document.querySelector('.product-information a[href=\"refund-policy.html\"]') !== null"), "Return information is available from product details")
    for width in (320, 390, 768, 1366):
        checks.viewport(width)
        checks.check(checks.evaluate("(() => {const d=document.querySelector('#product-dialog'),r=d.getBoundingClientRect();return r.left>=-1 && r.right<=innerWidth+1 && d.scrollWidth<=d.clientWidth+1;})()"), f"Product advice dialog fits at {width}px")
    checks.screenshot('shopping-product-mobile.png', 390, 844)
    checks.click('.product-zoom-open')
    checks.wait("document.querySelector('.image-zoom-image').complete && document.querySelector('.image-zoom-image').naturalWidth > 0")
    checks.check(checks.evaluate("document.querySelector('#image-zoom-dialog').open && document.querySelector('.image-zoom-image').getAttribute('src').startsWith('assets/gallery/')"), "Zoom loads the original photograph")
    checks.click('.image-zoom-toggle')
    checks.check(checks.evaluate("document.querySelector('.image-zoom-toggle').getAttribute('aria-pressed') === 'true' && document.querySelector('.image-zoom-viewport').scrollWidth > document.querySelector('.image-zoom-viewport').clientWidth"), "Enlarged photograph can be panned horizontally")
    checks.screenshot('shopping-zoom-mobile.png', 390, 844)
    checks.escape()
    checks.wait("!document.querySelector('#image-zoom-dialog').open")
    checks.wait("document.activeElement.classList.contains('product-zoom-open')")
    checks.check(checks.evaluate("!document.querySelector('#image-zoom-dialog').open && document.querySelector('#product-dialog').open && document.activeElement.classList.contains('product-zoom-open')"), "Escape closes only photo zoom and restores focus")
    checks.click('.product-dialog-close')
    checks.click('.look-tile .add-to-bag')
    checks.click('.header-shop-actions [data-shop-view=cart]')
    checks.check(checks.evaluate("document.querySelector('#shop-dialog').open && !!document.querySelector('#shop-dialog-footer a[href=\"refund-policy.html\"]')"), "Preview bag exposes return and shopping help")
    checks.check(checks.evaluate("window.__shoppingErrors.length === 0"), "Shopping interactions produce no uncaught JavaScript errors")


def main():
    (ROOT / 'tmp').mkdir(exist_ok=True)
    spec = importlib.util.spec_from_file_location('velora_shopping_test_server', ROOT / 'server.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.VeloraHandler.log_message = lambda *args: None
    with tempfile.TemporaryDirectory(prefix='shopping-browser-', dir=ROOT / 'tmp', ignore_cleanup_errors=True) as directory:
        temporary = Path(directory)
        app = module.make_server(host='127.0.0.1', port=0, database=temporary / 'accounts.sqlite3', catalog=ROOT / 'product-catalog.json', root=ROOT)
        thread = threading.Thread(target=app.serve_forever, daemon=True)
        thread.start()
        browser = connection = checks = None
        try:
            browser, connection = start_chrome(temporary / 'chrome-profile')
            connection.call('Page.enable')
            connection.call('Page.addScriptToEvaluateOnNewDocument', {'source': "window.__shoppingErrors=[]; window.addEventListener('error', e=>window.__shoppingErrors.push(e.message)); window.addEventListener('unhandledrejection', ()=>window.__shoppingErrors.push('unhandled rejection'));"})
            checks = ShoppingChecks(connection, f'http://127.0.0.1:{app.server_port}')
            scenarios(checks)
            report = f'PASS: {len(checks.passed)} shopping browser checks\n' + '\n'.join(checks.passed) + '\n'
            (ROOT / 'tmp/shopping-browser-results.txt').write_text(report, encoding='utf-8')
            print(report.splitlines()[0])
        except BaseException as error:
            if checks:
                print('Dialog state:', checks.evaluate("({zoom:document.querySelector('#image-zoom-dialog')?.open,product:document.querySelector('#product-dialog')?.open,active:document.activeElement?.outerHTML.slice(0,300),errors:window.__shoppingErrors})"))
                print('Product photo:', checks.evaluate("(()=>{const i=document.querySelector('.look-photo-trigger img');return {scrollY,src:i?.src,current:i?.currentSrc,complete:i?.complete,natural:i?.naturalWidth,loading:i?.loading,rect:i?.getBoundingClientRect().toJSON()}})()"))
            report = f'FAIL: {type(error).__name__}: {error}\nCompleted checks: {len(checks.passed) if checks else 0}\n'
            (ROOT / 'tmp/shopping-browser-results.txt').write_text(report, encoding='utf-8')
            print(report)
            if checks:
                checks.screenshot('shopping-failure.png', 390, 844)
            raise
        finally:
            if connection:
                connection.socket.close()
            if browser:
                browser.terminate()
                browser.wait(timeout=10)
            app.shutdown()
            app.server_close()
            thread.join(timeout=5)


if __name__ == '__main__':
    main()
