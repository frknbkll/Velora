(() => {
  "use strict";

  const params = new URLSearchParams(location.search);
  const content = document.querySelector("#product-page-content");
  const status = document.querySelector("#product-page-status");
  const returnLink = document.querySelector("#product-page-return");
  const image = document.querySelector("#product-page-image");
  const thumbnails = document.querySelector("#product-thumbnails");
  const photoCount = document.querySelector("#product-photo-count");
  const colorField = document.querySelector("#product-color-field");
  const colorOptions = document.querySelector("#product-page-colors");
  const sizeOptions = document.querySelector("#product-page-sizes");
  const stockNote = document.querySelector("#product-page-stock");
  const addButton = document.querySelector("#product-page-add");
  const wishlistButton = document.querySelector("#product-page-wishlist");
  const feedback = document.querySelector("#product-page-feedback");
  const main = document.querySelector("#main-content");
  const photoFrame = document.querySelector("#product-main-photo");
  const photoState = document.querySelector("#product-photo-state");
  const photoMessage = document.querySelector("#product-photo-message");
  const photoRetry = document.querySelector("#product-photo-retry");
  const photoInspector = window.VeloraImageInspector?.mount({ frame: photoFrame, image });
  const mobileBar = document.querySelector("#product-mobile-bar");
  const mobileAction = document.querySelector("#product-mobile-action");
  const mobileFeedback = document.querySelector("#product-mobile-feedback");
  const mobileViewport = matchMedia("(max-width: 760px)");
  const currency = window.VeloraShopping.currency;

  let product;
  let colors = [];
  let selection = { color: "", size: "" };
  let photos = [];
  let activePhoto = 0;
  let shopping = { wishlist: new Set(), cart: {} };
  let sizeConfirmed = false;
  let loadVersion = 0;

  function productError(message, retryable = false) {
    return Object.assign(new Error(message), { retryable });
  }

  function reserveMobileBar() {
    const banner = document.querySelector("#privacy-banner");
    const privacyObscures = banner && !banner.hidden && banner.getBoundingClientRect().height > innerHeight * .55;
    mobileBar.classList.toggle("is-privacy-obscured", Boolean(privacyObscures));
    const height = mobileViewport.matches && !mobileBar.hidden && !privacyObscures ? mobileBar.getBoundingClientRect().height + 24 : 0;
    document.documentElement.style.setProperty("--product-mobile-bar-height", `${height}px`);
  }

  function renderMobileAction() {
    if (!product || content.hidden) return;
    document.querySelector("#product-mobile-price").textContent = currency.format(Number(product.price) || 0);
    document.querySelector("#product-mobile-selection").textContent = `${selection.color} · ${sizeConfirmed ? selection.size : "Choose size"}`;
    mobileAction.disabled = sizeConfirmed && currentStock() === 0;
    mobileAction.textContent = !sizeConfirmed ? "Choose options" : mobileAction.disabled ? "Sold out" : "Add to bag";
    reserveMobileBar();
  }

  function setFeedback(message, compactMessage = message, error = false) {
    feedback.textContent = message;
    mobileFeedback.textContent = compactMessage;
    mobileFeedback.hidden = !compactMessage;
    mobileFeedback.classList.toggle("is-error", error);
    reserveMobileBar();
  }

  function chooseOptions(event) {
    event?.preventDefault();
    const options = document.querySelector("#product-page-options");
    options.scrollIntoView({ block: "center", behavior: "instant" });
    options.focus({ preventScroll: true });
  }

  function showUnavailable(message, retryable = false) {
    content.hidden = true;
    mobileBar.hidden = true;
    reserveMobileBar();
    main.setAttribute("aria-busy", "false");
    status.replaceChildren();
    status.setAttribute("role", "alert");
    const heading = document.createElement("h1");
    heading.textContent = retryable ? "A moment for this piece." : "This piece is unavailable";
    const explanation = document.createElement("p");
    explanation.textContent = message;
    status.append(heading, explanation);
    if (retryable) {
      const retry = document.createElement("button");
      retry.type = "button";
      retry.className = "product-retry";
      retry.id = "product-page-retry";
      retry.textContent = "Try again";
      retry.addEventListener("click", loadCurrentProduct);
      status.append(retry);
    }
    status.hidden = false;
    returnLink.hidden = false;
  }

  function readPreview() {
    if (params.has("id")) return null;
    const raw = params.get("preview");
    if (!raw || raw.length > 20000) return null;
    try {
      const value = JSON.parse(raw);
      if (!value || typeof value !== "object" || typeof value.name !== "string" ||
          typeof value.image !== "string" || !Array.isArray(value.sizes)) return null;
      return value;
    } catch {
      return null;
    }
  }

  async function loadProduct() {
    if (params.has("id")) {
      const id = params.get("id");
      if (!id || id.length > 100) throw productError("This product link is not valid.");
      const response = await fetch(`/api/catalog/${encodeURIComponent(id)}`, {
        cache: "no-store",
        signal: AbortSignal.timeout(10000),
      });
      if (response.status === 404) throw productError("This product may have been unpublished or removed.");
      if (!response.ok) throw productError("We couldn't load this product right now. Please try again.", true);
      const data = await response.json();
      if (!data.product || data.product.published !== true) throw productError("This product is no longer available.");
      return data.product;
    }
    return readPreview();
  }

  function colorsFor(item) {
    const mapped = window.veloraColorImages?.[item.color_key || item.image] || [];
    const primary = {
      name: item.base_color && item.base_color !== "Original" ? item.base_color : mapped[0]?.name || "Original",
      hex: item.color_hex || mapped[0]?.hex || "#d1c8bd",
      image: item.image,
      poses: mapped[0]?.poses || [],
    };
    const alternatives = [
      ...mapped.slice(1),
      ...(Array.isArray(item.color_variants) ? item.color_variants : []),
      ...(Array.isArray(item.colors) ? item.colors.slice(1) : []),
    ];
    const seen = new Set([primary.name.toLocaleLowerCase()]);
    return [primary, ...alternatives.filter((color) => {
      if (!color || typeof color.name !== "string") return false;
      const name = color.name.toLocaleLowerCase();
      if (seen.has(name)) return false;
      seen.add(name);
      return true;
    })];
  }

  function updateBagLink() {
    const count = Object.values(shopping.cart).reduce((total, quantity) => total + quantity, 0);
    document.querySelectorAll("[data-product-bag-count]").forEach((node) => { node.textContent = String(count); });
  }

  function persistShopping() {
    const saved = window.VeloraShopping.save(shopping);
    updateBagLink();
    return saved;
  }

  function loadShopping() {
    const state = window.VeloraShopping.read();
    shopping = { wishlist: state.wishlist, cart: Object.fromEntries(state.cart) };
    updateBagLink();
    if (state.readError) feedback.textContent = "Some saved shopping details could not be loaded. Please check your bag before continuing.";
  }

  function quantityInBag() {
    const byVariant = product.variant_stock && Object.keys(product.variant_stock).length;
    return Object.entries(shopping.cart).reduce((total, [key, quantity]) => {
      if (key !== product.key && !key.startsWith(`${product.key}::`)) return total;
      if (!byVariant || key === product.key) return total + quantity;
      const parts = key.slice(product.key.length + 2).split("::");
      try {
        return total + (parts.length === 2 && decodeURIComponent(parts[0]).toLowerCase() === selection.color.toLowerCase() &&
          decodeURIComponent(parts[1]).toLowerCase() === selection.size.toLowerCase() ? quantity : 0);
      } catch { return total; }
    }, 0);
  }

  function currentStock() {
    if (product.variant_stock && Object.keys(product.variant_stock).length) {
      return product.variant_stock[`${selection.color.toLocaleLowerCase()}|${selection.size.toLocaleLowerCase()}`] || 0;
    }
    return product.stock;
  }

  function galleryPhotos() {
    const selected = colors.find((color) => color.name === selection.color);
    const primary = selected?.image || product.image;
    const isBaseColor = selection.color === colors[0]?.name;
    const candidates = [primary, ...(selected?.poses || []), ...(isBaseColor ? product.images || [product.image] : []),
      ...(isBaseColor && assetSource(product.item_image) ? [product.item_image] : [])];
    return [...new Set(candidates.filter((photo) => typeof photo === "string" && photo))];
  }

  function showPhoto(index) {
    activePhoto = (index + photos.length) % photos.length;
    photoFrame.setAttribute("aria-busy", "true");
    photoFrame.dataset.photoState = "loading";
    photoState.hidden = false;
    photoMessage.textContent = "Loading photograph…";
    photoRetry.hidden = true;
    image.hidden = false;
    if (window.VeloraImageSources) window.VeloraImageSources.apply(image, photos[activePhoto], "(max-width: 760px) 100vw, 55vw");
    else image.src = photos[activePhoto];
    image.alt = photos[activePhoto] === product.item_image
      ? `${product.name} — item-only photograph`
      : `${product.name}${selection.color ? ` in ${selection.color}` : ""} — photo ${activePhoto + 1}`;
    const alternateColor = selection.color !== colors[0]?.name;
    const selfLink = `product.html?id=${encodeURIComponent(product.id || "")}${alternateColor ? `&color=${encodeURIComponent(selection.color)}` : assetSource(product.item_image) ? "&view=item" : ""}`;
    photoInspector?.update({ src: photos[activePhoto], alt: image.alt, title: product.name, hotspots: product.image_hotspots || [], productId: product.id, selfLink });
    photoCount.textContent = photos.length > 1 ? `${activePhoto + 1} / ${photos.length}` : "";
    thumbnails.querySelectorAll("button").forEach((button, buttonIndex) => {
      button.setAttribute("aria-pressed", String(buttonIndex === activePhoto));
    });
    renderShopLook();
  }

  function renderGallery() {
    photos = galleryPhotos();
    activePhoto = 0;
    thumbnails.replaceChildren();
    photos.forEach((photo, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute("aria-label", photo === product.item_image ? `Show item-only photograph of ${product.name}` : `Show photo ${index + 1} of ${photos.length}`);
      button.setAttribute("aria-pressed", String(index === 0));
      const thumbnail = document.createElement("img");
      if (window.VeloraImageSources) window.VeloraImageSources.apply(thumbnail, photo, "74px");
      else thumbnail.src = photo;
      thumbnail.alt = "";
      thumbnail.loading = "lazy";
      button.append(thumbnail);
      button.addEventListener("click", () => showPhoto(index));
      thumbnails.append(button);
    });
    const itemIndex = params.get("view") === "item" ? photos.indexOf(product.item_image) : -1;
    showPhoto(itemIndex >= 0 ? itemIndex : 0);
  }

  function assetSource(source) {
    if (typeof source !== "string" || !source) return "";
    try {
      const url = new URL(source, location.href);
      return url.origin === location.origin && ["http:", "https:"].includes(url.protocol)
        && url.pathname.startsWith("/assets/") && !url.username && !url.password ? source : "";
    } catch { return ""; }
  }

  function pieceLink(item) {
    return `product.html?id=${encodeURIComponent(item.id)}${assetSource(item.item_image) ? "&view=item" : ""}`;
  }

  function renderParentLook() {
    const link = document.querySelector("#product-parent-look"), parent = product.parent_look;
    const valid = parent && /^[A-Za-z0-9_-]{1,64}$/.test(parent.id || "") && parent.id !== product.id && typeof parent.name === "string";
    link.hidden = !valid;
    if (!valid) { link.removeAttribute("href"); link.textContent = ""; return; }
    link.href = `product.html?id=${encodeURIComponent(parent.id)}`;
    link.textContent = `← View the complete look: ${parent.name}`;
  }

  function renderShopLook() {
    const section = document.querySelector("#product-shop-look"), grid = document.querySelector("#product-look-items");
    if (product.parent_product_id) { grid.replaceChildren(); section.hidden = true; return; }
    const source = photos[activePhoto] === product.item_image ? product.image : photos[activePhoto];
    const isBasePhoto = source === product.image;
    const pieces = new Map();
    if (isBasePhoto && product.id && assetSource(product.item_image)) {
      pieces.set(product.id, { item: product, label: "Main piece" });
    }
    (Array.isArray(product.image_hotspots) ? product.image_hotspots : []).forEach((point) => {
      if (point?.image !== source) return;
      const item = point?.product;
      if (!item || !/^[A-Za-z0-9_-]{1,64}$/.test(item.id || "") || typeof item.name !== "string" || !item.name.trim()
          || !Number.isFinite(item.price) || item.price < 0 || !assetSource(item.item_image || item.image)) return;
      if (item.id === product.id && (!isBasePhoto || !assetSource(item.item_image || product.item_image))) return;
      if (!pieces.has(item.id)) pieces.set(item.id, { item, label: typeof point.label === "string" ? point.label : "" });
    });
    grid.replaceChildren();
    pieces.forEach(({ item, label }) => {
      const card = document.createElement("article"); card.className = "product-look-item"; card.dataset.lookProductId = item.id;
      const link = document.createElement("a"); link.className = "product-look-item-link"; link.href = pieceLink(item);
      const photo = document.createElement("img"); photo.alt = item.name; photo.loading = "lazy"; photo.decoding = "async";
      const source = assetSource(item.item_image || item.image);
      if (window.VeloraImageSources) window.VeloraImageSources.apply(photo, source, "(max-width: 760px) 44vw, (max-width: 1100px) 30vw, 22vw");
      else photo.src = source;
      const copy = document.createElement("div"); copy.className = "product-look-item-copy";
      if (label) { const caption = document.createElement("span"); caption.className = "product-look-item-label"; caption.textContent = label; copy.append(caption); }
      const name = document.createElement("h3"); name.textContent = item.name;
      const price = document.createElement("p"); price.className = "product-look-item-price"; price.textContent = currency.format(item.price);
      const action = document.createElement("span"); action.className = "product-look-item-action"; action.textContent = "View piece ↗";
      copy.append(name, price, action); link.append(photo, copy); card.append(link); grid.append(card);
    });
    section.hidden = !pieces.size;
  }

  function renderColors() {
    colorField.hidden = colors.length < 2;
    colorOptions.replaceChildren();
    colors.forEach((color) => {
      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute("aria-label", color.name);
      button.setAttribute("aria-pressed", String(selection.color === color.name));
      const swatch = document.createElement("span");
      swatch.className = "product-page-swatch";
      swatch.style.backgroundColor = color.hex || "#d1c8bd";
      swatch.setAttribute("aria-hidden", "true");
      const name = document.createElement("span");
      name.textContent = color.name;
      button.append(swatch, name);
      button.addEventListener("click", () => {
        selection.color = color.name;
        setFeedback("");
        colorOptions.querySelectorAll("button").forEach((option) => {
          option.setAttribute("aria-pressed", String(option === button));
        });
        document.querySelector("#product-color-label").textContent = `Color: ${color.name}`;
        renderGallery();
        renderStock();
        updateVariantUrl();
      });
      colorOptions.append(button);
    });
    document.querySelector("#product-color-label").textContent =
      colors.length > 1 ? `Color: ${selection.color}` : "Color";
  }

  function renderSizes() {
    sizeOptions.replaceChildren();
    product.sizes.forEach((size) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = size;
      button.setAttribute("aria-pressed", String(selection.size === size));
      button.addEventListener("click", () => {
        selection.size = size;
        sizeConfirmed = true;
        setFeedback("");
        sizeOptions.querySelectorAll("button").forEach((option) => {
          option.setAttribute("aria-pressed", String(option === button));
        });
        renderStock();
        updateVariantUrl();
      });
      sizeOptions.append(button);
    });
  }

  function renderStock() {
    const stock = currentStock();
    const soldOut = stock === 0;
    addButton.disabled = soldOut;
    addButton.textContent = soldOut ? "Sold out" : "Add to bag";
    stockNote.textContent = soldOut
      ? "This color and size is currently sold out."
      : stock === null || stock === undefined
        ? "Availability is not confirmed for this showcase item."
        : "Availability shown is illustrative.";
    if (product) renderMobileAction();
  }

  function updateVariantUrl() {
    params.set("color", selection.color);
    params.set("size", selection.size);
    history.replaceState(null, "", `${location.pathname}?${params}`);
  }

  function renderInformation() {
    const information = document.querySelector("#product-page-information");
    information.replaceChildren();
    const sections = [
      ["product-fit", "Size & fit", [
        product.fit || "Product-specific fit and garment measurements have not been supplied yet.",
        product.size_guide || "Size labels are illustrative in this concept collection. A size label alone cannot confirm your fit.",
      ]],
      ["", "Fabric & product details", [
        `Material / composition: ${product.material || "Not supplied yet"}`,
        `Fabric weight: ${product.fabric_weight || "Not supplied yet"}`,
        `Country of manufacture: ${product.origin || "Not supplied yet"}`,
      ]],
    ];
    sections.forEach(([id, title, paragraphs], index) => {
      const section = document.createElement("details");
      section.className = "product-accordion";
      if (index === 0) section.id = id;
      const summary = document.createElement("summary");
      summary.textContent = title;
      const body = document.createElement("div");
      body.className = "product-accordion-content";
      paragraphs.forEach((text) => {
        const paragraph = document.createElement("p");
        paragraph.textContent = text;
        body.append(paragraph);
      });
      section.append(summary, body);
      information.append(section);
    });
  }

  function renderProduct() {
    product.key = product.id ? `product:${product.id}` : product.key;
    colors = colorsFor(product);
    const sizes = product.sizes.filter((size) => typeof size === "string");
    if (!product.key || !product.name || !product.image || !sizes.length) {
      throw new Error("This product link does not contain a complete product.");
    }
    const queryColor = params.get("color");
    const querySize = params.get("size");
    selection = {
      color: colors.some((color) => color.name === queryColor) ? queryColor : colors[0].name,
      size: sizes.includes(querySize) ? querySize : sizes.includes("M") ? "M" : sizes[0],
    };
    sizeConfirmed = false;
    product.sizes = sizes;

    document.title = `${product.name} — Velora`;
    document.querySelector('meta[name="description"]').content = product.description || `Discover ${product.name} from Velora.`;
    document.querySelector("#product-page-title").textContent = product.name;
    document.querySelector("#product-page-collection").textContent = product.collection || "THE OPENING COLLECTION";
    document.querySelector("#product-page-byline").textContent = product.founder ? `Designed by ${product.founder}` : "From the Velora collection";
    document.querySelector("#product-page-price").textContent = currency.format(Number(product.price) || 0);
    document.querySelector("#product-page-description").textContent = product.description || "A considered piece from the Velora collection.";
    document.querySelector("[data-product-mobile-name]").textContent = product.name;
    document.querySelector("[data-product-mobile-price]").textContent = currency.format(Number(product.price) || 0);
    document.querySelector("[data-product-choose-options]").firstChild.textContent = colors.length > 1 ? "Choose color & size " : "Choose your size ";
    renderColors();
    renderSizes();
    renderGallery();
    renderStock();
    renderInformation();
    renderParentLook();
    wishlistButton.setAttribute("aria-pressed", String(shopping.wishlist.has(product.key)));
    wishlistButton.textContent = shopping.wishlist.has(product.key) ? "♥ Saved" : "♡ Wishlist";
    status.hidden = true;
    content.hidden = false;
    mobileBar.hidden = false;
    main.setAttribute("aria-busy", "false");
    renderMobileAction();
  }

  addButton.addEventListener("click", () => {
    const available = currentStock();
    const cartKey = `${product.key}::${encodeURIComponent(selection.color)}::${encodeURIComponent(selection.size)}`;
    const currentQuantity = shopping.cart[cartKey] || 0;
    if (available !== null && available !== undefined && quantityInBag() >= available) {
      setFeedback(available === 0
        ? "This size and color is currently sold out."
        : `Only ${available} of this selection can be added to your bag.`, undefined, true);
      return;
    }
    sizeConfirmed = true;
    shopping.cart[cartKey] = currentQuantity + 1;
    const saved = persistShopping();
    setFeedback(saved
      ? `Added ${product.name} to your shopping bag.`
      : "Added on this page, but your bag could not be retained. Check that browser storage is available before leaving this page.",
      saved ? "Added to your bag. Use View bag to review your selection." : "Your bag could not be saved. Check browser storage before leaving.", !saved);
    renderMobileAction();
  });

  document.querySelectorAll("[data-product-choose-options]").forEach((link) => link.addEventListener("click", chooseOptions));
  mobileAction.addEventListener("click", () => { if (sizeConfirmed) addButton.click(); else chooseOptions(); });
  mobileViewport.addEventListener("change", reserveMobileBar);
  window.addEventListener("resize", reserveMobileBar);
  if (typeof ResizeObserver !== "undefined") {
    const layoutObserver = new ResizeObserver(reserveMobileBar);
    layoutObserver.observe(mobileBar);
    const banner = document.querySelector("#privacy-banner");
    if (banner) layoutObserver.observe(banner);
  }
  image.addEventListener("load", () => {
    photoFrame.setAttribute("aria-busy", "false");
    photoFrame.dataset.photoState = "ready";
    photoState.hidden = true;
  });
  image.addEventListener("error", () => {
    if (!product) return;
    photoFrame.setAttribute("aria-busy", "false");
    photoFrame.dataset.photoState = "error";
    image.hidden = true;
    photoState.hidden = false;
    photoMessage.textContent = "This photograph couldn't load. You can try it again.";
    photoRetry.hidden = false;
  });
  photoRetry.addEventListener("click", () => {
    image.removeAttribute("src");
    showPhoto(activePhoto);
  });

  wishlistButton.addEventListener("click", () => {
    if (shopping.wishlist.has(product.key)) shopping.wishlist.delete(product.key);
    else shopping.wishlist.add(product.key);
    const saved = persistShopping();
    const isSaved = shopping.wishlist.has(product.key);
    wishlistButton.setAttribute("aria-pressed", String(isSaved));
    wishlistButton.textContent = isSaved ? "♥ Saved" : "♡ Wishlist";
    feedback.textContent = saved
      ? (isSaved ? "Added to your wishlist." : "Removed from your wishlist.")
      : `${isSaved ? "Added to" : "Removed from"} your wishlist for this visit.`;
  });

  window.addEventListener("velora:privacy-changed", () => {
    if (!window.VeloraPrivacy?.canSaveLooks()) shopping.wishlist.clear();
    persistShopping();
    if (product) {
      const saved = shopping.wishlist.has(product.key);
      wishlistButton.setAttribute("aria-pressed", String(saved));
      wishlistButton.textContent = saved ? "\u2665 Saved" : "\u2661 Wishlist";
    }
  });
  window.addEventListener("velora:device-data-cleared", () => {
    shopping = { wishlist: new Set(), cart: {} };
    updateBagLink();
    wishlistButton.setAttribute("aria-pressed", "false");
    wishlistButton.textContent = "\u2661 Wishlist";
    setFeedback("Your bag and saved looks have been cleared.");
  });
  window.addEventListener("pageshow", (event) => {
    if (!event.persisted) return;
    loadShopping();
    if (product) {
      const saved = shopping.wishlist.has(product.key);
      wishlistButton.setAttribute("aria-pressed", String(saved));
      wishlistButton.textContent = saved ? "\u2665 Saved" : "\u2661 Wishlist";
    }
  });
  async function loadCurrentProduct() {
    const version = ++loadVersion;
    main.setAttribute("aria-busy", "true");
    status.setAttribute("role", "status");
    status.textContent = "Loading product…";
    status.hidden = false;
    returnLink.hidden = true;
    content.hidden = true;
    mobileBar.hidden = true;
    reserveMobileBar();
    try {
      const loaded = await loadProduct();
      if (version !== loadVersion) return;
      if (!loaded) throw productError("This product link may be incomplete. Return to the collection to choose another piece.");
      product = loaded;
      renderProduct();
    } catch (error) {
      if (version !== loadVersion) return;
      const retryable = error?.retryable !== false;
      const message = error?.retryable === undefined
        ? "We couldn't connect to this piece right now. Check your connection and try again."
        : error.message;
      showUnavailable(message, retryable);
    }
  }
  loadShopping();
  loadCurrentProduct();
})();
