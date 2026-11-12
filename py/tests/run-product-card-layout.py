"""Check live product photo geometry, color previews and links on desktop/mobile.

Run with Velora listening on http://127.0.0.1:8000.
Requires local Chrome, using an isolated headless profile.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

import runpy,subprocess,socket,time,json,urllib.request,base64
from pathlib import Path
root=ROOT; BrowserConnection=runpy.run_path(str(root/'py/tests/run-product-colors.py'))['BrowserConnection']
with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
profile=root/'tmp/product-card-layout-check';profile.mkdir(parents=True,exist_ok=True)
p=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe','--headless','--disable-gpu','--no-first-run',f'--remote-debugging-port={port}',f'--user-data-dir={profile}','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
c=None
try:
 for _ in range(100):
  try:
   with urllib.request.urlopen(f'http://127.0.0.1:{port}/json',timeout=1) as r:page=next(x for x in json.load(r) if x['type']=='page')
   break
  except (OSError,StopIteration):time.sleep(.1)
 if 'page' not in locals():raise RuntimeError('Chrome did not start its local debugging endpoint')
 c=BrowserConnection(page['webSocketDebuggerUrl'])
 c.call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
 c.call('Page.navigate',{'url':'http://127.0.0.1:8000/index.html'})
 def ev(expr):
  res=c.call('Runtime.evaluate',{'expression':expr,'returnByValue':True,'awaitPromise':True})
  if 'exceptionDetails' in res:raise RuntimeError(res['exceptionDetails'])
  return res.get('result',{}).get('value')
 for _ in range(100):
  if ev('document.documentElement?.dataset.catalogState === "managed"'):break
  time.sleep(.1)
 report=ev('''(async()=>{
 visibleLookCount=1000;renderLooks();
 const cards=[...document.querySelectorAll('.look-tile')].filter(c=>c.querySelector('.has-photo-previews'));
 if(!cards.length||cards.length!==document.querySelectorAll('.look-tile').length)throw Error('A product card is missing photo selectors');
 await Promise.all(cards.map(card=>{const im=card.querySelector('.look-tile-image img');im.loading='eager';return im.decode()}));
 for(const card of cards){
  const im=card.querySelector('.look-tile-image img'), frame=card.querySelector('.look-tile-image');
  const box=im.getBoundingClientRect(), fbox=frame.getBoundingClientRect();
  if(box.height<50||fbox.height<50)throw Error('Collapsed product photo: '+card.dataset.productId+' image='+box.height+' frame='+fbox.height);
  if(Math.abs(box.width-fbox.width)>1)throw Error('Photo has side gaps');
  if(Math.abs(box.height-fbox.height)>1)throw Error('Photo does not fill its frame');
  if(Math.abs(fbox.height-cards[0].querySelector('.look-tile-image').getBoundingClientRect().height)>1)throw Error('Product photo heights do not match');
  if(getComputedStyle(im).objectFit!=='cover')throw Error('Photo does not fill edge to edge');
  const options=[...card.querySelectorAll('.product-color-preview')];
  if(options.length<1)throw Error('Missing photo variant'); if(options.length<2)continue;
  const main=card.querySelector('.look-tile-image img');
  const original=main.dataset.originalSrc;
  options[1].click();
  if(Math.abs(frame.getBoundingClientRect().height-fbox.height)>1)throw Error('Color selection changed the photo height');
  if(!main.dataset.originalSrc)throw Error('Missing selected image');
  if(options[1].getAttribute('aria-pressed')!=='true')throw Error('Color not selected');
  const chosen=options[1].dataset.optionValue;
  if(new URL(card.querySelector('.look-quick-view').href).searchParams.get('color')!==chosen)throw Error('Product link lost selected color');
  options[0].click();
 }
 const images=cards.flatMap(c=>[...c.querySelectorAll('.product-color-preview img')]);
 await Promise.all(images.map(im=>{im.loading='eager';return im.decode()}));
 return {products:cards.length,photoVariants:images.length,selectionAndLinks:'passed'};
})()''')
 print(json.dumps(report))
 ev("[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Necessary only')?.click(); document.querySelector('.has-photo-previews').scrollIntoView({block:'center'})")
 time.sleep(.4)
 (root/'tmp/homepage-variants-desktop.png').write_bytes(base64.b64decode(c.call('Page.captureScreenshot',{'format':'png'})['data']))
 c.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
 ev("document.querySelector('.has-photo-previews').scrollIntoView({block:'center'})")
 time.sleep(.3)
 assert ev("[...document.querySelectorAll('.look-tile-image')].every(f=>f.getBoundingClientRect().height>50)"),'Mobile product image frame collapsed'
 assert ev("(()=>{const frames=[...document.querySelectorAll('.look-tile-image')];const height=frames[0].getBoundingClientRect().height;return frames.every(f=>Math.abs(f.getBoundingClientRect().height-height)<1)})()"),'Mobile product image heights differ'
 assert ev('document.documentElement.scrollWidth<=innerWidth'),'Mobile horizontal overflow'
 (root/'tmp/homepage-variants-mobile.png').write_bytes(base64.b64decode(c.call('Page.captureScreenshot',{'format':'png'})['data']))
 print('Mobile layout: no horizontal overflow.')
finally:
 if c:c.socket.close()
 p.terminate();p.wait(timeout=10)
