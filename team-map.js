/* Geographic data: Natural Earth, public domain. See assets/world-land-source.json. */
(() => {
  const stage = document.querySelector('[data-world-map]');
  if (!stage) return;
  const canvas = stage.querySelector('canvas');
  const ctx = canvas.getContext('2d');
  const status = stage.querySelector('.world-loading');
  if (!ctx) { status.textContent = 'Explore our establishments in the location list.'; return; }
  const rad = Math.PI / 180;
  const locations = {
    rotterdam: { lat: 51.9244, lon: 4.4777, name: 'Rotterdam', country: 'Netherlands', description: "Our home base in the Netherlands, connecting all six Lenora establishments." },
    paris: { lat: 48.8566, lon: 2.3522, name: 'Paris', country: 'France', description: 'Part of the Lenora world, connected to our main establishment in Rotterdam.' },
    london: { lat: 51.5074, lon: -.1278, name: 'London', country: 'United Kingdom', description: 'Part of the Lenora world, connected to our main establishment in Rotterdam.' },
    dubai: { lat: 25.2048, lon: 55.2708, name: 'Dubai', country: 'United Arab Emirates', description: 'Part of the Lenora world, connected to our main establishment in Rotterdam.' },
    frankfurt: { lat: 50.1109, lon: 8.6821, name: 'Frankfurt', country: 'Germany', description: 'Part of the Lenora world, connected to our main establishment in Rotterdam.' },
    turkiye: { lat: 39, lon: 35, name: 'T\u00fcrkiye', country: 'Country presence', description: 'Our presence in T\u00fcrkiye. The marker represents the country rather than a specific city.' }
  };
  const buttons = [...stage.querySelectorAll('[data-location]')];
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  let paused = reduced.matches, selected = 'rotterdam', lon = 15 * rad, lat = 33 * rad;
  let texture, frame = 0, animation = null, drag = null, visible = true;
  const size = 640, radius = 292, center = 380;
  const sphere = document.createElement('canvas'); sphere.width = sphere.height = size;
  // Hardware shading keeps geographic reprojection off the main CPU thread.
  const gl = sphere.getContext('webgl', { alpha: true, antialias: true, preserveDrawingBuffer: true });
  let paintSphere;
  if (gl) {
    const shader = (type, source) => {
      const value = gl.createShader(type); gl.shaderSource(value, source); gl.compileShader(value);
      if (!gl.getShaderParameter(value, gl.COMPILE_STATUS)) throw Error('Globe shader failed');
      return value;
    };
    const program = gl.createProgram();
    gl.attachShader(program, shader(gl.VERTEX_SHADER, `attribute vec2 position; varying vec2 point;
      void main(){point=position;gl_Position=vec4(position,0.,1.);}`));
    gl.attachShader(program, shader(gl.FRAGMENT_SHADER, `precision highp float;
      varying vec2 point; uniform sampler2D land; uniform vec2 rotation;
      void main(){
        float d=dot(point,point);if(d>1.)discard;
        float z=sqrt(1.-d);float sl=sin(rotation.y),cl=cos(rotation.y);
        float latitude=asin(clamp(point.y*cl+z*sl,-1.,1.));
        float longitude=rotation.x+atan(point.x,z*cl-point.y*sl);
        vec2 uv=vec2(fract(longitude/6.28318530718+.5),.5-latitude/3.14159265359);
        float mask=texture2D(land,uv).r;
        vec3 ocean=vec3(.075,.155,.155),earth=vec3(.70,.65,.52);
        float light=.43+.57*max(0.,dot(vec3(point,z),normalize(vec3(-.48,.55,.85))));
        vec3 color=mix(ocean,earth,mask)*light;
        float fresnel=pow(1.-z,3.5);
        color+=vec3(.16,.30,.30)*fresnel*.55;
        gl_FragColor=vec4(color,1.-smoothstep(.992,1.,d));
      }`));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw Error('Globe program failed');
    gl.useProgram(program);
    const buffer = gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]), gl.STATIC_DRAW);
    const position = gl.getAttribLocation(program, 'position');gl.enableVertexAttribArray(position);gl.vertexAttribPointer(position,2,gl.FLOAT,false,0,0);
    const mapTexture = gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,mapTexture);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
    gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,1,1,0,gl.RGBA,gl.UNSIGNED_BYTE,new Uint8Array([0,0,0,255]));
    const rotation = gl.getUniformLocation(program,'rotation');
    let uploaded = false;
    paintSphere = () => {
      if (texture && !uploaded) { gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,texture);uploaded=true; }
      gl.uniform2f(rotation,lon,lat);gl.clear(gl.COLOR_BUFFER_BIT);gl.drawArrays(gl.TRIANGLES,0,6);
    };
    stage.dataset.renderer = 'webgl';
    sphere.addEventListener('webglcontextlost', e => { e.preventDefault(); status.hidden=false;status.textContent='Restoring atlas?'; });
    sphere.addEventListener('webglcontextrestored', () => { status.hidden=false;status.textContent='Reload this page to restore the interactive atlas.'; });
  } else {
    // Smaller raster fallback preserves all locations and controls without WebGL.
    const fallback = document.createElement('canvas');fallback.width=fallback.height=360;
    const sc=fallback.getContext('2d'), pixels=sc.createImageData(360,360), normals=[];
    for(let y=0;y<360;y++)for(let x=0;x<360;x++){
      const nx=(x+.5-180)/179,ny=-(y+.5-180)/179,d=nx*nx+ny*ny;
      if(d<1)normals.push([4*(y*360+x),nx,ny,Math.sqrt(1-d),Math.min(1,(1-d)*170)]);
    }
    paintSphere=()=>{
      const sl=Math.sin(lat),cl=Math.cos(lat);
      for(const [i,x,y,z,alpha]of normals){
        const p=Math.asin(Math.max(-1,Math.min(1,y*cl+z*sl))),l=lon+Math.atan2(x,z*cl-y*sl);
        const tx=((Math.floor((l/(2*Math.PI)+.5)*1600)%1600)+1600)%1600,ty=Math.max(0,Math.min(799,Math.floor((.5-p/Math.PI)*800)));
        const land=texture?texture[(ty*1600+tx)*4]/255:0,light=.43+.57*Math.max(0,-.43*x+.5*y+.77*z),rim=Math.pow(1-z,3.5);
        pixels.data[i]=(19+land*160)*light+rim*22;pixels.data[i+1]=(40+land*126)*light+rim*42;pixels.data[i+2]=(40+land*93)*light+rim*42;pixels.data[i+3]=255*alpha;
      }
      sc.putImageData(pixels,0,0);
    };
    paintSphere.canvas=fallback;stage.dataset.renderer='canvas';
  }
  const graticules=[];
  for(let p=-60;p<=60;p+=30)graticules.push(Array.from({length:181},(_,i)=>[p,i*2-180]));
  for(let l=-180;l<180;l+=30)graticules.push(Array.from({length:91},(_,i)=>[i*2-90,l]));
  const routes=Object.entries(locations).filter(([key])=>key!=='rotterdam').map(([key,p])=>{
    const vector=p=>[Math.cos(p.lat*rad)*Math.cos(p.lon*rad),Math.cos(p.lat*rad)*Math.sin(p.lon*rad),Math.sin(p.lat*rad)];
    const a=vector(locations.rotterdam),b=vector(p),angle=Math.acos(Math.min(1,a.reduce((v,n,i)=>v+n*b[i],0)));
    const points=Array.from({length:51},(_,i)=>{
      const t=i/50,sa=Math.sin((1-t)*angle)/Math.sin(angle),sb=Math.sin(t*angle)/Math.sin(angle),v=a.map((n,j)=>n*sa+b[j]*sb);
      return[Math.asin(v[2])/rad,Math.atan2(v[1],v[0])/rad,1+Math.sin(Math.PI*t)*.055];
    });
    return {key,points};
  });
  function project(latitude, longitude, elevation = 1) {
    const p = latitude * rad, d = longitude * rad - lon;
    const cp = Math.cos(p), sp = Math.sin(p), cl = Math.cos(lat), sl = Math.sin(lat);
    return [center + radius * elevation * cp * Math.sin(d), center - radius * elevation * (cl * sp - sl * cp * Math.cos(d)), sl * sp + cl * cp * Math.cos(d)];
  }
  function line(points, color, width = .6) {
    ctx.beginPath(); let pen = false;
    for (const p of points) {
      const v = project(...p);
      if (v[2] <= .015) { pen = false; continue; }
      if (pen) ctx.lineTo(v[0], v[1]); else ctx.moveTo(v[0], v[1]);
      pen = true;
    }
    ctx.strokeStyle = color; ctx.lineWidth = width; ctx.stroke();
  }
  function draw() {
    ctx.clearRect(0, 0, 760, 760);
    const halo=ctx.createRadialGradient(center,center,radius*.75,center,center,radius*1.15);
    halo.addColorStop(0,'#8fb7a000');halo.addColorStop(.7,'#8fb7a012');halo.addColorStop(1,'#8fb7a000');
    ctx.fillStyle=halo;ctx.fillRect(0,0,760,760);
    paintSphere();
    ctx.drawImage(paintSphere.canvas || sphere, center-radius, center-radius, radius*2, radius*2);
    for(const points of graticules)line(points,'#e0ddc514');
    ctx.beginPath();ctx.arc(center,center,radius,0,Math.PI*2);ctx.strokeStyle='#b8d2c54d';ctx.lineWidth=.8;ctx.stroke();
    for(const route of routes)line(route.points,route.key===selected?'#f0c993d9':'#d0ad7645',route.key===selected?1.7:.7);
    for (const [key, p] of Object.entries(locations)) {
      const v = project(p.lat, p.lon, 1.006); if (v[2] < .06) continue;
      const active = key === selected;
      if (active) { ctx.beginPath();ctx.arc(v[0], v[1], 12, 0, Math.PI * 2);ctx.fillStyle = '#f6e5c22a';ctx.fill();ctx.strokeStyle = '#f8e8c680';ctx.lineWidth = .7;ctx.stroke(); }
      ctx.beginPath();ctx.arc(v[0], v[1], active ? 4.3 : 2.8, 0, Math.PI * 2);
      ctx.fillStyle = key === 'rotterdam' ? '#b9684c' : '#e2c69a';ctx.fill();ctx.strokeStyle = '#fff3dd';ctx.lineWidth = 1.2;ctx.stroke();
      if (active) {
        const title = p.name + (key === 'rotterdam' ? ' / MAIN' : '');
        const fontSize = Math.max(13, 10 * 760 / Math.max(280, canvas.clientWidth));
        const labelHeight = fontSize + 17;
        ctx.font = `500 ${fontSize}px Arial, sans-serif`; const width = ctx.measureText(title).width + 24;
        const lx = Math.min(710 - width, Math.max(30, v[0] + 19)), ly = v[1] - labelHeight - 13;
        ctx.beginPath();ctx.moveTo(v[0] + 4, v[1] - 4);ctx.lineTo(lx, ly + labelHeight / 2);ctx.strokeStyle = '#e4d4b4bb';ctx.lineWidth = .8;ctx.stroke();
        ctx.fillStyle = '#f5efdf';ctx.beginPath();ctx.roundRect(lx,ly,width,labelHeight,3);ctx.fill();ctx.fillStyle = '#243b34';ctx.fillText(title, lx + 12, ly + fontSize + 7);
      }
    }
  }
  function tick(now) {
    frame = 0;
    if (animation) {
      const t = Math.min(1, (now - animation.start) / 850), e = 1 - Math.pow(1 - t, 3);
      lon = animation.lon + (animation.targetLon - animation.lon) * e;
      lat = animation.lat + (animation.targetLat - animation.lat) * e;
      if (t === 1) animation = null;
    }
    draw(); if (animation && visible) requestDraw();
  }
  function requestDraw() { if (!frame && visible) frame = requestAnimationFrame(tick); }
  function focusPlace(key) {
    selected = key; const p = locations[key];
    buttons.forEach(b => b.setAttribute('aria-pressed', String(b.dataset.location === key)));
    stage.querySelector('[data-place-role]').textContent = `${String(Object.keys(locations).indexOf(key) + 1).padStart(2, '0')} / ${key === 'rotterdam' ? 'MAIN ESTABLISHMENT' : 'LENORA PRESENCE'}`;
    stage.querySelector('[data-place-name]').textContent = p.name;
    stage.querySelector('[data-place-country]').textContent = p.country;
    stage.querySelector('[data-place-description]').textContent = p.description;
    stage.querySelector('[data-place-coordinates]').textContent = key === 'turkiye' ? 'COUNTRY-LEVEL LOCATION' : `${Math.abs(p.lat).toFixed(4)}\u00b0 N  /  ${Math.abs(p.lon).toFixed(4)}\u00b0 ${p.lon < 0 ? 'W' : 'E'}`;
    const targetLon = (p.lon + 10) * rad, targetLat = Math.max(18, p.lat - 18) * rad;
    if (paused) { lon = targetLon; lat = targetLat; animation = null; }
    else animation = { start: performance.now(), lon, lat, targetLon: lon + Math.atan2(Math.sin(targetLon - lon), Math.cos(targetLon - lon)), targetLat };
    requestDraw();
  }
  buttons.forEach(b => b.addEventListener('click', () => focusPlace(b.dataset.location)));
  stage.querySelector('.world-reset').addEventListener('click', () => focusPlace('rotterdam'));
  const control = stage.querySelector('.world-motion');
  function syncMotion() { control.setAttribute('aria-pressed', String(paused)); control.textContent = paused ? 'Enable motion' : 'Pause motion'; if (paused && animation) { lon = animation.targetLon;lat = animation.targetLat;animation = null;requestDraw(); } }
  control.addEventListener('click', () => { paused = !paused;syncMotion(); });
  reduced.addEventListener('change', () => { paused = reduced.matches;syncMotion(); });
  canvas.addEventListener('pointerdown', e => {
    if (e.button && e.button !== 0) return;
    drag = { x: e.clientX, y: e.clientY, lon, lat };animation = null;canvas.setPointerCapture(e.pointerId);canvas.classList.add('is-dragging');
  });
  canvas.addEventListener('pointermove', e => { if (!drag) return;lon = drag.lon - (e.clientX - drag.x) * .006;lat = Math.max(-1.2, Math.min(1.2, drag.lat + (e.clientY - drag.y) * .006));requestDraw(); });
  function endDrag(e) {
    if (drag && Math.hypot((e?.clientX ?? drag.x)-drag.x,(e?.clientY ?? drag.y)-drag.y)<6) {
      const box=canvas.getBoundingClientRect(),x=((e?.clientX ?? drag.x)-box.left)*760/box.width,y=((e?.clientY ?? drag.y)-box.top)*760/box.height;
      const nearest=Object.entries(locations).map(([key,p])=>{const v=project(p.lat,p.lon,1.006);return{key,z:v[2],distance:Math.hypot(x-v[0],y-v[1])};}).filter(p=>p.z>.06&&p.distance<24).sort((a,b)=>a.distance-b.distance)[0];
      if(nearest)focusPlace(nearest.key);
    }
    drag = null; canvas.classList.remove('is-dragging'); }
  canvas.addEventListener('pointerup', endDrag);canvas.addEventListener('pointercancel', endDrag);canvas.addEventListener('lostpointercapture', endDrag);
  canvas.addEventListener('keydown', e => {
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) return;
    e.preventDefault();animation = null;
    if (e.key === 'ArrowLeft') lon -= .12;if (e.key === 'ArrowRight') lon += .12;
    if (e.key === 'ArrowUp') lat = Math.min(1.2, lat + .12);if (e.key === 'ArrowDown') lat = Math.max(-1.2, lat - .12);requestDraw();
  });
  if ('IntersectionObserver' in window) new IntersectionObserver(entries => { visible = entries[0].isIntersecting;if (visible) requestDraw();else if (frame) { cancelAnimationFrame(frame);frame = 0; } }).observe(canvas);
  if ('ResizeObserver' in window) new ResizeObserver(requestDraw).observe(canvas);
  syncMotion(); requestDraw();
  // Load a prebuilt geographic mask only when the section approaches the viewport.
  // No GeoJSON parsing or texture construction is needed in the browser.
  let loading = false;
  function loadAtlas() {
    if (loading) return;
    loading = true;
    const image = new Image(); image.decoding = 'async';
    image.onload = () => {
      if (gl) texture = image;
      else {
        const map=document.createElement('canvas');map.width=1600;map.height=800;
        const mc=map.getContext('2d',{willReadFrequently:true});mc.drawImage(image,0,0,1600,800);
        texture=mc.getImageData(0,0,1600,800).data;
      }
      status.hidden=true;stage.dataset.ready='true';requestDraw();
    };
    image.onerror=()=>{ status.textContent='Atlas unavailable. Explore our locations in the list.';stage.dataset.ready='error'; };
    image.src='assets/world-land-mask.png';
  }
  if ('IntersectionObserver' in window) {
    const loader=new IntersectionObserver(entries=>{if(entries.some(entry=>entry.isIntersecting)){loadAtlas();loader.disconnect();}},{rootMargin:'300px'});
    loader.observe(stage);
  } else loadAtlas();
})();
