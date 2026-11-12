import * as THREE from "./vendor/three/three.module.js";
import { OrbitControls } from "./vendor/three/addons/controls/OrbitControls.js";
import { GLTFExporter } from "./vendor/three/addons/exporters/GLTFExporter.js";
import { buildGarment } from "./school-3d-models.js?v=2";

const stage = document.querySelector("#school-3d-stage");
const status = document.querySelector("#school-3d-status");
const $ = (selector) => document.querySelector(selector);

function currentDesign() {
  const color = document.querySelector('[data-school-color][aria-pressed="true"]');
  return {
    name: $("#school-design-name").value.trim() || "My first Velora design",
    silhouette: $("#school-silhouette").value,
    color: color.dataset.schoolColor,
    colorName: color.dataset.schoolColorName,
    texture: $("#school-texture").value,
    length: Number($("#school-length").value),
    fit: Number($("#school-fit").value),
  };
}

function unavailable(message) {
  document.dispatchEvent(new CustomEvent("velora:school-3d-unavailable", { detail: { message } }));
}

function disposeModel(model) {
  if (!model) return;
  const geometries = new Set(), materials = new Set(), textures = new Set();
  model.traverse((object) => {
    if (object.geometry) geometries.add(object.geometry);
    for (const material of (Array.isArray(object.material) ? object.material : [object.material])) {
      if (!material) continue;
      materials.add(material);
      for (const value of Object.values(material)) if (value?.isTexture) textures.add(value);
    }
  });
  textures.forEach((texture) => texture.dispose());
  materials.forEach((material) => material.dispose());
  geometries.forEach((geometry) => geometry.dispose());
}

function download(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function filename() {
  return currentDesign().name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60) || "velora-design";
}

