(() => {
  "use strict";

  const sessionKey = "velora-session-bag-v1";
  const savedKey = "velora-shopping-v1";
  const currency = new Intl.NumberFormat("en-IE", {
    style: "currency", currency: "EUR", minimumFractionDigits: 0, maximumFractionDigits: 2,
  });
  const allowed = () => Boolean(window.VeloraPrivacy?.canSaveLooks());
  const cartEntries = (value) => {
    const entries = value instanceof Map ? [...value] : value && typeof value === "object" && !Array.isArray(value) ? Object.entries(value) : [];
    return entries.filter(([key, quantity]) => typeof key === "string" && key.length > 0 && key.length <= 1500 &&
      Number.isInteger(quantity) && quantity > 0 && quantity <= 999999).slice(0, 500);
  };
  const wishlistEntries = (value) => (value instanceof Set ? [...value] : Array.isArray(value) ? value : [])
    .filter((key) => typeof key === "string" && key.length > 0 && key.length <= 1000).slice(0, 500);

  function read() {
    let persistent = {}, session = null, readError = false;
    if (allowed()) {
      try { persistent = JSON.parse(localStorage.getItem(savedKey) || "{}"); }
      catch { readError = true; }
    }
    try {
      const raw = sessionStorage.getItem(sessionKey);
      if (raw !== null) session = JSON.parse(raw);
    } catch { readError = true; }
    const cart = new Map(cartEntries(session?.cart ?? persistent?.cart));
    // Import an opted-in saved bag into the active tab once; an empty session
    // bag stays authoritative when products have subsequently been removed.
    if (session === null && cart.size) {
      try { sessionStorage.setItem(sessionKey, JSON.stringify({ cart: Object.fromEntries(cart) })); }
      catch { /* The page remains usable when storage is unavailable. */ }
    }
    return { wishlist: new Set(allowed() ? wishlistEntries(persistent?.wishlist) : []), cart, readError };
  }

  function save({ wishlist, cart }) {
    const cleanCart = Object.fromEntries(cartEntries(cart));
    let sessionSaved = false, persistentSaved = !allowed();
    try { sessionStorage.setItem(sessionKey, JSON.stringify({ cart: cleanCart })); sessionSaved = true; }
    catch { /* Callers show that this page's changes could not be retained. */ }
    try {
      if (allowed()) {
        localStorage.setItem(savedKey, JSON.stringify({ wishlist: wishlistEntries(wishlist), cart: cleanCart }));
        persistentSaved = true;
      } else localStorage.removeItem(savedKey);
    } catch { /* Optional persistence can fail independently of the session bag. */ }
    return sessionSaved && persistentSaved;
  }

  function clear() {
    try { sessionStorage.removeItem(sessionKey); } catch {}
    try { localStorage.removeItem(savedKey); } catch {}
  }

  window.addEventListener("velora:device-data-cleared", clear);
  window.VeloraShopping = Object.freeze({ read, save, clear, currency, sessionKey, savedKey });
})();
