/* Product photo zoom and linked catalog items. Originals load only after opening zoom. */
(() => {
  "use strict";
  const currency = new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR" });
  const controllers = new Set();
  let sequence = 0, viewer = null;
  const clamp = (value, minimum, maximum) => Math.max(minimum, Math.min(maximum, value));
  function node(tag, className, text) {
    const value = document.createElement(tag);
    if (className) value.className = className;
    if (text !== undefined) value.textContent = text;
    return value;
  }
  function photoUrl(value) {
    if (typeof value !== "string" || !value) return null;
    try {
      const url = new URL(value, location.href);
      if (url.origin !== location.origin || !["http:", "https:"].includes(url.protocol) || !url.pathname.startsWith("/assets/") || url.username || url.password) return null;
      return url;
    } catch { return null; }
  }
  function selfProductLink(value, productId) {
    if (typeof value !== "string" || !/^[a-zA-Z0-9_-]{1,64}$/.test(productId || "")) return "";
    try {
      const url = new URL(value, location.href);
      return url.origin === location.origin && ["http:", "https:"].includes(url.protocol) && !url.username && !url.password
        && url.pathname === new URL("product.html", location.href).pathname && url.searchParams.get("id") === productId ? value : "";
    } catch { return ""; }
  }
  function safeHotspots(points, source) {
    const photo = photoUrl(source);
    if (!photo || !Array.isArray(points)) return [];
    return points.filter((point) => {
      const target = point?.product, targetPhoto = photoUrl(point?.image);
      return target && targetPhoto?.pathname === photo.pathname && /^[a-zA-Z0-9_-]{1,64}$/.test(target.id || "")
        && typeof target.name === "string" && target.name.trim() && Number.isFinite(target.price) && target.price >= 0
        && Number.isFinite(point.x) && Number.isFinite(point.y) && point.x >= 0 && point.x <= 1 && point.y >= 0 && point.y <= 1;
    }).slice(0, 24);
  }
  function pictureBounds(image, relativeTo) {
    const rect = image.getBoundingClientRect(), parent = relativeTo.getBoundingClientRect();
    if (!rect.width || !rect.height || !image.naturalWidth || !image.naturalHeight || image.hidden) return null;
    const style = getComputedStyle(image), px = (name) => parseFloat(style[name]) || 0;
    const borderX = px("borderLeftWidth"), borderY = px("borderTopWidth");
    const paddingX = px("paddingLeft"), paddingY = px("paddingTop");
    const width = rect.width - borderX - px("borderRightWidth") - paddingX - px("paddingRight");
    const height = rect.height - borderY - px("borderBottomWidth") - paddingY - px("paddingBottom");
    let scaleX = width / image.naturalWidth, scaleY = height / image.naturalHeight;
    if (["contain", "cover", "scale-down", "none"].includes(style.objectFit)) {
      let scale = style.objectFit === "cover" ? Math.max(scaleX, scaleY) : Math.min(scaleX, scaleY);
      if (style.objectFit === "none") scale = 1;
      if (style.objectFit === "scale-down") scale = Math.min(1, scale);
      scaleX = scaleY = scale;
    }
    const renderedWidth = image.naturalWidth * scaleX, renderedHeight = image.naturalHeight * scaleY;
    // Product photos use centered object positioning. Percent positions are honored for other consumers.
    const positions = style.objectPosition.split(/\s+/), fraction = (part) => part?.endsWith("%") ? parseFloat(part) / 100 : .5;
    return {
      left: rect.left - parent.left + borderX + paddingX + (width - renderedWidth) * fraction(positions[0]),
      top: rect.top - parent.top + borderY + paddingY + (height - renderedHeight) * fraction(positions[1] || positions[0]),
      width: renderedWidth, height: renderedHeight,
      clipLeft: rect.left - parent.left + borderX + paddingX, clipTop: rect.top - parent.top + borderY + paddingY,
      clipWidth: width, clipHeight: height,
    };
  }
  function hotspotLayer(parent) {
    const layer = node("div", "vpi-hotspots"), card = node("div", "vpi-item-card");
    const cardId = `vpi-item-${++sequence}`;
    card.id = cardId; card.hidden = true; card.setAttribute("role", "group");
    layer.setAttribute("aria-label", "Shop items in this photograph");
    layer.append(card); parent.append(layer);
    let points = [], bounds = null, active = -1, buttons = [], suppressFocus = false, context = {}, labelBoxes = [];
    function placeCardLabel(button, label, x, y, left, right, top, bottom, maximum) {
      const origin = layer.getBoundingClientRect();
      const controls = [...parent.querySelectorAll(":scope > .save-look, :scope > .product-gallery-count, :scope > .product-gallery-controls button, :scope > .product-gallery-thumbnails")]
        .filter((element) => element.getClientRects().length && getComputedStyle(element).visibility !== "hidden")
        .map((element) => { const r = element.getBoundingClientRect(); return { left: r.left - origin.left, right: r.right - origin.left, top: r.top - origin.top, bottom: r.bottom - origin.top }; });
      const dots = points.map((point) => ({ x: bounds.left + point.x * bounds.width, y: bounds.top + point.y * bounds.height }))
        .filter((p) => p.x >= left - 4 && p.x <= right + 4 && p.y >= top - 4 && p.y <= bottom + 4)
        .map((p) => ({ left: p.x - 11, right: p.x + 11, top: p.y - 11, bottom: p.y + 11 }));
      const blocked = [...controls, ...dots, ...labelBoxes];
      const overlaps = (a, b) => a.left < b.right + 4 && a.right > b.left - 4 && a.top < b.bottom + 4 && a.bottom > b.top - 4;
      const sideWidth = Math.min(maximum, Math.max(right - x - 17, x - left - 17));
      let best = null;
      for (const cap of new Set([sideWidth, maximum])) {
        if (cap < 24) continue;
        label.style.maxWidth = `${cap}px`;
        const width = label.offsetWidth, height = label.offsetHeight;
        if (width > right - left || height > bottom - top) continue;
        const positionsX = [...new Set([x + 17, x - 17 - width, x - width / 2, left, right - width]
          .map((value) => clamp(value, left, right - width)))];
        const positionsY = [...new Set([y - height / 2, y - 17 - height, y + 17, top, bottom - height,
          ...blocked.flatMap((r) => [r.top - height - 4, r.bottom + 4])].map((value) => clamp(value, top, bottom - height)))];
        for (const px of positionsX) for (const py of positionsY) {
          const box = { left: px, right: px + width, top: py, bottom: py + height };
          if (blocked.some((r) => overlaps(box, r))) continue;
          const score = Math.abs(py + height / 2 - y) * 1.25 + Math.abs(px + width / 2 - x) * .25 + (maximum - width) * .05;
          if (!best || score < best.score) best = { ...box, cap, score };
        }
      }
      if (!best) {
        label.hidden = true;
        if (controls.some((r) => x >= r.left && x <= r.right && y >= r.top && y <= r.bottom)) button.hidden = true;
        return;
      }
      label.style.maxWidth = `${best.cap}px`; label.style.left = `${best.left - x + 22}px`; label.style.right = "auto";
      label.style.top = `${best.top + label.offsetHeight / 2 - y + 22}px`;
      button.classList.toggle("vpi-label-left", (best.left + best.right) / 2 < x);
      labelBoxes.push(best);
    }
    function placeLabel(button, x, y) {
      const label = button.querySelector(".vpi-marker-label");
      if (!bounds || !label || button.hidden) return;
      const left = Math.max(bounds.left, bounds.clipLeft) + 4, right = Math.min(bounds.left + bounds.width, bounds.clipLeft + bounds.clipWidth) - 4;
      const top = Math.max(bounds.top, bounds.clipTop) + 4, bottom = Math.min(bounds.top + bounds.height, bounds.clipTop + bounds.clipHeight) - 4;
      const maximum = parseFloat(getComputedStyle(layer).getPropertyValue("--vpi-label-width")) || 132;
      const onRight = Math.max(0, right - x - 17), onLeft = Math.max(0, x - left - 17);
      label.hidden = false; label.style.maxWidth = `${maximum}px`;
      const flip = onRight < label.offsetWidth && onLeft > onRight;
      button.classList.toggle("vpi-label-left", flip);
      label.style.maxWidth = `${Math.min(maximum, flip ? onLeft : onRight)}px`;
      const height = label.offsetHeight;
      label.hidden = Math.max(onLeft, onRight) < 24 || bottom - top < height;
      label.style.top = `${22 + clamp(y, top + height / 2, bottom - height / 2) - y}px`;
      if (parent.classList.contains("vpi-labels-only") && !label.hidden) placeCardLabel(button, label, x, y, left, right, top, bottom, maximum);
    }
    function close(refocus = false) {
      layer.classList.remove("is-item-open");
      if (active < 0) return;
      const button = buttons[active];
      buttons.forEach((item) => item.setAttribute("aria-expanded", "false"));
      active = -1; card.hidden = true;
      if (refocus) { suppressFocus = true; button?.focus({ preventScroll: true }); suppressFocus = false; }
    }
    function placeCard() {
      if (active < 0 || !bounds) return;
      const point = points[active], maxWidth = Math.max(100, bounds.clipWidth - 16);
      card.style.width = `${Math.min(250, maxWidth)}px`;
      card.style.maxHeight = `${Math.max(1, bounds.clipHeight - 16)}px`;
      const width = card.offsetWidth, height = card.offsetHeight;
      const anchorX = bounds.left + point.x * bounds.width, anchorY = bounds.top + point.y * bounds.height;
      const desiredTop = point.y > .55 ? anchorY - height - 21 : anchorY + 21;
      card.style.left = `${clamp(anchorX - width / 2, bounds.clipLeft + 8, bounds.clipLeft + bounds.clipWidth - width - 8)}px`;
      card.style.top = `${clamp(desiredTop, bounds.clipTop + 8, Math.max(bounds.clipTop + 8, bounds.clipTop + bounds.clipHeight - height - 8))}px`;
    }
    function show(index) {
      if (!bounds || !points[index]) return;
      active = index;
      buttons.forEach((button, i) => button.setAttribute("aria-expanded", String(i === index)));
      const point = points[index], target = point.product;
      const eyebrow = node("span", "vpi-item-label", typeof point.label === "string" && point.label.trim() ? point.label.trim() : "Shop this item");
      const name = node("strong", "vpi-item-name", target.name);
      const price = node("span", "vpi-item-price", currency.format(target.price));
      const link = node("a", "vpi-item-link", "View item ↗");
      link.href = (target.id === context.productId && selfProductLink(context.selfLink, context.productId))
        || `product.html?id=${encodeURIComponent(target.id)}${photoUrl(target.item_image) ? "&view=item" : ""}`;
      card.setAttribute("aria-label", `${target.name}, ${currency.format(target.price)}`);
      card.replaceChildren(eyebrow, name, price, link); card.hidden = false; card.scrollTop = 0; layer.classList.add("is-item-open");
      placeCard();
    }
    function update(nextPoints, nextBounds, nextContext = {}) {
      close(); points = nextPoints; bounds = nextBounds; context = nextContext; labelBoxes = [];
      buttons.forEach((button) => button.remove()); buttons = [];
      layer.hidden = !bounds || !points.length;
      points.forEach((point, index) => {
        const x = bounds ? bounds.left + point.x * bounds.width : 0, y = bounds ? bounds.top + point.y * bounds.height : 0;
        const button = node("button", "vpi-marker");
        button.type = "button"; button.setAttribute("aria-expanded", "false"); button.setAttribute("aria-controls", cardId);
        button.setAttribute("aria-label", `${point.label || point.product.name}, ${currency.format(point.product.price)}. Show item details`);
        button.style.left = `${x - 22}px`; button.style.top = `${y - 22}px`;
        const offscreen = !bounds || x < bounds.clipLeft || x > bounds.clipLeft + bounds.clipWidth || y < bounds.clipTop || y > bounds.clipTop + bounds.clipHeight;
        button.hidden = offscreen;
        button.append(node("span", "vpi-marker-dot", "+"));
        const label = node("span", "vpi-marker-label", typeof point.label === "string" && point.label.trim() ? point.label.trim() : point.product.name);
        label.setAttribute("aria-hidden", "true"); button.append(label);
        button.addEventListener("click", (event) => { event.stopPropagation(); show(index); });
        button.addEventListener("pointerenter", (event) => { if (event.pointerType === "mouse") show(index); });
        button.addEventListener("focus", () => { if (!suppressFocus) show(index); });
        layer.insertBefore(button, card); buttons.push(button); placeLabel(button, x, y);
      });
    }
    function relayout(nextBounds) {
      bounds = nextBounds;
      layer.hidden = !bounds || !points.length;
      if (!bounds) { close(); return; }
      labelBoxes = [];
      points.forEach((point, index) => {
        const x = bounds.left + point.x * bounds.width, y = bounds.top + point.y * bounds.height;
        buttons[index].style.left = `${x - 22}px`; buttons[index].style.top = `${y - 22}px`;
        buttons[index].hidden = x < bounds.clipLeft || x > bounds.clipLeft + bounds.clipWidth || y < bounds.clipTop || y > bounds.clipTop + bounds.clipHeight;
        placeLabel(buttons[index], x, y);
      });
      if (active >= 0 && buttons[active]?.hidden) close();
      else placeCard();
    }
    layer.addEventListener("focusout", (event) => { if (!layer.contains(event.relatedTarget)) close(); });
    layer.addEventListener("keydown", (event) => { if (event.key === "Escape" && active >= 0) { event.preventDefault(); event.stopPropagation(); close(true); } });
    const outside = (event) => { if (!layer.contains(event.target)) close(); };
    document.addEventListener("pointerdown", outside);
    return { update, relayout, close, destroy() { document.removeEventListener("pointerdown", outside); layer.remove(); } };
  }

  function createViewer() {
    const dialog = node("dialog", "vpi-dialog"); dialog.id = "velora-photo-inspector";
    dialog.setAttribute("aria-labelledby", "vpi-viewer-title");
    const header = node("div", "vpi-header"), title = node("h2", "", "A closer look"); title.id = "vpi-viewer-title";
    const close = node("button", "vpi-close", "×"); close.type = "button"; close.setAttribute("aria-label", "Close photo zoom");
    header.append(title, close);
    const toolbar = node("div", "vpi-toolbar"), minus = node("button", "", "−"), plus = node("button", "", "+"), fit = node("button", "vpi-fit", "Fit photo"), amount = node("output", "vpi-amount", "100%");
    [minus, fit, plus].forEach((button) => { button.type = "button"; });
    minus.setAttribute("aria-label", "Zoom out"); plus.setAttribute("aria-label", "Zoom in"); amount.setAttribute("aria-live", "polite");
    toolbar.append(minus, amount, plus, fit);
    const hint = node("p", "vpi-hint", "Zoom in, then drag or scroll to explore. Select an object label to view its price and details."); hint.id = "vpi-viewer-hint";
    const viewport = node("div", "vpi-viewport"), canvas = node("div", "vpi-canvas"), picture = node("div", "vpi-picture"), image = node("img", "vpi-original");
    image.dataset.photoOriginal = "true"; image.draggable = false;
    viewport.tabIndex = 0; viewport.setAttribute("role", "region"); viewport.setAttribute("aria-label", "Enlarged product photograph"); viewport.setAttribute("aria-describedby", hint.id);
    picture.append(image); canvas.append(picture); viewport.append(canvas);
    const state = node("p", "vpi-load-state", "Loading full-resolution photograph…"); state.setAttribute("role", "status");
    dialog.append(header, toolbar, hint, state, viewport); document.body.append(dialog);
    const hotspots = hotspotLayer(picture);
    let owner = null, options = null, previousFocus = null, zoom = 1, baseWidth = 0, baseHeight = 0, dragging = null;
    function visiblePicture() {
      const photo = picture.getBoundingClientRect(), view = viewport.getBoundingClientRect();
      const left = Math.max(0, view.left - photo.left), top = Math.max(0, view.top - photo.top);
      return { left: 0, top: 0, width: baseWidth * zoom, height: baseHeight * zoom,
        clipLeft: left, clipTop: top, clipWidth: Math.max(0, Math.min(photo.width, view.right - photo.left) - left),
        clipHeight: Math.max(0, Math.min(photo.height, view.bottom - photo.top) - top) };
    }
    function layout(preserveCenter = false) {
      if (!dialog.open || !image.complete || !image.naturalWidth) return;
      const width = Math.max(80, viewport.clientWidth - 32), height = Math.max(100, viewport.clientHeight - 32);
      const scale = Math.min(width / image.naturalWidth, height / image.naturalHeight, 1);
      baseWidth = image.naturalWidth * scale; baseHeight = image.naturalHeight * scale;
      const center = { x: (viewport.scrollLeft + viewport.clientWidth / 2) / Math.max(canvas.offsetWidth, 1), y: (viewport.scrollTop + viewport.clientHeight / 2) / Math.max(canvas.offsetHeight, 1) };
      picture.style.width = `${baseWidth * zoom}px`; picture.style.height = `${baseHeight * zoom}px`;
      canvas.style.width = `${Math.max(viewport.clientWidth, baseWidth * zoom + 32)}px`;
      canvas.style.height = `${Math.max(viewport.clientHeight, baseHeight * zoom + 32)}px`;
      amount.value = `${Math.round(zoom * 100)}%`; amount.textContent = amount.value;
      minus.disabled = zoom <= 1; plus.disabled = zoom >= 4; fit.disabled = zoom === 1;
      viewport.classList.toggle("is-zoomed", zoom > 1);
      if (preserveCenter) viewport.scrollTo(center.x * canvas.offsetWidth - viewport.clientWidth / 2, center.y * canvas.offsetHeight - viewport.clientHeight / 2);
      else viewport.scrollTo(0, 0);
      hotspots.relayout(visiblePicture());
    }
    function zoomTo(value) { zoom = clamp(value, 1, 4); hotspots.close(); layout(true); }
    image.addEventListener("load", () => {
      if (!dialog.open) return;
      state.hidden = true; viewport.hidden = false; toolbar.hidden = false;
      layout();
      hotspots.update(safeHotspots(options?.hotspots, options?.src), visiblePicture(), options);
    });
    image.addEventListener("error", () => {
      if (!dialog.open) return;
      state.textContent = "This full-resolution photograph couldn't load. Close and open it to try again."; state.hidden = false;
      viewport.hidden = true; toolbar.hidden = true; hotspots.update([], null);
    });
    close.addEventListener("click", () => dialog.close());
    plus.addEventListener("click", () => zoomTo(zoom + .5)); minus.addEventListener("click", () => zoomTo(zoom - .5)); fit.addEventListener("click", () => zoomTo(1));
    dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener("close", () => {
      image.removeAttribute("src"); hotspots.update([], null); owner = null; options = null; dragging = null;
      if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true });
    });
    dialog.addEventListener("keydown", (event) => {
      if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); dialog.close(); }
      else if (event.target === viewport && ["+", "=", "-", "0"].includes(event.key)) {
        event.preventDefault(); zoomTo(event.key === "0" ? 1 : zoom + (event.key === "-" ? -.5 : .5));
      }
    });
    viewport.addEventListener("pointerdown", (event) => {
      if (zoom <= 1 || event.button !== 0 || event.pointerType === "touch" || event.target.closest("button,a,.vpi-item-card")) return;
      dragging = { pointer: event.pointerId, x: event.clientX, y: event.clientY, left: viewport.scrollLeft, top: viewport.scrollTop };
      viewport.setPointerCapture(event.pointerId); viewport.classList.add("is-dragging");
    });
    viewport.addEventListener("pointermove", (event) => {
      if (!dragging || dragging.pointer !== event.pointerId) return;
      viewport.scrollLeft = dragging.left - event.clientX + dragging.x; viewport.scrollTop = dragging.top - event.clientY + dragging.y;
    });
    viewport.addEventListener("scroll", () => { if (dialog.open) hotspots.relayout(visiblePicture()); }, { passive: true });
    const stopDrag = () => { dragging = null; viewport.classList.remove("is-dragging"); };
    viewport.addEventListener("pointerup", stopDrag); viewport.addEventListener("pointercancel", stopDrag);
    const resize = new ResizeObserver(() => layout(true)); resize.observe(viewport);
    return {
      open(controller, data, trigger) {
        const source = photoUrl(data.src);
        if (!source) return;
        owner = controller; options = data; previousFocus = trigger || document.activeElement; zoom = 1;
        title.textContent = data.title || "A closer look"; image.alt = data.alt || data.title || "Product photograph";
        state.textContent = "Loading full-resolution photograph…"; state.hidden = false; viewport.hidden = true; toolbar.hidden = true;
        hotspots.update([], null); if (!dialog.open) dialog.showModal(); close.focus({ preventScroll: true }); image.src = source.href;
      },
      closeOwner(controller) { if (owner === controller && dialog.open) dialog.close(); },
    };
  }

  function mount({ frame, image, trigger, labelsOnly = false }) {
    if (!(frame instanceof HTMLElement) || !(image instanceof HTMLImageElement)) throw new TypeError("A photo frame and image are required.");
    let options = { src: "", alt: "", title: "", hotspots: [], productId: "", selfLink: "" }, destroyed = false;
    frame.classList.add("vpi-frame"); frame.classList.toggle("vpi-labels-only", labelsOnly);
    if (!labelsOnly) image.classList.add("vpi-photo");
    const ownButton = !labelsOnly && !(trigger instanceof HTMLButtonElement);
    const openButton = labelsOnly ? null : ownButton ? node("button", "vpi-open", "Zoom photo ↗") : trigger;
    if (openButton) { openButton.type = "button"; openButton.setAttribute("aria-haspopup", "dialog"); openButton.disabled = true; }
    if (ownButton) frame.append(openButton);
    const hotspots = hotspotLayer(frame);
    function ready() { return Boolean(!image.hidden && image.complete && image.naturalWidth && frame.getBoundingClientRect().width && frame.dataset.photoState !== "error" && frame.dataset.photoState !== "loading"); }
    function layout() {
      if (destroyed) return;
      const isReady = ready();
      if (openButton) { openButton.disabled = !isReady; openButton.hidden = !isReady; }
      hotspots.relayout(isReady ? pictureBounds(image, frame) : null);
    }
    const controller = {
      update(data = {}) {
        options = { src: data.src || "", alt: data.alt || "", title: data.title || "", hotspots: Array.isArray(data.hotspots) ? data.hotspots : [],
          productId: data.productId || "", selfLink: data.selfLink || "" };
        hotspots.update(safeHotspots(options.hotspots, options.src), ready() ? pictureBounds(image, frame) : null, options); layout();
      },
      open(trigger = openButton) {
        if (labelsOnly || destroyed || !ready() || !photoUrl(options.src)) return;
        if (!viewer) viewer = createViewer(); viewer.open(controller, options, trigger);
      },
      destroy() {
        if (destroyed) return; destroyed = true; viewer?.closeOwner(controller);
        resize.disconnect(); changes.disconnect(); image.removeEventListener("load", layout); image.removeEventListener("error", layout); image.removeEventListener("click", clickImage);
        openButton?.removeEventListener("click", clickButton); if (ownButton) openButton.remove(); hotspots.destroy(); frame.classList.remove("vpi-frame", "vpi-labels-only"); image.classList.remove("vpi-photo"); controllers.delete(controller);
      },
    };
    function clickImage(event) { if (!event.defaultPrevented && event.button === 0) controller.open(openButton); }
    function clickButton() { controller.open(openButton); }
    if (!labelsOnly) image.addEventListener("click", clickImage);
    openButton?.addEventListener("click", clickButton);
    image.addEventListener("load", layout); image.addEventListener("error", layout);
    const resize = new ResizeObserver(layout); resize.observe(frame); resize.observe(image);
    const changes = new MutationObserver(layout); changes.observe(image, { attributes: true, attributeFilter: ["src", "srcset", "hidden", "style"] }); changes.observe(frame, { attributes: true, attributeFilter: ["data-photo-state"] });
    controllers.add(controller); layout(); return controller;
  }
  window.VeloraImageInspector = Object.freeze({ mount });
})();
