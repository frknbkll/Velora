/* Place shoppable markers on an exact product photograph. All values remain in the product editor until saved. */
(() => {
  "use strict";
  const limit = 288, photoLimit = 24;
  let instance = 0;
  const euro = new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR" });
  const copy = (value) => JSON.parse(JSON.stringify(value));
  const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);

  function assetPath(value) {
    if (typeof value !== "string" || value.length > 2000) return "";
    try {
      const url = new URL(value, location.href);
      if (url.origin !== location.origin || !url.pathname.startsWith("/assets/") || url.username || url.password) return "";
      return url.pathname.slice(1);
    } catch { return ""; }
  }
  function node(tag, className = "", text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }
  function action(text, className = "admin-button admin-button-secondary") {
    const button = node("button", className, text); button.type = "button"; return button;
  }
  function field(text, control) {
    const label = node("label", "admin-field admin-hotspot-field", text);
    label.append(control); return label;
  }

  function mount(container, options = {}) {
    if (!(container instanceof Element)) throw new TypeError("Choose a container for the image marker editor.");
    const prefix = `admin-hotspot-${++instance}`;
    const state = { products: [], photos: [], hotspots: [], disabled: false, selected: -1, pending: false, source: "", loaded: false };
    const intro = node("p", "admin-field-hint admin-hotspot-intro", "Choose a photo, click the bag, shoes, scarf or other object, then link its published product and add a marker. Shoppers see that product's current price. Each photo keeps its own markers.");
    const photoSelect = node("select"); photoSelect.id = `${prefix}-photo`; photoSelect.dataset.hotspotControl = "photo";
    const photoField = field("Photograph", photoSelect);
    const preview = node("div", "admin-hotspot-preview");
    const image = node("img"); image.alt = "Product photograph for placing shopping markers"; image.draggable = false;
    const markers = node("div", "admin-hotspot-marker-layer");
    const empty = node("p", "admin-hotspot-preview-empty", "Upload a product photo to place markers.");
    preview.append(image, markers, empty);
    const instructions = node("p", "admin-field-hint", "Click a location in the photograph, or enter its horizontal and vertical position below. Positions are percentages of the original image.");
    const position = node("div", "admin-field-row admin-hotspot-position");
    const x = node("input"), y = node("input");
    for (const [control, name] of [[x, "x"], [y, "y"]]) {
      control.id = `${prefix}-${name}`; control.dataset.hotspotControl = name; control.type = "number"; control.min = "0"; control.max = "100"; control.step = "0.1"; control.value = "50"; control.inputMode = "decimal";
    }
    position.append(field("Horizontal position (%)", x), field("Vertical position (%)", y));
    const target = node("select"); target.id = `${prefix}-product`; target.dataset.hotspotControl = "product";
    const targetField = field("Linked product", target);
    const targetHint = node("p", "admin-field-hint", "Only published products are offered. Add a bag, pair of shoes or scarf to Products first, then link it here.");
    const label = node("input"); label.id = `${prefix}-label`; label.dataset.hotspotControl = "label"; label.type = "text"; label.maxLength = 80; label.placeholder = "For example: Bag or Scarf";
    const labelField = field("Object label (optional)", label);
    const toolbar = node("div", "admin-hotspot-edit-actions");
    const save = action("Add marker", "admin-button"), cancel = action("Cancel marker edit");
    save.dataset.hotspotAction = "save"; cancel.dataset.hotspotAction = "cancel";
    toolbar.append(save, cancel);
    const feedback = node("p", "admin-hotspot-feedback"); feedback.id = `${prefix}-feedback`; feedback.setAttribute("role", "status"); feedback.setAttribute("aria-live", "polite");
    const heading = node("div", "admin-hotspot-list-heading");
    const count = node("strong", "", `0 of ${photoLimit} markers on this photo · 0 of ${limit} total`); heading.append(count);
    const list = node("div", "admin-hotspot-list");
    container.classList.add("admin-image-hotspots");
    container.append(intro, photoField, preview, instructions, position, targetField, targetHint, labelField, toolbar, feedback, heading, list);

    function changed() { if (typeof options.onChange === "function") options.onChange(); }
    function publishedProducts() { return state.products.filter((product) => product.published && !product.deleted_at); }
    function currentProduct(id) { return state.products.find((product) => String(product.id) === String(id)); }
    function photoCount(excludeSelected = false) {
      return state.hotspots.filter((spot, index) => assetPath(spot.image) === state.source && (!excludeSelected || index !== state.selected)).length;
    }
    function message(text, error = false) { feedback.textContent = text; feedback.classList.toggle("is-error", error); }
    function pointFromControls() {
      const horizontal = Number(x.value), vertical = Number(y.value);
      if (x.value === "" || y.value === "" || !Number.isFinite(horizontal) || !Number.isFinite(vertical)
          || horizontal < 0 || horizontal > 100 || vertical < 0 || vertical > 100) return null;
      return { x: Math.round(horizontal * 1000) / 100000, y: Math.round(vertical * 1000) / 100000 };
    }
    function containedBounds() {
      if (!state.loaded || !image.naturalWidth || !image.naturalHeight) return null;
      const rect = image.getBoundingClientRect(), holder = preview.getBoundingClientRect();
      const scale = Math.min(rect.width / image.naturalWidth, rect.height / image.naturalHeight);
      const width = image.naturalWidth * scale, height = image.naturalHeight * scale;
      return { left: rect.left + (rect.width - width) / 2, top: rect.top + (rect.height - height) / 2, width, height,
        offsetX: rect.left - holder.left + (rect.width - width) / 2, offsetY: rect.top - holder.top + (rect.height - height) / 2 };
    }
    function place(button, point, bounds) {
      button.style.left = `${bounds.offsetX + point.x * bounds.width}px`;
      button.style.top = `${bounds.offsetY + point.y * bounds.height}px`;
    }
    function renderMarkers() {
      markers.replaceChildren();
      const bounds = containedBounds();
      if (!bounds || !state.source) return;
      state.hotspots.forEach((spot, index) => {
        if (assetPath(spot.image) !== state.source) return;
        const button = action(String(index + 1), "admin-hotspot-dot");
        button.dataset.hotspotIndex = String(index);
        button.classList.toggle("is-selected", state.selected === index);
        button.setAttribute("aria-label", `Edit marker ${index + 1}: ${spot.label || currentProduct(spot.product_id)?.name || "Linked item"}`);
        button.disabled = state.disabled;
        place(button, spot, bounds);
        button.addEventListener("click", (event) => { event.stopPropagation(); edit(index); });
        markers.append(button);
      });
      const pending = pointFromControls();
      if (state.pending && pending) {
        const dot = node("span", "admin-hotspot-pending", "+");
        dot.setAttribute("aria-hidden", "true"); place(dot, pending, bounds); markers.append(dot);
      }
    }
    function syncDisabled() {
      const unavailable = state.disabled || !state.photos.length;
      photoSelect.disabled = unavailable;
      for (const control of [x, y, target, label]) control.disabled = unavailable;
      save.disabled = unavailable || photoCount(true) >= photoLimit || (state.selected < 0 && state.hotspots.length >= limit);
      cancel.disabled = unavailable || (!state.pending && state.selected < 0);
      list.querySelectorAll("button").forEach((button) => { button.disabled = state.disabled; });
      preview.classList.toggle("is-disabled", unavailable);
      preview.setAttribute("aria-disabled", String(unavailable));
      container.setAttribute("aria-busy", String(state.disabled));
    }
    function syncDraft() {
      save.textContent = state.selected < 0 ? "Add marker" : "Update marker";
      syncDisabled(); renderMarkers();
    }
    function clearPending(notify = true) {
      state.selected = -1; state.pending = false;
      x.value = "50"; y.value = "50"; target.value = ""; label.value = "";
      message(""); syncDraft(); renderList();
      if (notify) changed();
    }
    function renderTargets() {
      const value = target.value;
      target.replaceChildren(new Option("Choose a published product", ""));
      for (const product of publishedProducts()) {
        const price = Number(product.price);
        target.add(new Option(`${product.name} · ${Number.isFinite(price) ? euro.format(price) : "Price unavailable"}`, String(product.id)));
      }
      if (value && !publishedProducts().some((product) => String(product.id) === value)) {
        const option = new Option("Linked product is not published — choose another", value); option.disabled = true; target.add(option);
      }
      target.value = value;
    }
    function showPhoto(source) {
      if (state.source === source && image.getAttribute("src")) { renderMarkers(); return; }
      state.source = source; state.loaded = false; markers.replaceChildren();
      image.hidden = !source; empty.hidden = Boolean(source);
      if (!source) {
        image.removeAttribute("src"); image.removeAttribute("srcset"); delete image.dataset.originalSrc;
        empty.textContent = "Upload a product photo to place markers.";
        return;
      }
      if (window.VeloraImageSources) window.VeloraImageSources.apply(image, source, "(max-width: 760px) 100vw, 450px");
      else image.src = source;
    }
    function renderPhotos() {
      const selected = state.photos.some((photo) => photo.image === state.source) ? state.source : state.photos[0]?.image || "";
      photoSelect.replaceChildren();
      if (!state.photos.length) photoSelect.add(new Option("No photographs uploaded", ""));
      state.photos.forEach((photo, index) => photoSelect.add(new Option(photo.label || `Photo ${index + 1}`, photo.image)));
      photoSelect.value = selected; showPhoto(selected);
    }
    function renderList() {
      count.textContent = `${photoCount()} of ${photoLimit} markers on this photo · ${state.hotspots.length} of ${limit} total`;
      list.replaceChildren();
      if (!state.hotspots.length) {
        list.append(node("p", "admin-hotspot-empty", "No shopping markers yet. Link an object to its product to make the photo shoppable."));
        return;
      }
      state.hotspots.forEach((spot, index) => {
        const product = currentProduct(spot.product_id);
        const row = node("div", "admin-hotspot-row"); row.classList.toggle("is-selected", index === state.selected);
        const number = node("span", "admin-hotspot-number", String(index + 1));
        const description = node("div", "admin-hotspot-copy");
        description.append(node("strong", "", spot.label || product?.name || "Linked item"));
        const photo = state.photos.find((item) => item.image === assetPath(spot.image));
        const price = product && product.published && !product.deleted_at ? euro.format(Number(product.price) || 0) : "Product is not publicly available";
        description.append(node("span", "", `${price} · ${photo?.label || "Photo"} · ${Math.round(spot.x * 100)}%, ${Math.round(spot.y * 100)}%`));
        const actions = node("div", "admin-hotspot-row-actions");
        const editButton = action("Edit"), removeButton = action("Remove");
        editButton.dataset.hotspotAction = "edit"; removeButton.dataset.hotspotAction = "remove";
        editButton.setAttribute("aria-label", `Edit marker ${index + 1}`); removeButton.setAttribute("aria-label", `Remove marker ${index + 1}`);
        editButton.addEventListener("click", () => edit(index));
        removeButton.addEventListener("click", () => {
          if (state.disabled) return;
          state.hotspots.splice(index, 1);
          if (state.selected === index) clearPending(false);
          else if (state.selected > index) state.selected -= 1;
          renderList(); syncDraft(); message("Marker removed. Save the product to keep this change."); changed();
        });
        actions.append(editButton, removeButton); row.append(number, description, actions); list.append(row);
      });
      syncDisabled();
    }
    function edit(index) {
      if (state.disabled) return;
      const spot = state.hotspots[index]; if (!spot) return;
      if (!state.photos.some((photo) => photo.image === assetPath(spot.image))) {
        message("This marker's photo is no longer in the gallery. Remove the marker or add the photo again.", true); return;
      }
      state.selected = index; state.pending = false;
      photoSelect.value = assetPath(spot.image); showPhoto(photoSelect.value);
      x.value = String(Math.round(spot.x * 1000) / 10); y.value = String(Math.round(spot.y * 1000) / 10);
      target.value = String(spot.product_id); label.value = spot.label || "";
      renderTargets(); target.value = String(spot.product_id);
      message("Move this marker or change its product, then choose Update marker.");
      renderList(); syncDraft(); target.focus({ preventScroll: true });
    }
    function markPending() {
      if (state.disabled) return;
      state.pending = true; message("Choose Add marker or Update marker to keep this location and linked product."); syncDraft(); changed();
    }
    preview.addEventListener("click", (event) => {
      if (state.disabled || event.target.closest("button")) return;
      const bounds = containedBounds(); if (!bounds) return;
      const nx = (event.clientX - bounds.left) / bounds.width, ny = (event.clientY - bounds.top) / bounds.height;
      if (nx < 0 || nx > 1 || ny < 0 || ny > 1) return;
      x.value = String(Math.round(nx * 1000) / 10); y.value = String(Math.round(ny * 1000) / 10); markPending();
    });
    image.addEventListener("load", () => { state.loaded = true; image.hidden = false; empty.hidden = true; renderMarkers(); });
    image.addEventListener("error", () => {
      state.loaded = false; image.hidden = true; empty.hidden = false; empty.textContent = "This photograph could not load. You can still position markers with the percentage fields."; markers.replaceChildren();
    });
    photoSelect.addEventListener("change", () => {
      showPhoto(photoSelect.value);
      if (state.selected >= 0 && !state.pending && assetPath(state.hotspots[state.selected]?.image) !== photoSelect.value) {
        state.selected = -1; state.pending = false; x.value = "50"; y.value = "50"; target.value = ""; label.value = "";
        message(""); renderList();
      }
      renderList(); syncDraft(); changed();
    });
    for (const control of [x, y, target, label]) control.addEventListener("input", markPending);
    target.addEventListener("change", markPending);
    save.addEventListener("click", () => {
      if (state.disabled) return;
      const point = pointFromControls();
      if (!state.source || !point) { message("Choose a photograph and positions from 0 to 100%.", true); x.focus(); return; }
      const product = publishedProducts().find((item) => String(item.id) === target.value);
      if (!product) { message("Choose a published product to show its current price.", true); target.focus(); return; }
      if (photoCount(true) >= photoLimit) { message(`A photograph can have up to ${photoLimit} markers. Choose another photo or edit an existing marker.`, true); return; }
      if (state.selected < 0 && state.hotspots.length >= limit) { message(`A product can have up to ${limit} markers across its photographs.`, true); return; }
      const spot = { image: state.source, x: point.x, y: point.y, product_id: String(product.id), label: label.value.trim() };
      if (state.selected < 0) state.hotspots.push(spot); else state.hotspots[state.selected] = spot;
      clearPending(false); renderList(); syncDraft(); message("Marker added to this photo. Save the product to keep your changes."); changed();
    });
    cancel.addEventListener("click", () => clearPending());
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(renderMarkers) : null;
    observer?.observe(preview);
    window.addEventListener("resize", renderMarkers);
    renderTargets(); renderPhotos(); renderList(); syncDraft();
    return {
      set(value = {}) {
        if (own(value, "products")) state.products = Array.isArray(value.products) ? value.products : [];
        if (own(value, "photos")) {
          const seen = new Set();
          state.photos = (Array.isArray(value.photos) ? value.photos : []).map((photo) => typeof photo === "string" ? { image: assetPath(photo), label: "" } : { image: assetPath(photo?.image), label: String(photo?.label || "") })
            .filter((photo) => photo.image && !seen.has(photo.image) && seen.add(photo.image));
        }
        if (own(value, "hotspots")) {
          state.hotspots = copy(Array.isArray(value.hotspots) ? value.hotspots : []).slice(0, limit);
          clearPending(false);
        }
        if (own(value, "disabled")) state.disabled = Boolean(value.disabled);
        renderTargets(); renderPhotos(); renderList(); syncDraft();
      },
      get() { return copy(state.hotspots); },
      snapshot() {
        return { hotspots: copy(state.hotspots), pending: state.pending ? { image: state.source, x: x.value, y: y.value, product_id: target.value, label: label.value } : null };
      },
      hasPending() { return state.pending; },
      clearPending() { clearPending(); },
      setDisabled(disabled) { state.disabled = Boolean(disabled); syncDisabled(); renderMarkers(); },
      destroy() { observer?.disconnect(); window.removeEventListener("resize", renderMarkers); container.replaceChildren(); container.classList.remove("admin-image-hotspots"); },
    };
  }
  window.VeloraAdminImageHotspots = Object.freeze({ mount });
})();
