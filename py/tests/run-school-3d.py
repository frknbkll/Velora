"""Browser checks for real WebGL models, customization, camera views and downloads."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

import base64,json,runpy,socket,struct,subprocess,time,urllib.request
from pathlib import Path
BrowserConnection=runpy.run_path(str(ROOT/'py/tests/run-product-colors.py'))['BrowserConnection']
with socket.socket() as reservation:reservation.bind(('127.0.0.1',0));port=reservation.getsockname()[1]
profile=ROOT/'tmp/school-3d-browser-check';profile.mkdir(parents=True,exist_ok=True)
downloads=ROOT/'tmp/school-3d-download-check';downloads.mkdir(parents=True,exist_ok=True)
for filename in ('atelier-3d-test.glb','atelier-3d-test-studio.png'):
 target=downloads/filename
 if target.exists():target.unlink()
process=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe','--headless','--use-angle=swiftshader','--enable-unsafe-swiftshader','--no-first-run',f'--remote-debugging-port={port}',f'--user-data-dir={profile}','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
c=None
try:
 for _ in range(100):
  try:
   with urllib.request.urlopen(f'http://127.0.0.1:{port}/json',timeout=1) as r:page=next(p for p in json.load(r) if p['type']=='page')
   break
  except (OSError,StopIteration):time.sleep(.1)
 if 'page' not in locals():raise RuntimeError('Chrome did not start')
 c=BrowserConnection(page['webSocketDebuggerUrl'])
 c.call('Page.enable')
 c.call('Network.enable');c.call('Network.setCacheDisabled',{'cacheDisabled':True})
 c.call('Browser.setDownloadBehavior',{'behavior':'allow','downloadPath':str(downloads)})
 c.call('Page.addScriptToEvaluateOnNewDocument',{'source':"window.__studioErrors=[];window.addEventListener('error',e=>window.__studioErrors.push(e.message));window.addEventListener('unhandledrejection',e=>window.__studioErrors.push(String(e.reason)))"})
 def ev(expression):
  r=c.call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
  if 'exceptionDetails' in r:raise RuntimeError(r['exceptionDetails'])
  return r.get('result',{}).get('value')
 def waitfor(expression,message):
  for _ in range(200):
   if ev(expression):return
   time.sleep(.1)
  raise RuntimeError(message+': '+str(ev("document.querySelector('#school-3d-status')?.textContent")))
 def screenshot(name):
  (ROOT/'tmp'/name).write_bytes(base64.b64decode(c.call('Page.captureScreenshot',{'format':'png'})['data']))
 c.call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})
 c.call('Page.navigate',{'url':'http://127.0.0.1:8000/velora-school.html#design-studio'})
 waitfor("document.querySelector('#school-3d-stage')?.dataset.ready==='true'",'3D studio did not initialize')
 ev("document.fonts.ready")
 ev("document.documentElement.style.scrollBehavior='auto';[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Necessary only')?.click();document.querySelector('.school-3d-sheet').scrollIntoView({block:'center'})")
 ev("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
 assert ev("document.querySelector('#school-3d-stage canvas').width>0 && getComputedStyle(document.querySelector('#school-design-svg')).display==='none'"),'3D view is not exclusive'
 image_front=ev("document.querySelector('[data-school-camera=front]').click();document.querySelector('#school-3d-stage canvas').toDataURL()")
 image_side=ev("document.querySelector('[data-school-camera=side]').click();document.querySelector('#school-3d-stage canvas').toDataURL()")
 assert image_front!=image_side,'Front and side renders are identical'
 position=ev("(()=>{const r=document.querySelector('#school-3d-stage canvas').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
 c.call('Input.dispatchMouseEvent',{'type':'mousePressed','x':position['x'],'y':position['y'],'button':'left','clickCount':1})
 c.call('Input.dispatchMouseEvent',{'type':'mouseMoved','x':position['x']+70,'y':position['y']+12,'buttons':1})
 c.call('Input.dispatchMouseEvent',{'type':'mouseReleased','x':position['x']+70,'y':position['y']+12,'button':'left','clickCount':1})
 time.sleep(.15)
 drag_image=ev("document.querySelector('#school-3d-stage canvas').toDataURL()")
 assert drag_image!=image_side,'Dragging did not rotate the model'
 c.call('Input.dispatchMouseEvent',{'type':'mouseWheel','x':position['x'],'y':position['y'],'deltaY':-120,'deltaX':0})
 time.sleep(.15)
 assert ev("document.querySelector('#school-3d-stage canvas').toDataURL()")!=drag_image,'Wheel zoom did not change the view'
 for shape in ('dress','jacket','set'):
  ev(f"document.querySelector('#school-silhouette').value='{shape}';document.querySelector('#school-silhouette').dispatchEvent(new Event('input',{{bubbles:true}}))")
  waitfor(f"document.querySelector('#school-3d-stage').dataset.silhouette==='{shape}'",'Silhouette did not change')
  ev("document.querySelector('[data-school-camera=reset]').click()")
  screenshot(f'school-3d-{shape}-desktop.png')
 ev("document.querySelector('#school-design-name').value='Atelier 3D Test';document.querySelector('#school-design-name').dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('[data-school-color-name=Sage]').click();document.querySelector('#school-texture').value='woven';document.querySelector('#school-texture').dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('#school-length').value='1.12';document.querySelector('#school-length').dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('#school-fit').value='1.08';document.querySelector('#school-fit').dispatchEvent(new Event('input',{bubbles:true}))")
 waitfor("(()=>{const d=document.querySelector('#school-3d-stage').dataset;return d.color==='#a4ac95'&&d.texture==='woven'&&d.length==='1.12'&&d.fit==='1.08'})()",'Customization did not update model')
 fabric_image=ev("document.querySelector('#school-3d-stage canvas').toDataURL()")
 ev("document.querySelector('[data-school-inspect=construction]').click()")
 assert ev("document.querySelector('#school-3d-stage').dataset.inspection==='construction' && document.querySelector('[data-school-inspect=construction]').getAttribute('aria-pressed')==='true'"),'Construction inspection did not activate'
 assert ev("document.querySelector('#school-3d-stage canvas').toDataURL()")!=fabric_image,'Construction overlay did not change the render'
 screenshot('school-3d-construction-desktop.png')
 construction_image=ev("document.querySelector('#school-3d-stage canvas').toDataURL()")
 ev("document.querySelector('#school-lighting').value='daylight';document.querySelector('#school-lighting').dispatchEvent(new Event('change',{bubbles:true}))")
 assert ev("document.querySelector('#school-3d-stage').dataset.lighting==='daylight'"),'Daylight lighting did not activate'
 assert ev("document.querySelector('#school-3d-stage canvas').toDataURL()")!=construction_image,'Lighting did not change the render'
 ev("document.querySelector('#school-design-form').requestSubmit()")
 for _ in range(200):
  if (downloads/'atelier-3d-test.glb').exists():break
  time.sleep(.1)
 data=(downloads/'atelier-3d-test.glb').read_bytes()
 magic,version,length=struct.unpack_from('<III',data)
 assert magic==0x46546c67 and version==2 and length==len(data),'Invalid GLB header'
 json_length,kind=struct.unpack_from('<II',data,12);assert kind==0x4e4f534a
 gltf=json.loads(data[20:20+json_length]);assert len(gltf['meshes'])>3 and gltf['materials'],'Export is not a real garment model'
 assert not any('Inspection overlay' in n.get('name','') for n in gltf.get('nodes',[])),'Construction overlay leaked into the clean model download'
 positions=[gltf['accessors'][p['attributes']['POSITION']] for m in gltf['meshes'] for p in m['primitives']]
 assert any(a['max'][2]-a['min'][2]>.2 for a in positions),'Exported model lacks 3D depth'
 assert ev("document.querySelector('#school-project-status').dataset.complete==='true'"),'3D export did not count for workshop'
 ev("document.querySelector('#school-snapshot').click()")
 for _ in range(100):
  if (downloads/'atelier-3d-test-studio.png').exists():break
  time.sleep(.1)
 png=(downloads/'atelier-3d-test-studio.png').read_bytes();assert png.startswith(b'\x89PNG\r\n\x1a\n') and len(png)>5000,'Studio image export failed'
 ev("document.querySelector('#school-auto-rotate').click()")
 assert ev("document.querySelector('#school-auto-rotate').getAttribute('aria-pressed')==='true'"),'Auto rotation did not start'
 ev("document.querySelector('#school-auto-rotate').click();document.querySelector('[data-school-mode=sketch]').click()")
 assert ev("document.querySelector('#school-3d-stage').hidden && getComputedStyle(document.querySelector('#school-design-svg')).display!=='none'"),'Sketch view did not open'
 assert ev("document.querySelector('#school-3d-inspection').hidden"),'3D inspection controls remain visible in sketch view'
 ev("document.querySelector('[data-school-mode=\"3d\"]').click()")
 assert ev("!document.querySelector('#school-3d-stage').hidden && getComputedStyle(document.querySelector('#school-design-svg')).display==='none'"),'3D view did not reopen'
 assert ev("!document.querySelector('#school-3d-inspection').hidden"),'3D inspection controls did not reopen'
 ev("document.querySelector('[data-school-inspect=fabric]').click()")
 c.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
 ev("document.querySelector('.school-3d-topbar').scrollIntoView({block:'start'})")
 time.sleep(.2)
 assert ev("document.documentElement.scrollWidth<=innerWidth"),'3D studio mobile overflow'
 assert ev("document.querySelector('#school-3d-stage canvas').getBoundingClientRect().height>=400"),'Mobile canvas collapsed'
 screenshot('school-3d-mobile.png')
 assert ev('Array.isArray(window.__studioErrors) && window.__studioErrors.length===0'),'Browser errors during 3D interactions'
 c.call('Page.addScriptToEvaluateOnNewDocument',{'source':"const getContext=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(kind,...rest){return String(kind).startsWith('webgl')?null:getContext.call(this,kind,...rest)}"})
 c.call('Page.reload',{'ignoreCache':True})
 waitfor("document.querySelector('#school-3d-stage')?.dataset.failed==='true'",'No-WebGL fallback did not activate')
 assert ev("document.querySelector('#school-3d-stage').hidden && !document.querySelector('#school-save-design').disabled && getComputedStyle(document.querySelector('#school-design-svg')).display!=='none'"),'2D fallback unavailable'
 print(json.dumps({'garments':3,'real3DDepth':True,'colorFabricFitLength':'passed','cameraViews':'distinct renders','constructionAndLighting':'passed','cleanExportDuringInspection':'passed','exports':['GLB','PNG'],'workshopIntegration':'passed','mobile':'passed','noWebGLFallback':'passed'}))
finally:
 if c:c.socket.close()
 process.terminate();process.wait(timeout=10)