try {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: true, powerPreference: "low-power" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.15;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const canvas = renderer.domElement;
  canvas.tabIndex = 0;
  canvas.setAttribute("role", "img");
  canvas.setAttribute("aria-describedby", "school-3d-help");
  stage.append(canvas);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color("#ebe5dc");
  const camera = new THREE.PerspectiveCamera(36, 1, .1, 60);
  camera.position.set(3, 2, 6);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = .09;
  controls.enablePan = false;
  controls.minPolarAngle = .32;
  controls.maxPolarAngle = Math.PI * .64;
  controls.minDistance = 1.8;
  controls.maxDistance = 12;
  controls.autoRotate = false;
  controls.autoRotateSpeed = .8;

  scene.add(new THREE.HemisphereLight("#fff9ec", "#a4917a", 2.4));
  const key = new THREE.DirectionalLight("#fff9ee", 3.2);
  key.position.set(4, 7, 5);
  key.castShadow = true;
  key.shadow.mapSize.set(1024, 1024);
  Object.assign(key.shadow.camera, { left: -3.5, right: 3.5, top: 4, bottom: -3, near: .5, far: 18 });
  key.shadow.normalBias = .025;
  scene.add(key);
  const fill = new THREE.DirectionalLight("#e8edff", 1.5);
  fill.position.set(-4, 3, -4);
  scene.add(fill);
  const front = new THREE.DirectionalLight("#ffffff", .65);
  front.position.set(-2, 2, 5);
  scene.add(front);

  const display = new THREE.Group();
  const pedestal = new THREE.Mesh(
    new THREE.CylinderGeometry(1.9, 1.96, .09, 80),
    new THREE.MeshStandardMaterial({ color: "#ded4c5", roughness: .96 }),
  );
  pedestal.position.y = -.035;
  pedestal.receiveShadow = true;
  display.add(pedestal);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(80, 80), new THREE.MeshStandardMaterial({ color: "#ebe5dc", roughness: 1 }));
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -.085;
  ground.receiveShadow = true;
  display.add(ground);
  scene.add(display);

  let garment, settings = currentDesign(), dirty = true, visible = false, stopped = false, queued = 0;
  let geometryKey = "", center = new THREE.Vector3(0, 1.5, 0), construction = null;
  const modelRoot = new THREE.Group();
  scene.add(modelRoot);

  function updateInspection() {
    if (construction) {
      scene.remove(construction);
      disposeModel(construction);
      construction = null;
    }
    const mode = stage.dataset.inspection || "fabric";
    if (mode === "construction" && garment) {
      garment.updateMatrixWorld(true);
      construction = new THREE.Group();
      construction.name = "Inspection overlay (not exported)";
      const tone = new THREE.Color(settings.color);
      const lightFabric = tone.r * .2126 + tone.g * .7152 + tone.b * .0722 > .25;
      const material = new THREE.LineBasicMaterial({ color: lightFabric ? "#4c4338" : "#f0d9b9", transparent: true, opacity: .27, depthWrite: false });
      garment.traverse((object) => {
        // Exclude tiny stitch tubes and hardware; the useful study is the shell.
        if (!object.isMesh || !object.geometry.index || object.geometry.attributes.position.count < 500) return;
        const lines = new THREE.LineSegments(new THREE.WireframeGeometry(object.geometry), material);
        lines.applyMatrix4(object.matrixWorld);
        construction.add(lines);
      });
      scene.add(construction);
    }
    const label = { dress: "Wrap dress", jacket: "Tailored jacket", set: "Wide-leg set" }[settings.silhouette];
    $("#school-stage-caption").textContent = `${label} / ${mode === "construction" ? "Construction study" : "Fabric view"}`;
    dirty = true;
  }

  function renderNow() {
    if (stopped) return;
    renderer.render(scene, camera);
    dirty = false;
  }

  function resize() {
    const width = stage.clientWidth;
    const height = stage.clientHeight;
    if (!width || !height) return;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    dirty = true;
    renderNow();
  }

  function frameModel(view = "reset") {
    const bounds = new THREE.Box3().setFromObject(garment);
    const size = bounds.getSize(new THREE.Vector3());
    bounds.getCenter(center);
    controls.target.copy(center);
    const fit = Math.max(size.y, size.x / Math.max(camera.aspect, .4));
    const distance = Math.max(3.4, fit / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2))) * 1.23);
    const direction = view === "front" ? new THREE.Vector3(0, .04, 1)
      : view === "side" ? new THREE.Vector3(1, .04, 0)
        : view === "back" ? new THREE.Vector3(0, .04, -1)
          : new THREE.Vector3(.65, .19, 1);
    camera.position.copy(center).add(direction.normalize().multiplyScalar(distance));
    controls.update();
    stage.dataset.view = view;
    document.querySelectorAll("[data-school-camera]").forEach((button) => {
      if (button.dataset.schoolCamera !== "reset") button.setAttribute("aria-pressed", String(button.dataset.schoolCamera === view));
    });
    dirty = true;
    renderNow();
  }

  function updateModel(next) {
    settings = next;
    const nextKey = JSON.stringify([next.silhouette, next.color, next.texture, next.length, next.fit]);
    if (nextKey !== geometryKey) {
      const previous = garment;
      const changedSilhouette = !previous || previous.userData.silhouette !== next.silhouette;
      garment = buildGarment(THREE, next);
      garment.name = next.name;
      garment.userData.designName = next.name;
      if (previous) modelRoot.remove(previous);
      modelRoot.add(garment);
      disposeModel(previous);
      geometryKey = nextKey;
      updateInspection();
      if (changedSilhouette) frameModel();
      else {
        const nextCenter = new THREE.Box3().setFromObject(garment).getCenter(new THREE.Vector3());
        camera.position.add(nextCenter.clone().sub(controls.target));
        controls.target.copy(nextCenter);
        center.copy(nextCenter);
        controls.update();
      }
    } else {
      garment.name = next.name;
      garment.userData.designName = next.name;
    }
    canvas.setAttribute("aria-label", `Interactive 3D ${$("#school-silhouette").selectedOptions[0].textContent.toLowerCase()} in ${next.colorName}`);
    stage.dataset.silhouette = next.silhouette;
    stage.dataset.color = next.color;
    stage.dataset.texture = next.texture;
    stage.dataset.length = String(next.length);
    stage.dataset.fit = String(next.fit);
    dirty = true;
    renderNow();
  }

  resize();
  updateModel(settings);
  resize();
  stage.dataset.ready = "true";
  stage.setAttribute("aria-busy", "false");
  $("#school-3d-loading").hidden = true;
  status.textContent = "3D studio ready. Explore your design from every angle.";
  document.dispatchEvent(new CustomEvent("velora:school-3d-ready"));

  controls.addEventListener("change", () => { dirty = true; });
  controls.addEventListener("start", () => {
    stage.dataset.view = "custom";
    document.querySelectorAll('[data-school-camera][aria-pressed="true"]').forEach((button) => button.setAttribute("aria-pressed", "false"));
  });
  document.addEventListener("velora:school-design", (event) => {
    cancelAnimationFrame(queued);
    queued = requestAnimationFrame(() => { queued = 0; updateModel(event.detail); });
  });
  document.querySelectorAll("[data-school-camera]").forEach((button) => button.addEventListener("click", () => {
    frameModel(button.dataset.schoolCamera);
  }));
  $("#school-auto-rotate").addEventListener("click", () => {
    controls.autoRotate = !controls.autoRotate;
    $("#school-auto-rotate").setAttribute("aria-pressed", String(controls.autoRotate));
    $("#school-auto-rotate").textContent = controls.autoRotate ? "Pause rotation" : "Auto rotate";
    dirty = true;
  });
  document.querySelectorAll("[data-school-inspect]").forEach((button) => button.addEventListener("click", () => {
    stage.dataset.inspection = button.dataset.schoolInspect;
    document.querySelectorAll("[data-school-inspect]").forEach((choice) => choice.setAttribute("aria-pressed", String(choice === button)));
    updateInspection();
    status.textContent = button.dataset.schoolInspect === "construction"
      ? "Construction study: inspect the mesh shaping. Downloads keep the clean fabric model."
      : "Fabric view: explore the surface, shape and finish.";
    renderNow();
  }));
  $("#school-lighting").addEventListener("change", () => {
    const daylight = $("#school-lighting").value === "daylight";
    const background = daylight ? "#e9edf0" : "#ebe5dc";
    scene.background.set(background);
    ground.material.color.set(background);
    pedestal.material.color.set(daylight ? "#d4dadd" : "#ded4c5");
    key.color.set(daylight ? "#ffffff" : "#fff9ee");
    fill.color.set(daylight ? "#ffffff" : "#e8edff");
    renderer.toneMappingExposure = daylight ? 1.05 : 1.15;
    stage.dataset.lighting = daylight ? "daylight" : "atelier";
    status.textContent = daylight ? "Neutral daylight helps compare your chosen color and finish." : "Warm atelier lighting restored.";
    dirty = true;
    renderNow();
  });

  canvas.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "+", "-", "=", "Home"].includes(event.key)) return;
    event.preventDefault();
    if (event.key === "Home") { frameModel(); return; }
    const offset = camera.position.clone().sub(controls.target);
    const spherical = new THREE.Spherical().setFromVector3(offset);
    if (event.key === "ArrowLeft") spherical.theta -= .12;
    if (event.key === "ArrowRight") spherical.theta += .12;
    if (event.key === "ArrowUp") spherical.phi -= .08;
    if (event.key === "ArrowDown") spherical.phi += .08;
    if (event.key === "+" || event.key === "=") spherical.radius *= .9;
    if (event.key === "-") spherical.radius *= 1.1;
    spherical.phi = THREE.MathUtils.clamp(spherical.phi, controls.minPolarAngle, controls.maxPolarAngle);
    spherical.radius = THREE.MathUtils.clamp(spherical.radius, controls.minDistance, controls.maxDistance);
    camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(spherical));
    controls.update();
    dirty = true;
    renderNow();
  });

  $("#school-snapshot").addEventListener("click", () => {
    if (queued) { cancelAnimationFrame(queued); queued = 0; updateModel(currentDesign()); }
    renderNow();
    canvas.toBlob((blob) => {
      if (!blob) { status.textContent = "The image could not be saved. Please try again."; return; }
      download(blob, `${filename()}-studio.png`);
      document.dispatchEvent(new CustomEvent("velora:school-design-saved", { detail: { format: "studio image" } }));
    }, "image/png");
  });

  document.addEventListener("velora:school-export-3d", async () => {
    const button = $("#school-save-design");
    if (button.disabled) return;
    button.disabled = true;
    status.textContent = "Preparing your 3D model…";
    try {
      if (queued) { cancelAnimationFrame(queued); queued = 0; updateModel(currentDesign()); }
      const exported = await new GLTFExporter().parseAsync(garment, { binary: true, onlyVisible: true, maxTextureSize: 512 });
      download(new Blob([exported], { type: "model/gltf-binary" }), `${filename()}.glb`);
      status.textContent = "Your GLB model is ready. Open it in compatible 3D design software.";
      document.dispatchEvent(new CustomEvent("velora:school-design-saved", { detail: { format: "3D model" } }));
    } catch (error) {
      status.textContent = "The 3D export could not be completed. Try saving a studio image or switching to the 2D sketch.";
      console.error("Velora 3D model export failed.", error);
    } finally {
      button.disabled = stage.dataset.mode === "3d" && stage.dataset.ready !== "true";
    }
  });

  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(stage);
  const intersection = new IntersectionObserver((entries) => { visible = entries.some((entry) => entry.isIntersecting); }, { rootMargin: "180px" });
  intersection.observe(stage);
  document.addEventListener("velora:school-view", () => { resize(); dirty = true; });
  canvas.addEventListener("webglcontextlost", (event) => {
    event.preventDefault();
    stopped = true;
    renderer.setAnimationLoop(null);
    unavailable("The 3D session was interrupted. Your design is still available in the 2D sketch view; reload the page to restart 3D.");
  });
  let lastTime = 0;
  renderer.setAnimationLoop((time) => {
    const delta = Math.min((time - lastTime) / 1000 || 0, .05);
    lastTime = time;
    if (stopped || !visible || document.hidden || stage.hidden) return;
    const changed = controls.update(delta);
    if (dirty || changed || controls.autoRotate) renderNow();
  });
  window.addEventListener("pagehide", (event) => {
    if (event.persisted) return;
    stopped = true;
    cancelAnimationFrame(queued);
    renderer.setAnimationLoop(null);
    intersection.disconnect();
    resizeObserver.disconnect();
    controls.dispose();
    disposeModel(garment);
    disposeModel(construction);
    disposeModel(display);
    renderer.dispose();
  });
} catch (error) {
  console.error("Velora 3D studio could not start.", error);
  unavailable("3D is unavailable in this browser. You can keep designing and saving in the 2D sketch view.");
}
