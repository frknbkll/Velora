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
  const storageKey = "velora-shopping-v1";
  const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

  let product;
  let colors = [];
  let selection = { color: "", size: "" };
  let photos = [];
  let activePhoto = 0;
  let shopping = { wishlist: new Set(), cart: {} };

  function showUnavailable(message) {
    status.replaceChildren();
    status.setAttribute("role", "alert");
    const heading = document.createElement("h1");
    heading.textContent = "This piece is unavailable";
    const explanation = document.createElement("p");
    explanation.textContent = message;
    status.append(heading, explanation);
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
      if (!id || id.length > 100) throw new Error("This product link is not valid.");
      const response = await fetch(`/api/catalog/${encodeURIComponent(id)}`, {
        cache: "no-store",
        signal: AbortSignal.timeout(10000),
      });
      if (response.status === 404) throw new Error("This product may have been unpublished or removed.");
      if (!response.ok) throw new Error("We couldn't load this product right now. Please try again.");
      const data = await response.json();
      if (!data.product || data.product.published !== true) throw new Error("This product is no longer available.");
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

  function persistShopping() {
    if (!window.VeloraPrivacy?.canSaveLooks()) return false;
    try {
      localStorage.setItem(storageKey, JSON.stringify({
        wishlist: [...shopping.wishlist],
        cart: shopping.cart,
      }));
      return true;
    } catch (error) {
      console.error("Could not save the Velora shopping state.", error);
      return false;
    }
  }

  function loadShopping() {
    if (!window.VeloraPrivacy?.canSaveLooks()) return;
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "{}");
      if (Array.isArray(saved.wishlist)) {
        shopping.wishlist = new Set(saved.wishlist.filter((key) => typeof key === "string" && key.length <= 1000));
      }
      if (saved.cart && typeof saved.cart === "object" && !Array.isArray(saved.cart)) {
        shopping.cart = Object.fromEntries(Object.entries(saved.cart).filter(
          ([key, quantity]) => key.length <= 1500 && Number.isInteger(quantity) && quantity > 0 && quantity <= 999999,
        ));
      }
    } catch (error) {
      console.error("Could not load the saved Velora shopping state.", error);
      feedback.textContent = "Saved bag and wishlist details could not be loaded.";
    }
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
    const candidates = [primary, ...(selected?.poses || []), ...(isBaseColor ? product.images || [product.image] : [])];
    return [...new Set(candidates.filter((photo) => typeof photo === "string" && photo))];
  }

  function showPhoto(index) {
    activePhoto = (index + photos.length) % photos.length;
    image.src = photos[activePhoto];
    image.alt = `${product.name}${selection.color ? ` in ${selection.color}` : ""} — photo ${activePhoto + 1}`;
    photoCount.textContent = photos.length > 1 ? `${activePhoto + 1} / ${photos.length}` : "";
    thumbnails.querySelectorAll("button").forEach((button, buttonIndex) => {
      button.setAttribute("aria-pressed", String(buttonIndex === activePhoto));
    });
  }

  function renderGallery() {
    photos = galleryPhotos();
    activePhoto = 0;
    thumbnails.replaceChildren();
    photos.forEach((photo, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute("aria-label", `Show photo ${index + 1} of ${photos.length}`);
      button.setAttribute("aria-pressed", String(index === 0));
      const thumbnail = document.createElement("img");
      thumbnail.src = photo;
      thumbnail.alt = "";
      thumbnail.loading = "lazy";
      button.append(thumbnail);
      button.addEventListener("click", () => showPhoto(index));
      thumbnails.append(button);
    });
    showPhoto(0);
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
    product.sizes = sizes;

    document.title = `${product.name} — Velora`;
    document.querySelector('meta[name="description"]').content = product.description || `Discover ${product.name} from Velora.`;
    document.querySelector("#product-page-title").textContent = product.name;
    document.querySelector("#product-page-collection").textContent = product.collection || "THE OPENING COLLECTION";
    document.querySelector("#product-page-byline").textContent = product.founder ? `Designed by ${product.founder}` : "From the Velora collection";
    document.querySelector("#product-page-price").textContent = currency.format(Number(product.price) || 0);
    document.querySelector("#product-page-description").textContent = product.description || "A considered piece from the Velora collection.";
    renderColors();
    renderSizes();
    renderGallery();
    renderStock();
    renderInformation();
    wishlistButton.setAttribute("aria-pressed", String(shopping.wishlist.has(product.key)));
    wishlistButton.textContent = shopping.wishlist.has(product.key) ? "♥ Saved" : "♡ Wishlist";
    status.hidden = true;
    content.hidden = false;
  }

  addButton.addEventListener("click", () => {
    const available = currentStock();
    const cartKey = `${product.key}::${encodeURIComponent(selection.color)}::${encodeURIComponent(selection.size)}`;
    const currentQuantity = shopping.cart[cartKey] || 0;
    if (available !== null && available !== undefined && currentQuantity >= available) {
      feedback.textContent = available === 0
        ? "This size and color is currently sold out."
        : `Only ${available} of this selection can be added to your bag.`;
      return;
    }
    shopping.cart[cartKey] = currentQuantity + 1;
    const saved = persistShopping();
    feedback.textContent = saved
      ? `Added ${product.name} to your shopping bag.`
      : "Added for this visit. To save your bag between visits, allow saved looks in your privacy preferences.";
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

  loadShopping();
  loadProduct().then((loaded) => {
    if (!loaded) {
      showUnavailable("This product link may be incomplete. Return to the collection to choose another piece.");
      return;
    }
    product = loaded;
    renderProduct();
  }).catch((error) => {
    console.error("Could not load the requested Velora product.", error);
    showUnavailable(error instanceof Error ? error.message : "We couldn't load this product right now.");
  });
})();
