/* Privacy controls use the account API and never store credentials in the browser. */
(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const dialog = $("#account-delete-dialog");
  const form = $("#account-delete-form");
  if (!dialog || !form || !window.VeloraAuth) return;
  const state = { busy: false, checking: false, active: true, returnFocus: null };

  function message(selector, text, success = false) {
    const node = $(selector);
    node.textContent = text;
    node.classList.toggle("is-error", Boolean(text) && !success);
    node.classList.toggle("is-success", Boolean(text) && success);
    node.setAttribute("role", success ? "status" : "alert");
  }

  function setBusy(busy) {
    state.busy = busy;
    form.setAttribute("aria-busy", String(busy));
    form.querySelectorAll("button").forEach((button) => { button.disabled = busy; });
    $("#account-delete-confirm").textContent = busy ? "Deleting account…" : "Permanently delete account";
  }

  async function clearDeviceData() {
    if (window.VeloraPrivacy?.clearDeviceData) {
      await window.VeloraPrivacy.clearDeviceData();
      return;
    }
    // The shared privacy controls normally handle this, including in other tabs.
    // Keep the account usable if that optional script cannot be loaded.
    try { localStorage.removeItem("velora-shopping-v1"); } catch { /* Storage may be unavailable. */ }
    window.dispatchEvent(new CustomEvent("velora:clear-device-data"));
  }

  function closeDelete() {
    if (state.busy) return;
    dialog.close();
    form.reset();
    message("#account-delete-message", "");
    state.returnFocus?.focus();
  }

  $("#privacy-clear-device").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      await clearDeviceData();
      message("#privacy-message", "Your saved wishlist, preview bag and cookie choices have been cleared on this device. Your account is still signed in.", true);
    } catch {
      message("#privacy-message", "We couldn't clear all device data. You can also remove this site's data in your browser settings.");
    } finally { button.disabled = false; }
  });

  $("#privacy-cookie-settings").addEventListener("click", () => {
    if (window.VeloraPrivacy?.openSettings) window.VeloraPrivacy.openSettings();
    else location.assign("cookie-policy.html");
  });

  $("#privacy-delete-open").addEventListener("click", async (event) => {
    if (state.checking || state.busy) return;
    state.checking = true;
    const button = event.currentTarget;
    state.returnFocus = button;
    button.disabled = true;
    message("#privacy-message", "");
    try {
      const status = await window.VeloraAuth.request("/api/security/status");
      if (!state.active) return;
      if (typeof status.mfaEnabled !== "boolean") throw new Error("We couldn't check your account. Refresh and try again.");
      form.reset();
      $("#account-delete-factor").hidden = !status.mfaEnabled;
      $("#account-delete-code").required = status.mfaEnabled;
      message("#account-delete-message", "");
      dialog.showModal();
      $("#account-delete-cancel").focus();
    } catch (error) {
      if (error.status === 401) location.assign("login.html?next=account.html");
      else message("#privacy-message", error.message || "We couldn't check your account. Please try again.");
    } finally {
      state.checking = false;
      button.disabled = false;
    }
  });

  $("#account-delete-cancel").addEventListener("click", closeDelete);
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeDelete();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.busy || !form.reportValidity()) return;
    const fields = new FormData(form);
    const body = { password: fields.get("password") };
    if (!$("#account-delete-factor").hidden) body.code = fields.get("code").trim();
    setBusy(true);
    message("#account-delete-message", "");
    try {
      await window.VeloraAuth.request("/api/account", { method: "DELETE", body });
      form.reset();
      window.VeloraAuth.user = null;
      window.VeloraAuth.csrfToken = null;
      try { await clearDeviceData(); } catch { /* Server deletion already succeeded. */ }
      location.replace("login.html?deleted=1");
    } catch (error) {
      if (error.status === 401) location.assign("login.html?next=account.html");
      else {
        message("#account-delete-message", error.message || "Your account could not be deleted. Please try again.");
        $("#account-delete-password").value = "";
        $("#account-delete-code").value = "";
        $("#account-delete-password").focus();
      }
    } finally { setBusy(false); }
  });

  window.addEventListener("pagehide", () => {
    state.active = false;
    form.reset();
    if (dialog.open) dialog.close();
  });
})();
