(() => {
  "use strict";
  const KEY = "veloraPrivacyChoice";
  const SHOP_KEY = "velora-shopping-v1";
  const MAX_AGE = 180 * 24 * 60 * 60 * 1000;
  let current = null;
  let returnFocus = null;
  const remove = (key) => { try { localStorage.removeItem(key); } catch {} };
  const readChoice = () => {
    try {
      const item = JSON.parse(localStorage.getItem(KEY));
      if (item?.version === 1 && typeof item.savedLooks === "boolean" &&
          Number.isFinite(item.updatedAt) && Number.isFinite(item.expiresAt) &&
          item.updatedAt <= Date.now() && item.expiresAt > Date.now() &&
          item.expiresAt - item.updatedAt <= MAX_AGE) return item;
    } catch {}
    remove(KEY);
    remove(SHOP_KEY);
    return null;
  };
  current = readChoice();
  if (!current?.savedLooks) remove(SHOP_KEY);

  const banner = document.createElement("aside");
  banner.id = "privacy-banner";
  banner.className = "privacy-banner";
  banner.setAttribute("aria-labelledby", "privacy-banner-title");
  banner.hidden = Boolean(current);
  banner.innerHTML = `<div class="privacy-banner-copy">
    <h2 id="privacy-banner-title">Your privacy, your choice.</h2>
    <p>We use essential storage for sign-in and your privacy choice. With your permission, we can also remember your bag and wishlist on this device. No advertising or analytics trackers.</p>
    <a href="cookie-policy.html">Read our Cookie Policy</a>
  </div><div class="privacy-actions">
    <button type="button" data-privacy-choice="necessary">Necessary only</button>
    <button type="button" data-privacy-choice="saved">Allow saved looks</button>
    <button type="button" class="privacy-text-button" data-privacy-settings>Manage preferences</button>
  </div>`;
  const dialog = document.createElement("dialog");
  dialog.id = "privacy-settings";
  dialog.className = "privacy-dialog";
  dialog.setAttribute("aria-labelledby", "privacy-settings-title");
  dialog.innerHTML = `<form method="dialog" id="privacy-settings-form">
    <div class="privacy-dialog-heading"><h2 id="privacy-settings-title">Privacy preferences</h2>
      <button type="button" class="privacy-close" aria-label="Close privacy preferences">×</button></div>
    <p>You can browse, sign in and use the bag without optional storage. Change your choice here at any time.</p>
    <label class="privacy-option"><input type="checkbox" checked disabled /><span><strong>Essential storage</strong><span>Sign-in sessions and your privacy choice. Always active.</span></span></label>
    <label class="privacy-option"><input id="privacy-saved-looks" type="checkbox" /><span><strong>Remember bag and wishlist</strong><span>Save your chosen looks on this device for up to 180 days. Otherwise, they stay on this page until you leave or reload.</span></span></label>
    <p class="privacy-small">There are no analytics or marketing cookies to enable. <a href="privacy.html">Privacy Policy</a> · <a href="cookie-policy.html">Cookie Policy</a></p>
    <div class="privacy-actions"><button type="button" data-privacy-choice="necessary">Necessary only</button><button type="submit">Save preferences</button></div>
  </form>`;
  document.body.append(banner, dialog);
  const reserveSpace = () => document.documentElement.style.setProperty("--privacy-banner-height", banner.hidden ? "0px" : `${banner.getBoundingClientRect().height + 36}px`);
  if (typeof ResizeObserver !== "undefined") new ResizeObserver(reserveSpace).observe(banner);
  window.addEventListener("resize", reserveSpace);
  reserveSpace();

  const closeSettings = () => {
    dialog.close();
    if (returnFocus?.isConnected) returnFocus.focus({ preventScroll: true });
  };
  const openSettings = () => {
    returnFocus = document.activeElement;
    dialog.querySelector("#privacy-saved-looks").checked = Boolean(current?.savedLooks);
    if (!dialog.open) dialog.showModal();
  };
  const saveChoice = (savedLooks) => {
    const updatedAt = Date.now();
    current = { version: 1, savedLooks, updatedAt, expiresAt: updatedAt + MAX_AGE };
    try { localStorage.setItem(KEY, JSON.stringify(current)); } catch {}
    if (!savedLooks) remove(SHOP_KEY);
    const focusWasInBanner = banner.contains(document.activeElement);
    banner.hidden = true;
    reserveSpace();
    window.dispatchEvent(new CustomEvent("velora:privacy-changed", { detail: { savedLooks } }));
    if (dialog.open) closeSettings();
    else if (focusWasInBanner) document.querySelector("main")?.focus({ preventScroll: true });
  };
  const clearDeviceData = () => {
    remove(KEY);
    remove(SHOP_KEY);
    current = null;
    banner.hidden = false;
    reserveSpace();
    window.dispatchEvent(new CustomEvent("velora:privacy-changed", { detail: { savedLooks: false } }));
    window.dispatchEvent(new CustomEvent("velora:device-data-cleared"));
  };
  document.addEventListener("click", (event) => {
    const choice = event.target.closest?.("[data-privacy-choice]");
    if (choice) saveChoice(choice.dataset.privacyChoice === "saved");
    if (event.target.closest?.("[data-privacy-settings], [data-cookie-preferences]")) openSettings();
  });
  dialog.querySelector(".privacy-close").addEventListener("click", closeSettings);
  dialog.addEventListener("cancel", (event) => { event.preventDefault(); closeSettings(); });
  dialog.querySelector("form").addEventListener("submit", (event) => {
    event.preventDefault();
    saveChoice(dialog.querySelector("#privacy-saved-looks").checked);
  });
  window.addEventListener("storage", (event) => {
    if (event.key !== KEY && event.key !== null) return;
    current = readChoice();
    if (!current?.savedLooks) remove(SHOP_KEY);
    banner.hidden = Boolean(current);
    reserveSpace();
    window.dispatchEvent(new CustomEvent("velora:privacy-changed", { detail: { savedLooks: Boolean(current?.savedLooks) } }));
  });
  // Keep focused page controls above the non-modal banner without moving banner focus.
  document.addEventListener("focusin", (event) => {
    if (banner.hidden || banner.contains(event.target) || dialog.open || event.target.classList?.contains("skip-link")) return;
    const target = event.target.getBoundingClientRect?.();
    if (target && target.bottom > banner.getBoundingClientRect().top - 10) event.target.scrollIntoView({ block: "center", behavior: "instant" });
  });
  window.VeloraPrivacy = Object.freeze({
    canSaveLooks: () => Boolean(current?.savedLooks && current.expiresAt > Date.now()),
    openSettings,
    clearDeviceData,
  });

  const businessFields = document.querySelectorAll("[data-business-field]");
  if (businessFields.length) {
    fetch("/api/business-details", { credentials: "omit", headers: { Accept: "application/json" } })
      .then((response) => { if (!response.ok) throw new Error(); return response.json(); })
      .then(({ businessDetails }) => businessFields.forEach((node) => {
        const value = businessDetails?.[node.dataset.businessField];
        node.textContent = typeof value === "string" && value.trim() ? value : "Not yet provided";
      })).catch(() => {});
  }
})();
