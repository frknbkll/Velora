(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const svgNS = "http://www.w3.org/2000/svg";
  const state = { color: "#604032", colorName: "Espresso", lessons: new Set(), savedDesign: false, passedQuiz: false, certificateName: "", certificateDate: "" };
  const silhouettes = {
    dress: {
      name: "The wrap dress",
      outline: "M198 106 Q240 132 282 106 L326 126 354 269 317 280 291 193 287 270 342 529 Q240 552 138 529 L193 270 189 193 163 280 126 269 154 126 Z",
      details: ["M198 106 256 213 193 270 M282 106 221 218 287 270", "M193 263 Q240 254 287 263 L287 279 Q240 269 193 279Z", "M248 274 Q303 294 306 351 M248 274 Q268 331 261 370", "M207 295 177 517 M241 299 240 531 M275 302 305 518"],
    },
    jacket: {
      name: "The tailored jacket",
      outline: "M202 120 165 132 128 173 108 376 149 384 181 238 174 469 306 469 299 238 331 384 372 376 352 173 315 132 278 120 264 161 216 161 Z",
      details: ["M202 120 185 185 220 214 206 244 240 299 M278 120 295 185 260 214 274 244 240 299 240 469", "M185 351H222V375H183 M258 351H295L297 375H258", "M121 350 153 357 M327 357 359 350", "M242 325h3 M242 364h3"],
    },
    set: {
      name: "The wide-leg set",
      outline: "M202 104 Q240 126 278 104 L310 124 342 257 309 267 283 187 288 287 192 287 197 187 171 267 138 257 170 124 Z M192 307H288L326 538H264L240 383 216 538H154Z",
      details: ["M202 104 Q240 147 278 104", "M192 276H288 M192 318H288 M240 308V383", "M214 320 193 526 M266 320 287 526", "M193 327 213 343 M287 327 267 343"],
    },
  };

  function svgElement(tag, attributes = {}, text) {
    const element = document.createElementNS(svgNS, tag);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function renderDesign() {
    const design = silhouettes[$("#school-silhouette").value];
    const texture = $("#school-texture").value;
    const name = $("#school-design-name").value.trim() || "My first Velora design";
    const garment = $("#school-garment");
    const length = Number($("#school-length").value);
    const fit = Number($("#school-fit").value);
    garment.setAttribute("transform", `translate(240 544) scale(${fit} ${length}) translate(-240 -544)`);
    garment.replaceChildren(svgElement("path", { d: design.outline, fill: state.color, stroke: "#382e27", "stroke-width": "1.5", "stroke-linejoin": "round" }));
    if (texture !== "plain") garment.append(svgElement("path", { d: design.outline, fill: `url(#school-${texture})` }));
    for (const d of design.details) garment.append(svgElement("path", { d, fill: "none", stroke: "#ffffff", "stroke-opacity": ".48", "stroke-width": "1.4", "stroke-linecap": "round" }));
    $("#school-svg-title").textContent = name;
    $("#school-svg-desc").textContent = `${design.name} concept in ${state.colorName}, with ${$("#school-texture").selectedOptions[0].textContent.toLowerCase()} finish.`;
    $("#school-sketch-label").textContent = name;
    const sketchLabel = $("#school-sketch-label");
    sketchLabel.removeAttribute("textLength");
    sketchLabel.removeAttribute("lengthAdjust");
    const labelContext = document.createElement("canvas").getContext("2d");
    labelContext.font = "14px Georgia,serif";
    if (labelContext.measureText(name).width > 408) {
      sketchLabel.setAttribute("textLength", "408");
      sketchLabel.setAttribute("lengthAdjust", "spacingAndGlyphs");
    }
    $("#school-design-caption").textContent = `${design.name} · ${state.colorName} · ${$("#school-texture").selectedOptions[0].textContent}`;
    $("#school-selected-color").textContent = `Selected color: ${state.colorName}`;
    $("#school-length-value").textContent = `${Math.round(length * 100)}%`;
    $("#school-fit-value").textContent = `${Math.round(fit * 100)}%`;
    document.dispatchEvent(new CustomEvent("velora:school-design", { detail: {
      name, silhouette: $("#school-silhouette").value, color: state.color,
      colorName: state.colorName, texture: $("#school-texture").value, length, fit,
    } }));
  }

  function downloadSVG(svg, filename) {
    const serialized = new XMLSerializer().serializeToString(svg);
    const url = URL.createObjectURL(new Blob([serialized], { type: "image/svg+xml;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  $("#school-design-form").addEventListener("input", renderDesign);
  document.querySelectorAll("[data-school-color]").forEach((button) => button.addEventListener("click", () => {
    state.color = button.dataset.schoolColor;
    state.colorName = button.dataset.schoolColorName;
    document.querySelectorAll("[data-school-color]").forEach((choice) => choice.setAttribute("aria-pressed", String(choice === button)));
    renderDesign();
  }));

  $("#school-design-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const name = $("#school-design-name").value.trim();
    if (!name) { $("#school-design-name").focus(); return; }
    if ($("#school-3d-stage").dataset.mode === "3d" && $("#school-3d-stage").dataset.ready === "true") {
      document.dispatchEvent(new CustomEvent("velora:school-export-3d"));
      return;
    }
    const filename = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60) || "velora-design";
    const sketch = $("#school-design-svg").cloneNode(true);
    sketch.removeAttribute("hidden");
    sketch.removeAttribute("aria-hidden");
    downloadSVG(sketch, `${filename}.svg`);
    state.savedDesign = true;
    $("#school-design-feedback").dataset.state = "success";
    $("#school-design-feedback").textContent = "Your design is ready in your downloads. Keep exploring, or complete the free workshop for your certificate.";
    updateProgress();
  });

  function setStudioView(mode) {
    const stage = $("#school-3d-stage");
    if (mode === "3d" && stage.dataset.failed === "true") mode = "sketch";
    stage.dataset.mode = mode;
    stage.hidden = mode !== "3d";
    $("#school-design-svg").toggleAttribute("hidden", mode === "3d");
    $("#school-design-svg").setAttribute("aria-hidden", String(mode === "3d"));
    $("#school-3d-toolbar").hidden = mode !== "3d";
    $("#school-3d-inspection").hidden = mode !== "3d";
    $("#school-3d-help").hidden = mode !== "3d";
    document.querySelectorAll("[data-school-mode]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.schoolMode === mode)));
    $("#school-save-design").textContent = mode === "3d" ? "Download 3D model ↓" : "Save my sketch ↓";
    $("#school-save-design").disabled = mode === "3d" && stage.dataset.ready !== "true";
    document.dispatchEvent(new CustomEvent("velora:school-view", { detail: { mode } }));
  }

  document.querySelectorAll("[data-school-mode]").forEach((button) => button.addEventListener("click", () => setStudioView(button.dataset.schoolMode)));
  document.addEventListener("velora:school-3d-ready", () => setStudioView($("#school-3d-stage").dataset.mode || "3d"));
  function showSketchFallback(message) {
    $("#school-3d-stage").dataset.failed = "true";
    $("#school-3d-stage").setAttribute("aria-busy", "false");
    document.querySelector('[data-school-mode="3d"]').disabled = true;
    setStudioView("sketch");
    $("#school-3d-status").textContent = message || "3D is unavailable in this browser. You can keep designing and saving in the 2D sketch view.";
  }
  document.addEventListener("velora:school-3d-unavailable", (event) => showSketchFallback(event.detail?.message));
  document.querySelector('script[src^="/js/school-3d.js"]')?.addEventListener("error", () => showSketchFallback());
  document.addEventListener("velora:school-design-saved", (event) => {
    state.savedDesign = true;
    $("#school-design-feedback").dataset.state = "success";
    $("#school-design-feedback").textContent = `Your ${event.detail?.format || "design"} is ready in your downloads. Your workshop design project is complete.`;
    updateProgress();
  });

  function certificateReady() { return state.lessons.size === 3 && state.savedDesign && state.passedQuiz; }

  function resetCertificate() {
    state.certificateName = "";
    state.certificateDate = "";
    $("#school-certificate-name").textContent = "Your name here";
    $("#school-certificate-date").textContent = "A first step. A new point of view.";
    $("#school-certificate-mark").textContent = "CERTIFICATE PREVIEW";
    $("#school-certificate-actions").hidden = true;
    $("#school-certificate-feedback").textContent = "";
  }

  function updateProgress() {
    $("#school-lessons-status").textContent = `Complete all three lessons (${state.lessons.size}/3)`;
    $("#school-lessons-status").dataset.complete = String(state.lessons.size === 3);
    $("#school-project-status").textContent = "Save your first design";
    $("#school-project-status").dataset.complete = String(state.savedDesign);
    $("#school-check-status").textContent = "Pass the two-question check";
    $("#school-check-status").dataset.complete = String(state.passedQuiz);
    $("#school-create-certificate").disabled = !certificateReady();
    if (!certificateReady() && state.certificateName) resetCertificate();
  }

  document.querySelectorAll("[data-school-lesson]").forEach((button) => button.addEventListener("click", () => {
    const id = button.dataset.schoolLesson;
    if (state.lessons.has(id)) state.lessons.delete(id); else state.lessons.add(id);
    const complete = state.lessons.has(id);
    button.setAttribute("aria-pressed", String(complete));
    button.textContent = complete ? "Lesson complete ✓" : "Mark lesson complete";
    updateProgress();
  }));

  $("#school-quiz").addEventListener("submit", (event) => {
    event.preventDefault();
    const answers = new FormData(event.currentTarget);
    const score = Number(answers.get("brief") === "purpose") + Number(answers.get("fabric") === "sample");
    state.passedQuiz = score === 2;
    $("#school-quiz-feedback").dataset.state = state.passedQuiz ? "success" : "error";
    $("#school-quiz-feedback").textContent = state.passedQuiz
      ? "2 / 2 — well considered. Your knowledge check is complete."
      : `${score} / 2 — take another look at the lessons, then try again. Start with the wearer's purpose and check real fabric samples.`;
    updateProgress();
  });

  $("#school-student-name").addEventListener("input", () => {
    if (state.certificateName && $("#school-student-name").value.trim() !== state.certificateName) resetCertificate();
  });

  $("#school-certificate-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if (!certificateReady()) return;
    const name = $("#school-student-name").value.trim();
    if (!name) { $("#school-student-name").focus(); return; }
    state.certificateName = name;
    state.certificateDate = new Intl.DateTimeFormat("en-GB", { dateStyle: "long" }).format(new Date());
    $("#school-certificate-name").textContent = name;
    $("#school-certificate-date").textContent = `Completed ${state.certificateDate}`;
    $("#school-certificate-mark").textContent = "INTRODUCTORY WORKSHOP · COMPLETED";
    $("#school-certificate-actions").hidden = false;
    $("#school-certificate-feedback").dataset.state = "success";
    $("#school-certificate-feedback").textContent = "Your completion certificate is ready. Download the SVG, or print and choose Save as PDF.";
  });

  $("#school-print-certificate").addEventListener("click", () => { if (state.certificateName && certificateReady()) window.print(); });
  $("#school-save-certificate").addEventListener("click", () => {
    if (!state.certificateName || !certificateReady()) return;
    const svg = svgElement("svg", { viewBox: "0 0 1100 780", width: "1100", height: "780", role: "img" });
    svg.append(svgElement("title", {}, "Velora School certificate of completion"));
    svg.append(svgElement("rect", { width: "1100", height: "780", fill: "#f8f4ed" }));
    svg.append(svgElement("rect", { x: "30", y: "30", width: "1040", height: "720", fill: "none", stroke: "#b49a7c" }));
    svg.append(svgElement("rect", { x: "42", y: "42", width: "1016", height: "696", fill: "none", stroke: "#ded7ce" }));
    const text = (y, value, size, family = "Georgia,serif", color = "#292621") => {
      const label = svgElement("text", { x: "550", y: String(y), "text-anchor": "middle", fill: color, "font-family": family, "font-size": String(size) }, value);
      const context = document.createElement("canvas").getContext("2d");
      context.font = `${size}px ${family}`;
      if (context.measureText(value).width > 940) {
        label.setAttribute("textLength", "940");
        label.setAttribute("lengthAdjust", "spacingAndGlyphs");
      }
      svg.append(label);
    };
    text(110, "VELORA SCHOOL", 18, "Arial,sans-serif", "#a64e37");
    text(205, "Certificate of completion", 52);
    text(270, "This is to celebrate", 18, "Arial,sans-serif");
    text(352, state.certificateName, state.certificateName.length > 45 ? 24 : state.certificateName.length > 28 ? 32 : 44);
    text(425, "for completing the Introductory Design Workshop", 24);
    text(475, "Design brief · Color & fabric · Creative presentation", 17, "Arial,sans-serif");
    text(560, `Completed ${state.certificateDate}`, 18, "Arial,sans-serif");
    text(640, "Self-guided learning · Not an accredited qualification", 16, "Arial,sans-serif", "#81796f");
    text(675, "Completion is self-reported and is not independently verified.", 14, "Arial,sans-serif", "#81796f");
    downloadSVG(svg, "velora-school-completion-certificate.svg");
  });

  const courses = {
    foundations: { title: "Fashion Foundations", description: "A beginner pathway for turning a loose idea into a considered garment concept. Planned launch price: €29.", modules: ["Write a clear design brief", "Explore silhouette and proportion", "Develop a color and fabric direction", "Present your first garment concept"] },
    collection: { title: "The Collection Studio", description: "Develop a consistent visual story across a small capsule collection. Planned launch price: €59.", modules: ["Find a theme and point of view", "Build a focused moodboard", "Choose a working palette", "Explore a family of silhouettes", "Plan a three-look capsule", "Edit and present the collection"] },
    portfolio: { title: "Portfolio & Presentation", description: "A pathway for communicating your decisions as clearly as your designs. Planned launch price: €99.", modules: ["Define your audience", "Select your strongest work", "Document your process", "Refine sketches and captions", "Choose a clear page layout", "Write a concise creative statement", "Build the project sequence", "Review and present your portfolio"] },
  };
  const dialog = $("#school-course-dialog");
  document.querySelectorAll("[data-school-course]").forEach((button) => button.addEventListener("click", () => {
    const course = courses[button.dataset.schoolCourse];
    $("#school-dialog-title").textContent = course.title;
    $("#school-dialog-description").textContent = course.description;
    $("#school-dialog-modules").replaceChildren(...course.modules.map((module) => { const li = document.createElement("li"); li.textContent = module; return li; }));
    dialog.showModal();
  }));
  $("#school-dialog-close").addEventListener("click", () => dialog.close());
  $("#school-dialog-start").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => {
    const box = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom)) dialog.close();
  });

  setStudioView("3d");
  renderDesign();
  updateProgress();
})();
