/* Business information is loaded on demand and saved through the protected API. */
(() => {
  "use strict";
  const $ = (selector) => document.querySelector(selector);
  const form = $("#admin-business-form");
  if (!form || !window.VeloraAuth) return;
  const fields = ["legalName", "country", "registrationNumber", "vatNumber", "businessAddress", "customerServiceEmail", "returnAddress"];
  const state = { saved: null, loading: null, busy: false, active: true };

  function values() {
    return Object.fromEntries(fields.map((name) => [name, form.elements.namedItem(name).value.trim()]));
  }

  function validDetails(details) {
    return details && typeof details === "object" && fields.every((name) => typeof details[name] === "string");
  }

  function dirty() {
    if (!state.saved) return false;
    const draft = values();
    return fields.some((name) => draft[name] !== state.saved[name]);
  }

  function syncControls() {
    const changed = dirty();
    $("#admin-business-discard").disabled = state.busy || !changed;
    $("#admin-business-save").disabled = state.busy;
    $("#admin-business-save").textContent = state.busy ? "Saving…" : "Save public details";
    $("#admin-business-save-state").textContent = changed ? "You have unsaved changes." : "Showing the saved public details.";
    form.setAttribute("aria-busy", String(state.busy));
  }

  function populate(details) {
    state.saved = Object.fromEntries(fields.map((name) => [name, details[name]]));
    for (const name of fields) form.elements.namedItem(name).value = details[name];
    syncControls();
  }

  function message(text, success = false) {
    const node = $("#admin-business-message");
    node.textContent = text;
    node.classList.toggle("is-success", Boolean(text) && success);
    node.classList.toggle("is-error", Boolean(text) && !success);
    node.setAttribute("role", success ? "status" : "alert");
  }

  function routeError(error) {
    if (error.status === 401) { location.replace("login.html?next=admin.html"); return true; }
    if (error.status === 403) { location.replace("account.html"); return true; }
    return false;
  }

  async function loadBusiness() {
    if (state.loading || state.saved) return state.loading;
    state.loading = (async () => {
      $("#admin-business-loading").textContent = "Loading your public business details…";
      $("#admin-business-loading").hidden = false;
      $("#admin-business-error").hidden = true;
      $("#admin-business-retry").disabled = true;
      try {
        const user = await window.VeloraAuth.ready;
        if (user?.role !== "admin") return;
        const { businessDetails } = await window.VeloraAuth.request("/api/admin/business-details");
        if (!state.active) return;
        if (!validDetails(businessDetails)) throw new Error("We couldn't read the saved business details. Please try again.");
        populate(businessDetails);
        form.hidden = false;
      } catch (error) {
        if (routeError(error)) return;
        $("#admin-business-error-message").textContent = error.status === 404
          ? "Business settings are unavailable on this server. Restart Velora with the latest project files and try again."
          : error.message || "We couldn't load your business details. Please try again.";
        $("#admin-business-error").hidden = false;
      } finally {
        $("#admin-business-loading").hidden = true;
        $("#admin-business-retry").disabled = false;
        state.loading = null;
      }
    })();
    return state.loading;
  }

  form.addEventListener("input", () => { message(""); syncControls(); });
  $("#admin-business-discard").addEventListener("click", () => {
    if (state.busy || !state.saved) return;
    populate(state.saved);
    message("Unsaved changes discarded. Your published details have not changed.", true);
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.busy || !state.saved || !form.reportValidity()) return;
    state.busy = true;
    const draft = values();
    form.querySelectorAll("input,textarea").forEach((field) => { field.disabled = true; });
    syncControls();
    message("");
    try {
      const { businessDetails } = await window.VeloraAuth.request("/api/admin/business-details", { method: "PATCH", body: draft });
      if (!state.active) return;
      if (!validDetails(businessDetails)) throw new Error("The server returned incomplete details. Reload this page to check what was saved.");
      populate(businessDetails);
      message("Business details saved. The saved information is now public.", true);
      window.dispatchEvent(new CustomEvent("velora:business-details-changed", { detail: { businessDetails } }));
    } catch (error) {
      if (!routeError(error)) message(error.message || "We couldn't save your business details. Your changes are still in the form.");
    } finally {
      state.busy = false;
      form.querySelectorAll("input,textarea").forEach((field) => { field.disabled = false; });
      syncControls();
    }
  });
  $("#admin-business-retry").addEventListener("click", loadBusiness);
  document.addEventListener("velora:admin-section", (event) => {
    if (event.detail?.section === "business") loadBusiness();
  });
  window.VeloraAuth.ready.then((user) => {
    if (user?.role === "admin" && location.hash === "#business") loadBusiness();
  }).catch(() => {});
  window.addEventListener("pagehide", () => { state.active = false; });
})();
