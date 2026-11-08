(() => {
  "use strict";
  const $ = (selector) => document.querySelector(selector);
  const currency = new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR", maximumFractionDigits: 2 });
  const shortDate = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });
  const sections = ["overview", "products", "customers", "activity", "security", "business", "operations", "support", "folder-access", "discounts"];
  const state = { overview: null, products: [], customers: [], events: [], editing: null, photos: [], colorVariants: [], colorImage: null, colorUploading: false, colorSaving: false, generatingDescription: false, generatingDraft: false, saving: false, uploading: false, editorVersion: 0, trash: null, trashBusy: false };
  let toastTimer;
  let loading;
  let currentSection = null;
  let editorSnapshot = null;
  let discardAction = null;
  let discardFocus = null;
  const mobileNavigation = window.matchMedia("(max-width: 899px)");
  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function icon(name) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "admin-icon"); svg.setAttribute("aria-hidden", "true");
    const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", `#studio-${name}`); svg.append(use); return svg;
  }
  function initials(name) { return String(name || "V").trim().split(/\s+/).slice(0, 2).map((part) => Array.from(part)[0] || "").join("").toUpperCase(); }
  function avatar(name) { const node = element("span", "admin-avatar", initials(name)); node.setAttribute("aria-hidden", "true"); return node; }
  function dateLabel(value, withTime = false) {
    if (!value) return "\u2014";
    const date = new Date(typeof value === "number" ? value * 1000 : value);
    if (Number.isNaN(date.getTime())) return "\u2014";
    return shortDate.format(date) + (withTime ? ` \u00b7 ${date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}` : "");
  }
  function productImage(product, className) { const image = element("img", className); image.src = product.image; image.alt = ""; image.loading = "lazy"; image.decoding = "async"; return image; }
  function showToast(message) { clearTimeout(toastTimer); $("#admin-toast").textContent = message; $("#admin-toast").hidden = false; toastTimer = setTimeout(() => { $("#admin-toast").hidden = true; }, 5500); }
  function showError(error) {
    if (error?.status === 401) { location.replace("login.html?next=admin.html"); return; }
    if (error?.status === 403) { location.replace("account.html"); return; }
    $("#admin-fetch-error-message").textContent = error?.message || "We couldn\u2019t load the studio. Please try again."; $("#admin-fetch-error").hidden = false;
  }
  function editorError(text) { $("#admin-edit-error").textContent = text; $("#admin-edit-error").hidden = !text; }
  function activeProducts() { return state.products.filter((product) => !product.deleted_at); }
  function renderOverview() {
    const overview = state.overview; if (!overview) return;
    $("#admin-total-products").textContent = overview.totalProducts; $("#admin-published-products").textContent = overview.publishedProducts;
    $("#admin-draft-products").textContent = overview.draftProducts; $("#admin-total-customers").textContent = overview.totalCustomers; $("#admin-product-nav-count").textContent = overview.totalProducts;
    $("#admin-low-stock").textContent = overview.lowStockProducts ?? activeProducts().filter((product) => product.stock > 0 && product.stock <= 5).length;
    $("#admin-out-of-stock").textContent = overview.outOfStockProducts ?? activeProducts().filter((product) => product.stock === 0).length;
    $("#admin-trash-count").textContent = overview.trashedProducts ?? state.products.filter((product) => product.deleted_at).length;
    const people = (overview.recentCustomers || []).slice(0, 4).map((customer) => {
      const row = element("div", "admin-recent-person"), copy = element("div");
      copy.append(element("strong", "", customer.name), element("p", "", customer.email));
      const joined = element("time", "", dateLabel(customer.created_at)); joined.dateTime = String(customer.created_at || ""); row.append(avatar(customer.name), copy, joined); return row;
    });
    $("#admin-recent-customers").replaceChildren(...(people.length ? people : [element("p", "admin-empty", "A new community starts here. Customer registrations will appear as soon as someone joins.")]));
    const preview = activeProducts().slice(0, 3).map((product) => { const card = element("article", "admin-preview-item"), copy = element("div"); copy.append(element("h3", "", product.name), element("p", "", product.founder), element("strong", "", currency.format(product.price))); card.append(productImage(product, "admin-preview-image"), copy); return card; });
    $("#admin-product-preview").replaceChildren(...(preview.length ? preview : [element("p", "admin-empty", "Add your first product to begin your collection.")]));
  }
  function actionButton(label, action, id, iconName) {
    const button = element("button", `admin-edit-button${action === "trash" ? " is-danger" : ""}`); button.type = "button"; button.dataset[`${action}Product`] = id;
    const product = state.products.find((item) => item.id === id); button.setAttribute("aria-label", `${label} ${product?.name || "product"}`);
    if (iconName) button.append(icon(iconName)); button.append(element("span", "", label)); return button;
  }
  function renderProducts() {
    const search = $("#admin-product-search").value.trim().toLocaleLowerCase(), visibility = $("#admin-product-filter").value, stockFilter = $("#admin-stock-filter").value;
    const matches = state.products.filter((product) => {
      const visible = visibility === "trash" ? Boolean(product.deleted_at) : !product.deleted_at && (visibility === "all" || (visibility === "published" ? product.published : !product.published));
      const stock = stockFilter === "all" || (stockFilter === "low" && product.stock > 0 && product.stock <= 5) || (stockFilter === "out" && product.stock === 0) || (stockFilter === "untracked" && product.stock == null);
      return visible && stock && `${product.name} ${product.sku || ""} ${product.founder} ${product.collection}`.toLocaleLowerCase().includes(search);
    });
    const sort = $("#admin-product-sort").value;
    matches.sort((a, b) => { if (sort === "name") return a.name.localeCompare(b.name); if (sort === "price-low") return a.price - b.price; if (sort === "price-high") return b.price - a.price; if (sort === "stock") return (a.stock ?? Infinity) - (b.stock ?? Infinity) || a.name.localeCompare(b.name); return String(b.updated_at || "").localeCompare(String(a.updated_at || "")); });
    const rows = matches.map((product) => {
      const row = element("tr"); row.dataset.productId = product.id;
      const nameCell = element("td"), cell = element("div", "admin-product-cell"), copy = element("div");
      copy.append(element("strong", "", product.name), element("small", "", `${product.sku || "No SKU"} \u00b7 ${product.collection.replace(/^THE | EDIT$/g, "")}`));
      const imageCount = product.images?.length || 1; if (imageCount > 1) copy.append(element("span", "admin-photo-count", `${imageCount} photos`));
      cell.append(productImage(product), copy); nameCell.append(cell);
      const statusCell = element("td"); statusCell.append(element("span", `admin-status${!product.deleted_at && product.published ? " is-published" : ""}`, product.deleted_at ? "In trash" : product.published ? "Published" : "Draft"));
      const stockCell = element("td"), tracked = product.stock != null;
      stockCell.append(element("span", `admin-stock-status${product.stock === 0 ? " is-out" : tracked && product.stock <= 5 ? " is-low" : ""}`, tracked ? `${product.stock}${product.stock === 0 ? " \u00b7 Sold out" : product.stock <= 5 ? " \u00b7 Low stock" : " in stock"}` : "Not tracked"));
      const actions = element("td"), buttons = element("div", "admin-row-actions");
      if (product.deleted_at) buttons.append(actionButton("Restore", "restore", product.id, "clock"));
      else buttons.append(actionButton("Edit", "edit", product.id, "edit"), actionButton("Duplicate", "duplicate", product.id, "copy"), actionButton("Trash", "trash", product.id, "trash"));
      actions.append(buttons); row.append(nameCell, element("td", "admin-founder-cell", product.founder), element("td", "admin-price-cell", currency.format(product.price)), stockCell, statusCell, actions);
      [...row.cells].forEach((cell, index) => { cell.dataset.label = ["Product", "Founder", "Price", "Stock", "Visibility", "Actions"][index]; });
      return row;
    });
    $("#admin-products-body").replaceChildren(...rows); $("#admin-products-empty").hidden = matches.length > 0;
    $("#admin-products-empty").textContent = visibility === "trash" && !search ? "Your trash is empty. Removed products can be restored here." : "No products match these filters. Try another search or stock level.";
    const total = visibility === "trash" ? state.products.filter((product) => product.deleted_at).length : activeProducts().length;
    $("#admin-product-count").textContent = `${matches.length} of ${total} products`;
  }
  function renderCustomers() {
    const search = $("#admin-customer-search").value.trim().toLocaleLowerCase(), matches = state.customers.filter((customer) => `${customer.name} ${customer.email}`.toLocaleLowerCase().includes(search));
    const rows = matches.map((customer) => { const row = element("tr"), name = element("td"), copy = element("div", "admin-customer-name"); copy.append(avatar(customer.name), element("span", "", customer.name)); name.append(copy); row.append(name, element("td", "admin-customer-email", customer.email), element("td", "admin-customer-joined", dateLabel(customer.created_at))); return row; });
    $("#admin-customers-body").replaceChildren(...rows); $("#admin-customers-empty").textContent = search ? "No customers match your search. Try another name or email." : "No customers yet. New registrations will appear here."; $("#admin-customers-empty").hidden = matches.length > 0;
    $("#admin-customer-count").textContent = `${matches.length} of ${state.customers.length} customers`; $("#admin-community-count").textContent = `${state.customers.length} ${state.customers.length === 1 ? "customer" : "customers"}`;
  }
  function activityRow(event) {
    const row = element("article", "admin-activity-row"), mark = element("span", "admin-activity-mark"); mark.append(icon(event.action === "trash" || event.action === "delete" ? "trash" : event.action === "create" ? "plus" : "edit"));
    const copy = element("div"), title = element("p"), words = { create: "created", created: "created", update: "updated", updated: "updated", trash: "moved to trash", delete: "moved to trash", restore: "restored", restored: "restored", duplicate: "duplicated", duplicated: "duplicated" };
    title.append(document.createTextNode(`${event.actor_name || "Administrator"} ${words[event.action] || "changed"} `), element("strong", "", event.product_name || "a product"));
    const time = element("time", "", dateLabel(event.created_at, true)); time.dateTime = event.created_at || ""; copy.append(title, time); row.append(mark, copy); return row;
  }
  function renderActivity() {
    $("#admin-activity-list").replaceChildren(...(state.events.length ? state.events.map(activityRow) : [element("p", "admin-empty", "Your studio is ready for its next chapter. Product changes will appear here.")]));
    $("#admin-latest-activity").replaceChildren(...(state.events.length ? state.events.slice(0, 4).map(activityRow) : [element("p", "admin-empty", "The changes you make to your collection will be remembered here.")]));
    $("#admin-activity-count").textContent = `${state.events.length} recent ${state.events.length === 1 ? "change" : "changes"}`;
  }
  function selectSection() {
    const selected = window.veloraCommerceRole === "warehouse" ? "operations" : location.hash.slice(1), section = sections.includes(selected) ? selected : "overview";
    if (currentSection && currentSection !== section && editorIsDirty()) {
      history.replaceState(null, "", `#${currentSection}`);
      requestEditorDiscard(() => { finishCloseEditor(); location.hash = section; });
      return;
    }
    const sectionChanged = currentSection !== null && currentSection !== section;
    currentSection = section;
    sections.forEach((name) => { $(`#admin-${name}`).hidden = name !== section; });
    document.querySelectorAll("[data-admin-section]").forEach((link) => { if (link.dataset.adminSection === section) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current"); });
    const sectionTitle = section === "business" ? "Business details" : section === "folder-access" ? "Velora accounts" : section === "discounts" ? "Discount codes" : section[0].toUpperCase() + section.slice(1);
    $("#admin-breadcrumb").textContent = sectionTitle; document.title = `${sectionTitle} \u2014 Velora admin`;
    $("#admin-menu-current").textContent = sectionTitle;
    closeMobileMenu(false);
    requestAnimationFrame(() => {
      const nav = $(".admin-nav"), current = nav?.querySelector('[aria-current="page"]');
      if (!mobileNavigation.matches && current) {
        const frame = nav.getBoundingClientRect(), item = current.getBoundingClientRect();
        if (item.right > frame.right) nav.scrollLeft += item.right - frame.right;
        else if (item.left < frame.left) nav.scrollLeft += item.left - frame.left;
      }
      if (sectionChanged) {
        window.scrollTo({ top: 0, left: 0, behavior: "instant" });
        const heading = $(`#admin-${section} h1`);
        if (heading) { heading.tabIndex = -1; heading.focus({ preventScroll: true }); }
      }
    });
    document.dispatchEvent(new CustomEvent("velora:admin-section", { detail: { section } }));
  }
  function closeMobileMenu(restoreFocus = false) {
    const toggle = $("#admin-menu-toggle");
    const wasOpen = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", "false");
    $(".admin-sidebar").classList.remove("is-menu-open");
    if (restoreFocus && wasOpen) toggle.focus({ preventScroll: true });
  }
  function editorValues() {
    return JSON.stringify({
      fields: [...$("#admin-edit-form").querySelectorAll("input,select,textarea")]
        .filter((control) => control.type !== "file")
        .map((control) => [control.id || control.name, control.type === "checkbox" ? control.checked : control.value]),
      photos: state.photos,
      colors: state.colorVariants,
    });
  }
  function editorIsDirty() {
    return $("#admin-edit-dialog").open && editorSnapshot !== null && (state.uploading || editorValues() !== editorSnapshot);
  }
  function finishCloseEditor() {
    editorSnapshot = null;
    state.editorVersion += 1;
    state.uploading = false;
    $("#admin-edit-dialog").close();
  }
  function requestEditorDiscard(action) {
    if (state.saving) return;
    if (!editorIsDirty()) { action(); return; }
    if ($("#admin-discard-dialog").open) return;
    discardAction = action;
    discardFocus = document.activeElement;
    $("#admin-discard-dialog").showModal();
    $("#admin-discard-keep").focus();
  }
  function keepEditing() {
    discardAction = null;
    $("#admin-discard-dialog").close();
    if (discardFocus?.isConnected) discardFocus.focus({ preventScroll: true });
    else $("#admin-edit-product-name").focus({ preventScroll: true });
  }
  async function refreshData() {
    if (loading) return loading; $("#admin-data-retry").disabled = true; $("#admin-main").setAttribute("aria-busy", "true");
    loading = (async () => {
      try {
        const [overview, products, customers, activity] = await Promise.all([window.VeloraAuth.request("/api/admin/overview"), window.VeloraAuth.request("/api/admin/products"), window.VeloraAuth.request("/api/admin/customers"), window.VeloraAuth.request("/api/admin/activity")]);
        state.overview = overview; state.products = products.products; state.customers = customers.customers; state.events = activity.events;
        renderOverview(); renderProducts(); renderCustomers(); renderActivity(); $("#admin-fetch-error").hidden = true; return true;
      } catch (error) { showError(error); return false; }
      finally { $("#admin-data-retry").disabled = false; $("#admin-main").removeAttribute("aria-busy"); loading = null; }
    })(); return loading;
  }

  function renderGallery() {
    const cards = state.photos.map((src, index) => {
      const card = element("div", "admin-photo-card"); card.dataset.imageIndex = index;
      const image = element("img"); image.src = src; image.alt = `Product photo ${index + 1}${index === 0 ? ", cover" : ""}`;
      const label = element("span", `admin-photo-label${index === 0 ? " is-cover" : ""}`, index === 0 ? "Cover photo" : `Photo ${index + 1}`);
      const cover = element("button", "admin-photo-cover", index === 0 ? "Cover selected" : "Make cover");
      cover.type = "button"; cover.dataset.imageAction = "cover"; cover.dataset.imageIndex = index; cover.disabled = index === 0 || state.uploading;
      const actions = element("div", "admin-photo-actions");
      [["left", "\u2190", "Move photo earlier"], ["right", "\u2192", "Move photo later"], ["remove", "\u00d7", "Remove photo"]].forEach(([action, text, name]) => {
        const button = element("button", "", text); button.type = "button"; button.dataset.imageAction = action; button.dataset.imageIndex = index;
        button.setAttribute("aria-label", `${name} ${index + 1}`);
        button.disabled = state.uploading || (action === "left" && index === 0) || (action === "right" && index === state.photos.length - 1); actions.append(button);
      });
      card.append(image, label, cover, actions); return card;
    });
    $("#admin-image-gallery").replaceChildren(...(cards.length ? cards : [element("p", "admin-photos-empty", "Add at least one photo to bring this piece to life.")]));
    $("#admin-image-count").textContent = `${state.photos.length} of 12 photos`;
    $("#admin-generate-product").disabled = !state.photos.length || state.uploading || state.saving || state.generatingDraft || Boolean(state.editing);
    const image = $("#admin-edit-image"); image.hidden = !state.photos.length;
    if (state.photos.length) image.src = state.photos[0]; else image.removeAttribute("src");
  }
  function renderColorVariants() {
    const list = state.colorVariants.map((variant, index) => {
      const row = element("div", "admin-color-variant");
      const image = element("img");
      image.src = variant.image; image.alt = ""; image.loading = "lazy";
      const swatch = element("span", "admin-color-variant-swatch");
      swatch.style.setProperty("--variant-color", variant.hex);
      const copy = element("div", "admin-color-variant-copy");
      copy.append(element("strong", "", variant.name), element("span", "", variant.image.split("/").pop()));
      const remove = element("button", "admin-color-variant-remove", "Remove");
      remove.type = "button"; remove.dataset.removeColor = String(index);
      remove.setAttribute("aria-label", `Remove ${variant.name} color`);
      remove.disabled = state.saving;
      row.append(image, swatch, copy, remove);
      return row;
    });
    const note = $("#admin-color-variants-note");
    if (!state.editing) {
      note.textContent = "Save this product before adding alternate colors.";
    } else {
      note.textContent = "Preset color previews stay available. Added colors are saved with this product.";
    }
    $("#admin-ai-color-suggestion").hidden = true;
    $("#admin-ai-color-suggestion").textContent = "";
    $("#admin-add-color-editor").disabled = !state.editing || state.saving;
    $("#admin-color-variants").replaceChildren(...(list.length ? list : [
      element("p", "admin-color-variants-empty", state.editing ? "No extra colors added yet." : "Create the product first, then add its colors here."),
    ]));
  }
  function openColorDialog(productId = "") {
    const select = $("#admin-color-product");
    const products = state.products.filter((product) => !product.deleted_at);
    select.replaceChildren(new Option("Choose an existing product", ""));
    products.forEach((product) => select.add(new Option(`${product.name} · ${product.sku || product.collection.replace(/^THE | EDIT$/g, "")}`, product.id)));
    select.value = productId || "";
    select.disabled = Boolean(productId);
    $("#admin-color-form").reset();
    select.value = productId || "";
    state.colorImage = null;
    state.colorUploading = false;
    state.colorSaving = false;
    $("#admin-color-image-file").disabled = false;
    $("#admin-color-image-label").textContent = "Choose this color's product photo";
    $("#admin-color-image-preview").hidden = true;
    $("#admin-color-image-preview").removeAttribute("src");
    $("#admin-color-upload-status").textContent = "";
    $("#admin-color-save").disabled = false;
    $("#admin-color-error").textContent = "";
    $("#admin-color-error").hidden = true;
    if (!$("#admin-color-dialog").open) $("#admin-color-dialog").showModal();
    if (productId) $("#admin-color-name").focus({ preventScroll: true });
    else select.focus({ preventScroll: true });
  }
  async function uploadColorImage(event) {
    const file = event.target.files[0]; event.target.value = "";
    if (!file || state.colorUploading || state.colorSaving) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) { $("#admin-color-error").textContent = "Choose a JPG, PNG or WebP photo."; $("#admin-color-error").hidden = false; return; }
    if (file.size > 8 * 1024 * 1024 || file.size === 0) { $("#admin-color-error").textContent = "The photo must be between 1 byte and 8 MB."; $("#admin-color-error").hidden = false; return; }
    state.colorUploading = true;
    $("#admin-color-image-file").disabled = true;
    $("#admin-color-save").disabled = true;
    $("#admin-color-cancel").disabled = true;
    $("#admin-color-close").disabled = true;
    $("#admin-color-error").hidden = true;
    $("#admin-color-upload-status").textContent = "Uploading color photo…";
    try {
      const data = await readPhoto(file), preview = new Image(); preview.src = data;
      try { await preview.decode(); } catch { throw new Error("This file could not be opened as a photo. Please choose another image."); }
      if (preview.naturalWidth * preview.naturalHeight > 40000000) throw new Error("Choose a photo with no more than 40 million pixels.");
      const response = await window.VeloraAuth.request("/api/admin/uploads", { method: "POST", body: { name: file.name, data } });
      state.colorImage = response.image;
      $("#admin-color-image-preview").src = response.image;
      $("#admin-color-image-preview").hidden = false;
      $("#admin-color-image-label").textContent = file.name;
      $("#admin-color-upload-status").textContent = "Color photo uploaded.";
    } catch (error) {
      if (error.status === 401 || error.status === 403) showError(error);
      else { $("#admin-color-error").textContent = error.message || "We couldn't upload this color photo."; $("#admin-color-error").hidden = false; }
      $("#admin-color-upload-status").textContent = "";
    } finally {
      state.colorUploading = false;
      $("#admin-color-image-file").disabled = false;
      $("#admin-color-save").disabled = false;
      $("#admin-color-cancel").disabled = false;
      $("#admin-color-close").disabled = false;
    }
  }
  async function saveColorVariant(event) {
    event.preventDefault();
    const form = $("#admin-color-form");
    if (state.colorSaving || state.colorUploading || !form.reportValidity()) return;
    if (!state.colorImage) {
      $("#admin-color-error").textContent = "Choose and upload a photo for this color first.";
      $("#admin-color-error").hidden = false;
      $("#admin-color-image-file").focus();
      return;
    }
    const productId = $("#admin-color-product").value;
    const product = state.products.find((item) => item.id === productId && !item.deleted_at);
    if (!product) {
      $("#admin-color-error").textContent = "Choose an existing product to add this color to.";
      $("#admin-color-error").hidden = false;
      $("#admin-color-product").focus();
      return;
    }
    state.colorSaving = true;
    $("#admin-color-save").disabled = true;
    $("#admin-color-cancel").disabled = true;
    $("#admin-color-close").disabled = true;
    $("#admin-color-error").hidden = true;
    try {
      const response = await window.VeloraAuth.request(`/api/admin/products/${encodeURIComponent(productId)}/colors`, {
        method: "POST",
        body: { name: $("#admin-color-name").value.trim(), hex: $("#admin-color-hex").value, image: state.colorImage },
      });
      const index = state.products.findIndex((item) => item.id === productId);
      if (index >= 0) state.products[index] = response.product;
      if (state.editing?.id === productId) {
        state.editing = response.product;
        state.colorVariants = [...(response.product.color_variants || [])];
        if (editorSnapshot) {
          const saved = JSON.parse(editorSnapshot);
          saved.colors = state.colorVariants;
          editorSnapshot = JSON.stringify(saved);
        }
        renderColorVariants();
      }
      renderProducts();
      $("#admin-color-dialog").close();
      showToast(`${$("#admin-color-name").value.trim()} added to ${response.product.name}.`);
    } catch (error) {
      if (error.status === 401 || error.status === 403) showError(error);
      else { $("#admin-color-error").textContent = error.message || "We couldn't add this color. Please try again."; $("#admin-color-error").hidden = false; }
    } finally {
      state.colorSaving = false;
      $("#admin-color-save").disabled = false;
      $("#admin-color-cancel").disabled = false;
      $("#admin-color-close").disabled = false;
    }
  }
  function openEditor(id = null) {
    const product = id ? state.products.find((item) => String(item.id) === String(id)) : null;
    if (id && (!product || product.deleted_at)) return;
    state.editorVersion += 1; state.editing = product; state.photos = product ? [...(product.images?.length ? product.images : [product.image])] : []; state.colorVariants = product ? [...(product.color_variants || [])] : []; state.uploading = false;
    $("#admin-edit-form").reset();
    $("#admin-edit-title").textContent = product ? "Edit product" : "Add a new piece";
    $("#admin-edit-name").textContent = product?.name || "Your next favorite piece"; $("#admin-edit-founder").textContent = product?.founder || "A considered addition to your collection";
    $("#admin-edit-product-name").value = product?.name || ""; $("#admin-edit-sku").value = product?.sku || ""; $("#admin-edit-designer").value = product?.founder || "";
    $("#admin-edit-collection").value = product?.collection || "THE EVERYDAY EDIT"; $("#admin-edit-price").value = product?.price ?? "";
    $("#admin-edit-description").value = product?.description || ""; $("#admin-edit-stock").value = product?.stock ?? "";
    for (const field of ["material", "fabric_weight", "origin", "fit"]) {
      $(`#admin-edit-${field.replaceAll("_", "-")}`).value = product?.[field] || "";
    }
    $("#admin-edit-base-color").value = product?.base_color || "Original"; $("#admin-edit-color-hex").value = product?.color_hex || "#d1c8bd"; $("#admin-edit-published").checked = Boolean(product?.published);
    const sizes = product?.sizes || ["XS", "S", "M", "L"];
    document.querySelectorAll('#admin-size-options input').forEach((input) => { input.checked = sizes.includes(input.value); });
    $("#admin-editor-trash").hidden = !product; $("#admin-upload-status").textContent = "";
    $("#admin-description-status").textContent = "When you generate, these details and the cover photo are sent to OpenAI.";
    $("#admin-product-draft-status").textContent = product
      ? "Image-first generation is available when adding a new product."
      : "Upload a photo to generate a product name, description, category, colors, sizes and suggested price. The AI suggests 10 units of stock; confirm your real count. The SKU is assigned when saved. This image is sent to OpenAI only when you generate. New products stay unpublished.";
    $("#admin-generate-description").disabled = state.generatingDescription || state.generatingDraft;
    $("#admin-edit-save").textContent = product ? "Save changes \u2197" : "Create product \u2197"; $("#admin-edit-save").disabled = state.generatingDescription || state.generatingDraft; $("#admin-image-files").disabled = false;
    editorError(""); renderGallery(); renderColorVariants();
    if (!$("#admin-edit-dialog").open) $("#admin-edit-dialog").showModal();
    editorSnapshot = editorValues();
    $("#admin-edit-dialog").scrollTop = 0; $("#admin-edit-product-name").focus({ preventScroll: true });
  }
  async function generateDescription() {
    if (state.generatingDescription || state.saving) return;
    const name = $("#admin-edit-product-name").value.trim();
    const baseColor = $("#admin-edit-base-color").value.trim();
    if (!name) {
      $("#admin-description-status").textContent = "Enter a product name first.";
      $("#admin-edit-product-name").focus();
      return;
    }
    if (!baseColor) {
      $("#admin-description-status").textContent = "Enter the primary color first.";
      $("#admin-edit-base-color").focus();
      return;
    }
    if (!state.photos.length) {
      $("#admin-description-status").textContent = "Upload a product photo first so AI can identify the visible style.";
      $("#admin-image-files").focus();
      return;
    }
    const version = state.editorVersion;
    state.generatingDescription = true;
    $("#admin-generate-description").disabled = true;
    $("#admin-edit-save").disabled = true;
    $("#admin-description-status").textContent = "Generating a description… product details and the cover photo are being sent to OpenAI.";
    try {
      const response = await window.VeloraAuth.request("/api/admin/product-description", {
        method: "POST",
        body: {
          name,
          collection: $("#admin-edit-collection").value,
          base_color: baseColor,
          image: state.photos[0],
        },
      });
      if (version !== state.editorVersion || !$("#admin-edit-dialog").open) return;
      $("#admin-edit-description").value = response.description;
      $("#admin-edit-description").dispatchEvent(new Event("input", { bubbles: true }));
      $("#admin-description-status").textContent = "AI draft added. Review and edit it before saving.";
    } catch (error) {
      if (version !== state.editorVersion || !$("#admin-edit-dialog").open) return;
      $("#admin-description-status").textContent = error.message || "We couldn't generate a description. Please try again.";
      if (error.status === 401 || error.status === 403) showError(error);
    } finally {
      state.generatingDescription = false;
      if ($("#admin-edit-dialog").open) {
        $("#admin-generate-description").disabled = false;
        $("#admin-edit-save").disabled = state.uploading;
      }
    }
  }
  async function generateProductDraft() {
    if (state.generatingDraft || state.generatingDescription || state.saving || state.uploading) return;
    if (state.editing) {
      $("#admin-product-draft-status").textContent = "Image-first generation is available when adding a new product.";
      return;
    }
    if (!state.photos.length) {
      $("#admin-product-draft-status").textContent = "Upload a product photo first.";
      $("#admin-image-files").focus();
      return;
    }
    const version = state.editorVersion;
    state.generatingDraft = true;
    $("#admin-generate-product").disabled = true;
    $("#admin-generate-description").disabled = true;
    $("#admin-edit-save").disabled = true;
    $("#admin-image-files").disabled = true;
    $("#admin-product-draft-status").textContent = "Analyzing the cover photo and preparing a product draft… The image is being sent to OpenAI.";
    try {
      const response = await window.VeloraAuth.request("/api/admin/product-draft", {
        method: "POST",
        body: { image: state.photos[0] },
      });
      if (version !== state.editorVersion || !$("#admin-edit-dialog").open) return;
      const draft = response.draft;
      $("#admin-edit-product-name").value = draft.name;
      $("#admin-edit-name").textContent = draft.name;
      $("#admin-edit-sku").value = "";
      $("#admin-edit-price").value = draft.price.toFixed(2);
      $("#admin-edit-designer").value = draft.founder;
      $("#admin-edit-founder").textContent = draft.founder;
      $("#admin-edit-collection").value = draft.collection;
      $("#admin-edit-description").value = draft.description;
      $("#admin-edit-stock").value = String(draft.stock);
      $("#admin-edit-base-color").value = draft.base_color;
      $("#admin-edit-color-hex").value = draft.color_hex;
      $("#admin-edit-published").checked = false;
      document.querySelectorAll("#admin-size-options input").forEach((input) => {
        input.checked = draft.sizes.includes(input.value);
      });
      const colorSuggestion = $("#admin-ai-color-suggestion");
      colorSuggestion.textContent = `AI suggests ${draft.extra_color} (${draft.extra_color_hex}) as an additional color. Upload a matching photo in “Add color” to add it as a product variant.`;
      colorSuggestion.hidden = false;
      $("#admin-product-draft-status").textContent = `Draft generated. The €${draft.price.toFixed(2)} price and ${draft.sizes.join(", ")} sizes are suggestions; stock is an estimated 10 units. Confirm details before publishing. The SKU will be assigned when you save.`;
      $("#admin-edit-description").dispatchEvent(new Event("input", { bubbles: true }));
    } catch (error) {
      if (version !== state.editorVersion || !$("#admin-edit-dialog").open) return;
      $("#admin-product-draft-status").textContent = error.message || "We couldn't generate a product draft. Please try again.";
      if (error.status === 401 || error.status === 403) showError(error);
    } finally {
      state.generatingDraft = false;
      if ($("#admin-edit-dialog").open) {
        $("#admin-image-files").disabled = false;
        $("#admin-edit-save").disabled = state.uploading;
        $("#admin-generate-description").disabled = false;
        renderGallery();
      }
    }
  }
  function closeEditor() { requestEditorDiscard(finishCloseEditor); }
  function setEditorBusy(busy) {
    state.saving = busy; $("#admin-edit-dialog").setAttribute("aria-busy", String(busy));
    $("#admin-edit-form").querySelectorAll("input, textarea, select, button").forEach((control) => { control.disabled = busy; });
    $("#admin-edit-close").disabled = busy; $("#admin-edit-save").textContent = busy ? "Saving\u2026" : state.editing ? "Save changes \u2197" : "Create product \u2197";
  }
  async function saveProduct(event) {
    event.preventDefault(); if (state.saving || state.uploading || state.generatingDescription || state.generatingDraft || !$("#admin-edit-form").reportValidity()) return;
    const sizes = [...document.querySelectorAll('#admin-size-options input:checked')].map((input) => input.value);
    if (!state.photos.length) { editorError("Add at least one product photo before saving."); $("#admin-image-files").focus(); return; }
    if (!sizes.length) { editorError("Select at least one available size."); $("#admin-size-options input").focus(); return; }
    const values = {
      name: $("#admin-edit-product-name").value.trim(), founder: $("#admin-edit-designer").value.trim(), collection: $("#admin-edit-collection").value,
      price: Number($("#admin-edit-price").value), description: $("#admin-edit-description").value.trim(), stock: $("#admin-edit-stock").value === "" ? null : Number($("#admin-edit-stock").value),
      sizes, images: [...state.photos], base_color: $("#admin-edit-base-color").value.trim(), color_hex: $("#admin-edit-color-hex").value, color_variants: [...state.colorVariants], published: $("#admin-edit-published").checked,
    };
    for (const field of ["material", "fabric_weight", "origin", "fit"]) {
      values[field] = $(`#admin-edit-${field.replaceAll("_", "-")}`).value.trim();
    }
    if ($("#admin-edit-sku").value.trim()) values.sku = $("#admin-edit-sku").value.trim();
    const product = state.editing; editorError(""); setEditorBusy(true);
    try {
      const path = product ? `/api/admin/products/${encodeURIComponent(product.id)}` : "/api/admin/products";
      const response = await window.VeloraAuth.request(path, { method: product ? "PATCH" : "POST", body: values });
      if (response.product) { const old = state.products.find((item) => item.id === response.product.id); if (old) Object.assign(old, response.product); else state.products.unshift(response.product); }
      if (!product) {
        $("#admin-product-search").value = "";
        $("#admin-product-filter").value = "all";
        $("#admin-stock-filter").value = "all";
        $("#admin-product-sort").value = "newest";
      }
      editorSnapshot = null; $("#admin-edit-dialog").close(); state.editorVersion += 1; await refreshData();
      showToast(product ? "Product updated. Your collection is ready." : "Product created. Your new piece is ready.");
    } catch (error) { if (error.status === 401 || error.status === 403) showError(error); else editorError(error.message || "We couldn\u2019t save this product. Please try again."); }
    finally { setEditorBusy(false); renderGallery(); }
  }
  function readPhoto(file) {
    return new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = () => reject(new Error("We couldn\u2019t read this photo. Please choose it again.")); reader.readAsDataURL(file); });
  }
  async function uploadPhotos(event) {
    const files = [...event.target.files]; event.target.value = "";
    if (!files.length || state.uploading || state.saving) return;
    if (files.length > 12 - state.photos.length) { editorError(`You can add ${12 - state.photos.length} more photos. A product can have up to 12.`); return; }
    const version = state.editorVersion; state.uploading = true; $("#admin-edit-save").disabled = true; $("#admin-image-files").disabled = true; editorError(""); renderGallery();
    let added = 0;
    try {
      for (const [index, file] of files.entries()) {
        if (version !== state.editorVersion) return;
        if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) throw new Error("Choose JPG, PNG or WebP photos.");
        if (file.size > 8 * 1024 * 1024 || file.size === 0) throw new Error("Each photo must be between 1 byte and 8 MB.");
        $("#admin-upload-status").textContent = `Uploading photo ${index + 1} of ${files.length}\u2026`;
        const data = await readPhoto(file), preview = new Image(); preview.src = data;
        try { await preview.decode(); } catch { throw new Error("This file could not be opened as a photo. Please choose another image."); }
        if (preview.naturalWidth * preview.naturalHeight > 40000000) throw new Error("Choose photos with no more than 40 million pixels.");
        if (version !== state.editorVersion) return;
        const response = await window.VeloraAuth.request("/api/admin/uploads", { method: "POST", body: { name: file.name, data } });
        if (version !== state.editorVersion) return;
        state.photos.push(response.image); added += 1; renderGallery();
      }
      $("#admin-upload-status").textContent = `${added} ${added === 1 ? "photo" : "photos"} added. Choose your favorite cover.`;
    } catch (error) {
      if (version === state.editorVersion) { $("#admin-upload-status").textContent = added ? `${added} ${added === 1 ? "photo" : "photos"} added.` : ""; if (error.status === 401 || error.status === 403) showError(error); else editorError(error.message || "We couldn\u2019t upload that photo. Please try again."); }
    } finally { if (version === state.editorVersion) { state.uploading = false; $("#admin-edit-save").disabled = false; $("#admin-image-files").disabled = false; renderGallery(); } }
  }

  function openTrash(id) {
    const product = state.products.find((item) => item.id === id); if (!product || product.deleted_at || state.saving) return;
    const proceed = () => {
      if ($("#admin-edit-dialog").open) finishCloseEditor();
      state.trash = product;
      $("#admin-delete-name").textContent = product.name; $("#admin-delete-error").hidden = true; $("#admin-delete-dialog").showModal(); $("#admin-delete-cancel").focus();
    };
    if ($("#admin-edit-dialog").open) requestEditorDiscard(proceed); else proceed();
  }
  function closeTrash() { if (!state.trashBusy) $("#admin-delete-dialog").close(); }
  async function trashProduct() {
    if (!state.trash || state.trashBusy) return; state.trashBusy = true;
    $("#admin-delete-dialog").querySelectorAll("button").forEach((button) => { button.disabled = true; }); $("#admin-delete-confirm").textContent = "Moving\u2026";
    try {
      await window.VeloraAuth.request(`/api/admin/products/${encodeURIComponent(state.trash.id)}`, { method: "DELETE", body: {} });
      $("#admin-delete-dialog").close(); await refreshData(); showToast("Product moved to trash. You can restore it whenever you need.");
    } catch (error) { if (error.status === 401 || error.status === 403) showError(error); else { $("#admin-delete-error").textContent = error.message; $("#admin-delete-error").hidden = false; } }
    finally { state.trashBusy = false; $("#admin-delete-dialog").querySelectorAll("button").forEach((button) => { button.disabled = false; }); $("#admin-delete-confirm").textContent = "Move to trash"; }
  }
  async function productAction(button, action, id) {
    button.disabled = true;
    try {
      const response = await window.VeloraAuth.request(`/api/admin/products/${encodeURIComponent(id)}/${action}`, { method: "POST", body: {} });
      if (action === "duplicate") {
        $("#admin-product-search").value = "";
        $("#admin-product-filter").value = "draft";
        $("#admin-stock-filter").value = "all";
      }
      await refreshData(); showToast(action === "restore" ? "Product restored as a draft. Review it before publishing." : "A draft copy is ready for your finishing touches.");
      if (action === "duplicate" && response.product) openEditor(response.product.id);
    } catch (error) { showError(error); } finally { if (button.isConnected) button.disabled = false; }
  }
  function exportProducts() {
    const rows = [["SKU", "Name", "Founder", "Category", "Price EUR", "Stock", "Sizes", "Status", "Description", "Images"], ...activeProducts().map((product) => [product.sku || "", product.name, product.founder, product.collection, product.price, product.stock ?? "Not tracked", product.sizes?.join(" / ") || "", product.published ? "Published" : "Draft", product.description, (product.images || [product.image]).join(" | ")])];
    function escape(value) { let text = String(value ?? ""); if (/^[\s]*[=+\-@]/.test(text) || /^[\t\r\n]/.test(text)) text = "'" + text; return `"${text.replaceAll('"', '""')}"`; }
    const csv = "\uFEFF" + rows.map((row) => row.map(escape).join(",")).join("\r\n"), url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8;" }));
    const link = element("a"); link.href = url; link.download = `velora-catalog-${new Date().toISOString().slice(0, 10)}.csv`; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    showToast("Catalog exported. Your active products are in the CSV file.");
  }
  async function init() {
    try {
      if (!window.VeloraAuth) throw new Error("The studio couldn\u2019t connect. Please try again.");
      const user = await window.VeloraAuth.ready;
      if (!user) { location.replace("login.html?next=admin.html"); return; } if (user.role !== "admin") { location.replace("account.html"); return; }
      $("#admin-sidebar-name").textContent = user.name; $("#admin-sidebar-avatar").textContent = initials(user.name);
      $("#admin-today").textContent = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "long", year: "numeric" }).format(new Date());
      const operations = await window.VeloraAuth.request("/api/admin/commerce");
      window.veloraCommerceRole = operations.role;
      if (operations.role === "manager") {
        document.querySelectorAll('[data-admin-section="business"],[data-admin-section="security"],[data-admin-section="folder-access"]').forEach(link => { link.hidden = true; });
      }
      if (operations.role === "warehouse") {
        document.querySelectorAll("[data-admin-section]").forEach(link => { link.hidden = link.dataset.adminSection !== "operations"; });
        location.hash = "operations";
      }
      selectSection(); $("#admin-access").hidden = true; $("#admin-shell").hidden = false; if (window.veloraCommerceRole !== "warehouse") await refreshData();
    } catch (error) { $("#admin-access").classList.add("has-error"); $("#admin-access h1").textContent = "A moment behind the scenes."; $("#admin-access-message").textContent = error.message || "We couldn\u2019t open the studio. Please try again."; $("#admin-access-retry").hidden = false; }
  }
  window.addEventListener("hashchange", selectSection);
  $("#admin-menu-toggle").addEventListener("click", () => {
    const toggle = $("#admin-menu-toggle"), open = toggle.getAttribute("aria-expanded") !== "true";
    toggle.setAttribute("aria-expanded", String(open));
    $(".admin-sidebar").classList.toggle("is-menu-open", open);
    if (open) $(".admin-nav a:not([hidden])[aria-current='page']")?.focus({ preventScroll: true });
  });
  document.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    if (!event.target.closest(".admin-sidebar")) closeMobileMenu(false);
    const link = event.target.closest("a[href]");
    if (link?.dataset.adminSection) closeMobileMenu(false);
    if (!link || link.target === "_blank" || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || !editorIsDirty()) return;
    event.preventDefault();
    requestEditorDiscard(() => { finishCloseEditor(); location.href = link.href; });
  }, true);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && $("#admin-menu-toggle").getAttribute("aria-expanded") === "true") {
      event.preventDefault(); closeMobileMenu(true);
    }
  });
  mobileNavigation.addEventListener("change", () => closeMobileMenu(false));
  window.addEventListener("beforeunload", (event) => {
    if (!editorIsDirty()) return;
    event.preventDefault(); event.returnValue = "";
  });
  $("#admin-discard-keep").addEventListener("click", keepEditing);
  $("#admin-discard-confirm").addEventListener("click", () => {
    const action = discardAction; discardAction = null;
    $("#admin-discard-dialog").close();
    action?.();
  });
  $("#admin-discard-dialog").addEventListener("cancel", (event) => { event.preventDefault(); keepEditing(); });
  $("#admin-product-search").addEventListener("input", renderProducts);
  ["#admin-product-filter", "#admin-stock-filter", "#admin-product-sort"].forEach((selector) => $(selector).addEventListener("change", renderProducts));
  $("#admin-customer-search").addEventListener("input", renderCustomers); $("#admin-add-product").addEventListener("click", () => openEditor()); $("#admin-export-products").addEventListener("click", exportProducts);
  $("#admin-add-color").addEventListener("click", () => openColorDialog());
  $("#admin-add-color-editor").addEventListener("click", () => { if (state.editing) openColorDialog(state.editing.id); });
  $("#admin-color-close").addEventListener("click", () => { if (!state.colorSaving && !state.colorUploading) $("#admin-color-dialog").close(); });
  $("#admin-color-cancel").addEventListener("click", () => { if (!state.colorSaving && !state.colorUploading) $("#admin-color-dialog").close(); });
  $("#admin-color-dialog").addEventListener("cancel", (event) => { if (state.colorSaving || state.colorUploading) event.preventDefault(); });
  $("#admin-color-dialog").addEventListener("click", (event) => { if (event.target === event.currentTarget && !state.colorSaving && !state.colorUploading) $("#admin-color-dialog").close(); });
  $("#admin-color-image-file").addEventListener("change", uploadColorImage);
  $("#admin-color-form").addEventListener("submit", saveColorVariant);
  $("#admin-color-variants").addEventListener("click", (event) => {
    if (!(event.target instanceof Element) || state.saving) return;
    const button = event.target.closest("[data-remove-color]");
    if (!button) return;
    const index = Number(button.dataset.removeColor);
    if (!Number.isInteger(index) || index < 0 || index >= state.colorVariants.length) return;
    state.colorVariants.splice(index, 1);
    renderColorVariants();
  });
  $("#admin-products-body").addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return; const button = event.target.closest("button"); if (!button) return;
    if (button.dataset.editProduct) openEditor(button.dataset.editProduct); else if (button.dataset.trashProduct) openTrash(button.dataset.trashProduct);
    else if (button.dataset.duplicateProduct) productAction(button, "duplicate", button.dataset.duplicateProduct); else if (button.dataset.restoreProduct) productAction(button, "restore", button.dataset.restoreProduct);
  });
  $("#admin-edit-close").addEventListener("click", closeEditor); $("#admin-edit-cancel").addEventListener("click", closeEditor);
  $("#admin-edit-dialog").addEventListener("cancel", (event) => { event.preventDefault(); closeEditor(); });
  $("#admin-edit-dialog").addEventListener("click", (event) => { if (event.target !== event.currentTarget) return; const rect = event.currentTarget.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) closeEditor(); });
  $("#admin-edit-form").addEventListener("submit", saveProduct);
  $("#admin-generate-description").addEventListener("click", generateDescription);
  $("#admin-generate-product").addEventListener("click", generateProductDraft);
  $("#admin-edit-product-name").addEventListener("input", () => { $("#admin-edit-name").textContent = $("#admin-edit-product-name").value.trim() || "Your next favorite piece"; });
  $("#admin-edit-designer").addEventListener("input", () => { $("#admin-edit-founder").textContent = $("#admin-edit-designer").value.trim() || "A considered addition to your collection"; });
  $("#admin-image-files").addEventListener("change", uploadPhotos);
  $("#admin-image-gallery").addEventListener("click", (event) => {
    if (!(event.target instanceof Element) || state.saving || state.uploading) return;
    const button = event.target.closest("[data-image-action]"); if (!button) return;
    const index = Number(button.dataset.imageIndex); if (!Number.isInteger(index) || index < 0 || index >= state.photos.length) return;
    const action = button.dataset.imageAction;
    if (action === "remove") state.photos.splice(index, 1); else if (action === "cover") state.photos.unshift(state.photos.splice(index, 1)[0]);
    else if (action === "left" && index > 0) [state.photos[index - 1], state.photos[index]] = [state.photos[index], state.photos[index - 1]];
    else if (action === "right" && index < state.photos.length - 1) [state.photos[index + 1], state.photos[index]] = [state.photos[index], state.photos[index + 1]];
    renderGallery();
    const nextIndex = action === "cover" ? 0 : action === "left" ? index - 1 : action === "right" ? index + 1 : Math.min(index, state.photos.length - 1);
    const card = document.querySelector(`#admin-image-gallery > [data-image-index="${nextIndex}"]`);
    const nextControl = card?.querySelector(`[data-image-action="${action}"]:not(:disabled)`) || card?.querySelector("button:not(:disabled)");
    if (nextControl) nextControl.focus();
    else $("#admin-image-files").focus();
  });
  $("#admin-editor-trash").addEventListener("click", () => { if (state.editing) openTrash(state.editing.id); });
  $("#admin-delete-close").addEventListener("click", closeTrash); $("#admin-delete-cancel").addEventListener("click", closeTrash); $("#admin-delete-confirm").addEventListener("click", trashProduct);
  $("#admin-delete-dialog").addEventListener("cancel", (event) => { if (state.trashBusy) event.preventDefault(); }); $("#admin-data-retry").addEventListener("click", refreshData);
  $("#admin-activity-refresh").addEventListener("click", async (event) => { event.currentTarget.disabled = true; await refreshData(); $("#admin-activity-refresh").disabled = false; });
  document.querySelectorAll("[data-stock-shortcut]").forEach((button) => button.addEventListener("click", () => { $("#admin-product-filter").value = "all"; $("#admin-product-search").value = ""; $("#admin-stock-filter").value = button.dataset.stockShortcut; location.hash = "products"; selectSection(); renderProducts(); }));
  $("#admin-trash-shortcut").addEventListener("click", () => { $("#admin-product-filter").value = "trash"; $("#admin-product-search").value = ""; $("#admin-stock-filter").value = "all"; location.hash = "products"; selectSection(); renderProducts(); });
  $("#admin-signout").addEventListener("click", () => requestEditorDiscard(async () => {
    if ($("#admin-edit-dialog").open) finishCloseEditor();
    $("#admin-signout").disabled = true;
    try { await window.VeloraAuth.logout(); } catch (error) { showError(error); $("#admin-signout").disabled = false; }
  }));
  init();
})();
