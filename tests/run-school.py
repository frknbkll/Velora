"""Verify the local School page, studio exports, course previews and certificate flow."""
import runpy,subprocess,socket,time,json,urllib.request,base64,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
BrowserConnection=runpy.run_path(str(ROOT/'tests/run-product-colors.py'))['BrowserConnection']
with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
profile=ROOT/'tmp/school-browser-check';profile.mkdir(parents=True,exist_ok=True)
downloads=ROOT/'tmp/school-check-downloads';downloads.mkdir(parents=True,exist_ok=True)
for filename in ('my-school-test.svg','velora-school-completion-certificate.svg'):
 target=downloads/filename
 if target.exists():target.unlink()
process=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe','--headless','--disable-gpu','--no-first-run',f'--remote-debugging-port={port}',f'--user-data-dir={profile}','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
c=None
try:
 for _ in range(100):
  try:
   with urllib.request.urlopen(f'http://127.0.0.1:{port}/json',timeout=1) as r:page=next(p for p in json.load(r) if p['type']=='page')
   break
  except (OSError,StopIteration):time.sleep(.1)
 if 'page' not in locals():raise RuntimeError('Headless Chrome did not start')
 c=BrowserConnection(page['webSocketDebuggerUrl'])
 c.call('Network.enable');c.call('Network.setCacheDisabled',{'cacheDisabled':True})
 c.call('Browser.setDownloadBehavior',{'behavior':'allow','downloadPath':str(downloads)})
 def ev(expression):
  r=c.call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
  if 'exceptionDetails' in r:raise RuntimeError(r['exceptionDetails'])
  return r.get('result',{}).get('value')
 def navigate(url,ready):
  c.call('Page.navigate',{'url':url})
  for _ in range(100):
   if ev(ready):return
   time.sleep(.1)
  raise RuntimeError('Page not ready')
 def screenshot(name):
  (ROOT/'tmp'/name).write_bytes(base64.b64decode(c.call('Page.captureScreenshot',{'format':'png'})['data']))
 c.call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
 navigate('http://127.0.0.1:8000/velora-school.html',"document.querySelector('#school-garment')?.children.length>0")
 ev("document.documentElement.style.scrollBehavior='auto';[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Necessary only')?.click()")
 assert ev("document.documentElement.scrollWidth<=innerWidth"),'Desktop overflow'
 assert ev("document.querySelector('#school-create-certificate').disabled"),'Certificate enabled too early'
 assert ev("getComputedStyle(document.querySelector('#school-certificate-actions')).display==='none'"),'Certificate actions shown before completion'
 assert ev("new Set([...document.querySelectorAll('[data-school-color]')].map(b=>getComputedStyle(b).backgroundColor)).size===6"),'Palette colors missing'
 screenshot('school-desktop.png')
 ev("document.querySelector('[data-school-mode=sketch]').click()")
 for key,count in [('foundations',4),('collection',6),('portfolio',8)]:
  assert ev(f"document.querySelector('[data-school-course=\"{key}\"]').click();document.querySelector('#school-course-dialog').open && document.querySelectorAll('#school-dialog-modules li').length=={count}"),'Course dialog failed'
  ev("document.querySelector('#school-dialog-close').click()")
 ev("document.querySelector('#courses').scrollIntoView({block:'start'})");screenshot('school-courses-desktop.png')
 ev("document.querySelector('#school-design-name').value='W'.repeat(60);document.querySelector('#school-design-name').dispatchEvent(new Event('input',{bubbles:true}))")
 assert ev("document.querySelector('#school-sketch-label').getAttribute('textLength')==='408'"),'Long design title is not fitted'
 ev("document.querySelector('#school-design-name').value='My School Test';document.querySelector('#school-silhouette').value='jacket';document.querySelector('#school-silhouette').dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('[data-school-color-name=Sage]').click();document.querySelector('#school-texture').value='woven';document.querySelector('#school-texture').dispatchEvent(new Event('input',{bubbles:true}))")
 assert ev("document.querySelector('#school-garment path').getAttribute('fill')==='#a4ac95' && document.querySelector('#school-design-caption').textContent.includes('jacket')"),'Studio selection failed'
 ev("document.querySelector('#school-design-form').requestSubmit()")
 for _ in range(100):
  if (downloads/'my-school-test.svg').exists():break
  time.sleep(.1)
 ET.parse(downloads/'my-school-test.svg')
 ev("document.querySelectorAll('[data-school-lesson]').forEach(b=>{b.closest('details').open=true;b.click()});document.querySelector('[name=brief][value=trend]').checked=true;document.querySelector('[name=fabric][value=screen]').checked=true;document.querySelector('#school-quiz').requestSubmit()")
 assert ev("document.querySelector('#school-create-certificate').disabled"),'Incorrect quiz unlocked certificate'
 ev("document.querySelector('[name=brief][value=purpose]').checked=true;document.querySelector('[name=fabric][value=sample]').checked=true;document.querySelector('#school-quiz').requestSubmit()")
 assert ev("!document.querySelector('#school-create-certificate').disabled"),'Completion did not unlock certificate'
 ev("document.querySelector('#school-student-name').value='Amina & Design';document.querySelector('#school-certificate-form').requestSubmit()")
 assert ev("document.querySelector('#school-certificate-name').textContent==='Amina & Design' && !document.querySelector('#school-certificate-actions').hidden"),'Certificate missing name'
 ev("document.querySelector('#school-save-certificate').click()")
 for _ in range(100):
  if (downloads/'velora-school-completion-certificate.svg').exists():break
  time.sleep(.1)
 cert=ET.parse(downloads/'velora-school-completion-certificate.svg')
 assert 'Amina & Design' in ''.join(cert.getroot().itertext()),'Certificate download missing name'
 ev("document.querySelector('#certificate').scrollIntoView({block:'start'})")
 screenshot('school-certificate-desktop.png')
 c.call('Emulation.setEmulatedMedia',{'media':'print'})
 assert ev("getComputedStyle(document.querySelector('.school-header')).display==='none' && getComputedStyle(document.querySelector('.school-certificate-paper')).visibility==='visible'"),'Certificate print layout failed'
 c.call('Emulation.setEmulatedMedia',{'media':''})
 c.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
 ev('scrollTo(0,0)');time.sleep(.2)
 assert ev('document.documentElement.scrollWidth<=innerWidth'),'Mobile School overflow'
 screenshot('school-mobile.png')
 ev("document.querySelector('#design-studio').scrollIntoView({block:'start'})");screenshot('school-studio-mobile.png')
 ev("document.querySelector('[data-school-lesson]').click()")
 assert ev("document.querySelector('#school-create-certificate').disabled && document.querySelector('#school-certificate-actions').hidden"),'Undoing completion did not reset certificate'
 navigate('http://127.0.0.1:8000/index.html',"document.querySelector('.hero-school-link')!==null && getComputedStyle(document.querySelector('.hero-school-link')).display==='flex'")
 screenshot('school-homepage-cta-mobile.png')
 ev("document.documentElement.style.scrollBehavior='auto';scrollTo(0,0)")
 assert ev("(()=>{const a=document.querySelector('.hero-school-link'),b=document.querySelector('.hero-copy>.text-link'),hero=document.querySelector('.hero');return a.getBoundingClientRect().top>=b.getBoundingClientRect().bottom && a.getBoundingClientRect().bottom<=hero.getBoundingClientRect().bottom && a.getAttribute('href')==='velora-school.html'})()"),'Homepage School link placement failed'
 screenshot('school-homepage-cta-mobile.png')
 print(json.dumps({'coursePreviews':3,'studioExport':'valid SVG','knowledgeCheck':'passed','certificate':'gated and downloadable','desktopAndMobile':'passed','homepageLink':'passed'}))
finally:
 if c:c.socket.close()
 process.terminate();process.wait(timeout=10)
