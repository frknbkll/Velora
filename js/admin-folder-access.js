/* Velora colleague accounts and folder grants are enforced by the protected API. */
(() => {
  "use strict";
  const $ = (selector) => document.querySelector(selector);
  const panel = $("#admin-folder-access"), dialog = $("#admin-folder-access-dialog"), form = $("#admin-folder-access-form");
  if (!panel || !dialog || !form || !window.VeloraAuth) return;
  const state = { departments: [], colleagues: [], loaded: false, loading: false, saving: false, editing: null, mode: "edit", active: true, grants: new Map() };
  const activeInput = $("#admin-folder-access-active"), departmentInput = $("#admin-folder-access-department"), roleInput = $("#admin-folder-access-role");
  const refresh = $("#admin-folder-access-refresh"), create = $("#admin-colleague-create"), createFields = $("#admin-colleague-create-fields");
  const emailInput = $("#admin-colleague-email"), passwordInput = $("#admin-colleague-password");
  const rows = $("#admin-folder-access-rows"), permissionFields = $("#admin-folder-access-permissions");
  const roles = { colleague: "Colleague", manager: "Store manager", warehouse: "Warehouse", owner: "Full control" };
  if (!roleInput || !create || !createFields || !emailInput || !passwordInput) return;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function message(text, editor = false, success = false) {
    const node = $(editor ? "#admin-folder-access-edit-message" : "#admin-folder-access-message");
    node.textContent = text;
    node.classList.toggle("is-success", Boolean(text) && success);
    node.classList.toggle("is-error", Boolean(text) && !success);
    node.setAttribute("role", success ? "status" : "alert");
  }
  function routeError(error, editor = false) {
    if (error.status === 401) { location.replace("login.html?next=admin.html"); return; }
    message(error.status === 403 ? "Only a Velora owner can create colleague accounts or change their access."
      : error.status === 404 ? "Colleague account management is unavailable on this server. Restart Velora with the latest project files and try again."
        : error.message || "We couldn't load colleague access. Please try again.", editor);
  }
  function departmentName(id) { return state.departments.find((item) => item.id === id)?.name || "Not assigned"; }
  function isVeloraAccount(person) { return person.accountType === "velora" && /^[^\s@]+@velora\.com$/i.test(person.email || ""); }
  function emptyRow(text) {
    const row = el("tr"), cell = el("td", "folder-access-empty", text);
    cell.colSpan = 5; row.append(cell); return row;
  }
  function render() {
    const query = $("#admin-folder-access-search").value.trim().toLocaleLowerCase();
    const matches = state.colleagues.filter((person) => `${person.name} ${person.email} ${departmentName(person.department)} ${roles[person.role] || "Colleague"}`.toLocaleLowerCase().includes(query));
    rows.replaceChildren(...matches.map((person) => {
      const row = el("tr"); row.dataset.colleagueId = person.id;
      const identity = el("td"), copy = el("div", "folder-access-person");
      copy.append(el("strong", "", person.name), el("span", "", person.email)); identity.append(copy);
      const status = el("td");
      status.append(el("span", `admin-status${person.active ? " is-published" : ""}`, person.active ? "Enabled" : "Disabled"));
      status.append(el("small", `folder-access-role-label${person.fullControl ? " is-full-control" : ""}`, roles[person.role] || "Colleague"));
      const summary = el("td"), grants = Array.isArray(person.grants) ? person.grants : [], chips = el("div", "folder-access-grants");
      if (person.active && person.fullControl) {
        chips.append(el("span", "folder-access-grant is-full-control", "All shared folders · Manage"));
        summary.append(chips, el("small", "folder-access-summary-note", "Includes Finance and Human Resources"));
      } else {
        (person.active ? grants.filter((grant) => grant.folder !== "company" || grant.access === "write") : []).forEach((grant) => {
          const department = state.departments.find((item) => item.id === grant.folder);
          if (department) chips.append(el("span", `folder-access-grant${department.sensitive ? " is-sensitive" : ""}`, `${department.name} · ${grant.access === "write" ? "Manage" : "Read"}`));
        });
        summary.append(chips, el("small", "folder-access-summary-note", person.active ? "Company library · Read included" : "Sign-in and colleague access disabled"));
      }
      const action = el("td"), edit = el("button", "admin-button admin-button-secondary folder-access-edit", "Edit access");
      edit.type = "button"; edit.setAttribute("aria-label", `Edit access for ${person.name}`);
      edit.addEventListener("click", () => openEditor(person)); action.append(edit);
      row.append(identity, el("td", "folder-access-department", departmentName(person.department)), status, summary, action);
      return row;
    }));
    if (!matches.length) rows.append(emptyRow(query ? "No Velora colleague accounts match this search." : "No Velora colleague accounts yet. Create an @velora.com account to get started."));
    $("#admin-folder-access-count").textContent = `${matches.length} of ${state.colleagues.length} Velora accounts · ${state.colleagues.filter((person) => person.active).length} enabled colleagues`;
  }
  async function load(force = false) {
    if (state.loading || (state.loaded && !force)) return;
    state.loading = true; refresh.disabled = true; create.disabled = true; panel.setAttribute("aria-busy", "true"); message("");
    if (!state.loaded) rows.replaceChildren(emptyRow("Loading Velora colleague accounts…"));
    try {
      const user = await window.VeloraAuth.ready;
      if (user?.role !== "admin") return;
      const result = await window.VeloraAuth.request("/api/admin/folder-access");
      if (!state.active) return;
      if (!Array.isArray(result.departments) || !Array.isArray(result.colleagues)) throw new Error("We couldn't read the saved colleague accounts. Please try again.");
      state.departments = result.departments; state.colleagues = result.colleagues.filter(isVeloraAccount); state.loaded = true; render();
    } catch (error) {
      if (error.status === 403) {
        state.colleagues = []; state.loaded = false;
        if (!state.saving) closeEditor();
        rows.replaceChildren(emptyRow("Colleague account management is available to owners only."));
        $("#admin-folder-access-count").textContent = "Owner permission required";
      } else if (!state.loaded) rows.replaceChildren(emptyRow("Colleague accounts could not be loaded. Use Refresh colleagues to retry."));
      routeError(error);
    } finally {
      state.loading = false; refresh.disabled = false; create.disabled = !state.loaded; panel.setAttribute("aria-busy", "false");
    }
  }
  function syncControls() {
    const enabled = activeInput.checked, fullControl = roleInput.value === "owner";
    const editingSelf = state.mode === "edit" && state.editing === window.VeloraAuth.user?.id;
    departmentInput.required = enabled; departmentInput.disabled = state.saving || !enabled;
    activeInput.disabled = state.saving || editingSelf; roleInput.disabled = state.saving || editingSelf;
    $("#admin-folder-access-full-control").hidden = !fullControl;
    $("#admin-folder-access-role-description").textContent = fullControl
      ? "Full control includes every admin area and management of every department folder, including Finance and Human Resources."
      : roleInput.value === "manager" ? "Store managers can manage the collection, stock, orders, returns and discount codes. Folder access follows the permissions below."
        : roleInput.value === "warehouse" ? "Warehouse accounts can use fulfillment tools. Folder access follows the permissions below."
          : "Colleagues can use the intranet and their permitted shared folders. They do not receive admin panel access.";
    createFields.querySelectorAll("input").forEach((input) => { input.disabled = state.saving || state.mode !== "create"; });
    permissionFields.querySelectorAll("select").forEach((select) => {
      const department = state.departments.find((item) => item.id === select.dataset.folder);
      const restricted = !fullControl && department.sensitive && departmentInput.value !== department.id;
      if (restricted) state.grants.delete(department.id);
      select.value = fullControl ? "write" : restricted ? "" : state.grants.get(department.id) || (department.id === "company" ? "read" : "");
      select.disabled = state.saving || !enabled || fullControl || restricted;
      select.closest(".folder-access-permission").classList.toggle("is-restricted", restricted);
      select.closest(".folder-access-permission").classList.toggle("is-included", fullControl);
      select.closest(".folder-access-permission").querySelector("small").textContent = fullControl ? "Manage access is included with Full control"
        : restricted ? `Requires ${department.name} as the primary department` : department.id === "company" ? "Read access is included for enabled colleagues"
          : department.sensitive ? "Matching department and explicit permission required" : "Grant the access this colleague needs";
    });
    $("#admin-folder-access-save").disabled = state.saving;
    $("#admin-folder-access-save").textContent = state.saving ? "Saving account…" : state.mode === "create" ? "Create Velora account" : "Save access";
    $("#admin-folder-access-close").disabled = state.saving; $("#admin-folder-access-cancel").disabled = state.saving;
    form.setAttribute("aria-busy", String(state.saving));
  }
  function fillPermissions() {
    permissionFields.replaceChildren(...state.departments.map((department) => {
      const label = el("label", "folder-access-permission"), copy = el("span", "folder-access-permission-copy");
      copy.append(el("strong", "", department.name));
      if (department.sensitive) copy.append(el("span", "folder-access-sensitive-label", "Restricted"));
      copy.append(el("small", "", ""));
      const select = el("select"); select.dataset.folder = department.id; select.setAttribute("aria-label", `${department.name} folder permission`);
      (department.id === "company" ? [["read", "Read · included"], ["write", "Manage files"]] : [["", "No access"], ["read", "Read files"], ["write", "Manage files"]]).forEach(([value, title]) => {
        const option = el("option", "", title); option.value = value; select.append(option);
      });
      label.append(copy, select); return label;
    }));
  }
  function openEditor(person = null) {
    if (state.saving || !state.loaded) return;
    form.reset(); emailInput.setCustomValidity("");
    state.mode = person ? "edit" : "create"; state.editing = person?.id ?? null;
    state.grants = new Map((person?.grants || []).map((grant) => [grant.folder, grant.access]));
    $("#admin-folder-access-dialog-title").textContent = person ? "Edit colleague access" : "Create a Velora account";
    createFields.hidden = Boolean(person); $("#admin-folder-access-identity").hidden = !person;
    $("#admin-folder-access-name").textContent = person?.name || ""; $("#admin-folder-access-email").textContent = person?.email || "";
    activeInput.checked = person ? Boolean(person.active) : true; roleInput.value = person?.role || "colleague";
    const placeholder = el("option", "", "Choose a department"); placeholder.value = "";
    departmentInput.replaceChildren(placeholder, ...state.departments.filter((item) => item.id !== "company").map((department) => {
      const option = el("option", "", department.name); option.value = department.id; return option;
    }));
    departmentInput.value = person?.department || ""; fillPermissions(); message("", true); syncControls(); dialog.showModal();
    (person ? departmentInput : $("#admin-colleague-first-name")).focus();
  }
  function clearPassword() { passwordInput.value = ""; }
  function closeEditor() {
    if (state.saving) return;
    dialog.close(); state.editing = null; clearPassword();
  }
  emailInput.addEventListener("input", () => {
    const email = emailInput.value.trim();
    emailInput.setCustomValidity(!email || /^[^\s@]+@velora\.com$/i.test(email) ? "" : "Use a colleague work email ending with @velora.com.");
  });
  form.addEventListener("change", (event) => {
    if (event.target.matches("select[data-folder]")) state.grants.set(event.target.dataset.folder, event.target.value);
    syncControls(); message("", true);
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.saving || (state.mode === "edit" && state.editing === null) || !form.reportValidity()) return;
    const creating = state.mode === "create", enabled = activeInput.checked, fullControl = roleInput.value === "owner";
    const payload = {
      active: enabled, department: departmentInput.value || null, role: roleInput.value, fullControl,
      grants: enabled && !fullControl ? [...permissionFields.querySelectorAll("select")].filter((select) => !select.disabled && select.value && !(select.dataset.folder === "company" && select.value === "read")).map((select) => ({ folder: select.dataset.folder, access: select.value })) : [],
    };
    if (creating) Object.assign(payload, { firstName: $("#admin-colleague-first-name").value.trim(), lastName: $("#admin-colleague-last-name").value.trim(), email: emailInput.value.trim().toLowerCase(), password: passwordInput.value });
    const editing = state.editing; state.saving = true; message("", true); syncControls();
    try {
      const result = await window.VeloraAuth.request(creating ? "/api/admin/colleagues" : `/api/admin/colleagues/${encodeURIComponent(editing)}`, { method: creating ? "POST" : "PATCH", body: payload });
      if (!result.colleague || (!creating && result.colleague.id !== editing) || !isVeloraAccount(result.colleague)) throw new Error("Refresh colleague accounts to check the saved access.");
      clearPassword();
      if (!state.active) return;
      const index = state.colleagues.findIndex((person) => person.id === result.colleague.id);
      if (index >= 0) state.colleagues[index] = result.colleague; else state.colleagues.push(result.colleague);
      state.colleagues.sort((a, b) => a.name.localeCompare(b.name)); render(); dialog.close(); state.editing = null;
      message(`${creating ? "Velora account created" : "Access saved"} for ${result.colleague.name}. ${result.colleague.active ? "The account permissions apply immediately." : "Sign-in is disabled."}`, false, true);
      document.dispatchEvent(new CustomEvent("velora:folder-access-changed", { detail: { colleague: result.colleague } }));
    } catch (error) { if (state.active) routeError(error, true); }
    finally { delete payload.password; state.saving = false; syncControls(); }
  });
  $("#admin-folder-access-close").addEventListener("click", closeEditor);
  $("#admin-folder-access-cancel").addEventListener("click", closeEditor);
  dialog.addEventListener("cancel", (event) => { if (state.saving) event.preventDefault(); });
  dialog.addEventListener("close", clearPassword);
  $("#admin-folder-access-search").addEventListener("input", () => { if (state.loaded) render(); });
  refresh.addEventListener("click", () => load(true)); create.addEventListener("click", () => openEditor());
  document.addEventListener("velora:admin-section", (event) => { if (event.detail?.section === "folder-access") load(); });
  window.VeloraAuth.ready.then((user) => { if (user?.role === "admin" && location.hash === "#folder-access") load(); }).catch(() => {});
  window.addEventListener("pagehide", () => { state.active = false; clearPassword(); form.reset(); if (dialog.open) dialog.close(); });
})();
