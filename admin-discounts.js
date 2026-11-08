/* Seasonal campaigns are saved explicitly; templates start as inactive drafts. */
(() => {
  "use strict";
  const $ = (selector) => document.querySelector(selector);
  const panel = $("#admin-discounts");
  if (!panel || !window.VeloraAuth) return;
  const presets = [
    { id: "black-friday", name: "Black Friday", code: "BLACKFRIDAY20", amount: 20, caption: "A considered seasonal event", mark: "BF" },
    { id: "halloween", name: "Halloween", code: "SPOOKY15", amount: 15, caption: "A little autumn magic", mark: "31" },
    { id: "christmas", name: "Christmas", code: "GIFT15", amount: 15, caption: "Something worth giving", mark: "25" },
    { id: "new-year", name: "New Year", code: "FRESH15", amount: 15, caption: "A fresh beginning", mark: "01" },
    { id: "summer", name: "Summer", code: "SUMMER20", amount: 20, caption: "Long days, lighter moments", mark: "S" },
    { id: "custom", name: "Your own theme", code: "", amount: 10, caption: "Make a moment of your own", mark: "+" },
  ];
  const state = { discounts: [], loaded: false, loading: false, saving: false, editing: null };
  const money = (amount) => new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR" }).format(amount);
  const formatDate = (value) => value ? new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value)) : "";
  function el(tag, cls, text) { const node = document.createElement(tag); if (cls) node.className = cls; if (text !== undefined) node.textContent = text; return node; }
  function button(text, fn, cls = "admin-button admin-button-secondary") { const node = el("button", cls, text); node.type = "button"; node.addEventListener("click", fn); return node; }
  function message(text, editor = false, success = false) {
    const node = $(editor ? "#discount-editor-message" : "#discounts-message");
    node.textContent = text; node.classList.toggle("is-success", Boolean(text) && success); node.classList.toggle("is-error", Boolean(text) && !success); node.setAttribute("role", success ? "status" : "alert");
  }
  function errorMessage(error, editor = false) {
    if (error.status === 401) { location.replace("login.html?next=admin.html"); return; }
    message(error.status === 403 ? "An owner or store manager can manage discount codes." : error.message || "We couldn't save this discount. Please try again.", editor);
  }
  function status(discount) {
    if (!discount.active) return "Inactive";
    if (discount.endsAt && Date.parse(discount.endsAt) <= Date.now()) return "Expired";
    if (discount.startsAt && Date.parse(discount.startsAt) > Date.now()) return "Scheduled";
    return "Active";
  }
  function offer(discount) { return discount.type === "percent" ? `${discount.amount}% off` : `${money(discount.amount)} off`; }
  function localDate(value) {
    if (!value) return "";
    const date = new Date(value);
    return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  }
  function render() {
    const query = $("#discounts-search").value.trim().toLocaleLowerCase();
    const filtered = state.discounts.filter((discount) => `${discount.code} ${discount.name} ${discount.theme} ${status(discount)}`.toLocaleLowerCase().includes(query));
    $("#discounts-total").textContent = String(state.discounts.length);
    $("#discounts-active").textContent = String(state.discounts.filter((item) => status(item) === "Active").length);
    $("#discounts-scheduled").textContent = String(state.discounts.filter((item) => status(item) === "Scheduled").length);
    $("#discounts-count").textContent = `${filtered.length} of ${state.discounts.length} codes`;
    const rows = filtered.map((discount) => {
      const row = el("tr"); row.dataset.discountId = discount.id;
      const identity = el("td"), copy = el("div", "discount-code-identity"); copy.append(el("strong", "", discount.code), el("span", "", discount.name)); identity.append(copy);
      const theme = presets.find((item) => item.id === discount.theme);
      const themeCell = el("td"); themeCell.append(el("span", `discount-theme-label theme-${theme?.id || "custom"}`, theme?.name || "Custom"));
      const rules = el("td", "discount-code-rules"); rules.append(el("span", "", discount.minSubtotal ? `From ${money(discount.minSubtotal)}` : "No minimum spend"));
      if (discount.startsAt) rules.append(el("small", "", `Starts ${formatDate(discount.startsAt)}`));
      if (discount.endsAt) rules.append(el("small", "", `Ends ${formatDate(discount.endsAt)}`));
      const label = status(discount), statusCell = el("td"); statusCell.append(el("span", `discount-status is-${label.toLowerCase()}`, label));
      const actions = el("td"), controls = el("div", "discount-code-actions");
      const edit = button("Edit", () => openEditor(discount)); edit.disabled = state.saving; edit.setAttribute("aria-label", `Edit discount ${discount.code}`);
      const toggle = button(discount.active ? "Deactivate" : "Activate", () => toggleCode(discount)); toggle.disabled = state.saving; toggle.setAttribute("aria-label", `${discount.active ? "Deactivate" : "Activate"} discount ${discount.code}`);
      controls.append(edit, toggle); actions.append(controls); row.append(identity, themeCell, el("td", "discount-code-offer", offer(discount)), rules, statusCell, actions); return row;
    });
    if (!rows.length) { const row = el("tr"), cell = el("td", "discounts-empty", query ? "No codes match that search." : "Your next occasion starts here. Choose a theme or create a code."); cell.colSpan = 6; row.append(cell); rows.push(row); }
    $("#discounts-rows").replaceChildren(...rows);
  }
  async function load(force = false) {
    if (state.loading || (state.loaded && !force)) return;
    state.loading = true; $("#discounts-refresh").disabled = true; panel.setAttribute("aria-busy", "true"); message("");
    try {
      const user = await window.VeloraAuth.ready;
      if (user?.role !== "admin") return;
      const result = await window.VeloraAuth.request("/api/admin/discounts");
      if (!Array.isArray(result.discounts)) throw new Error("We couldn't read your saved discounts.");
      state.discounts = result.discounts; state.loaded = true; render();
    } catch (error) { if (error.status === 403) { state.discounts = []; render(); } errorMessage(error); }
    finally { state.loading = false; $("#discounts-refresh").disabled = false; panel.setAttribute("aria-busy", "false"); }
  }
  async function toggleCode(discount) {
    if (state.saving) return; state.saving = true; render(); message("");
    try { await window.VeloraAuth.request(`/api/admin/discounts/${encodeURIComponent(discount.id)}`, { method: "PATCH", body: { active: !discount.active } }); await load(true); message(`${discount.code} ${discount.active ? "deactivated" : "activated"}.`, false, true); }
    catch (error) { errorMessage(error); }
    finally { state.saving = false; render(); }
  }

  const dialog = el("dialog", "admin-edit-dialog discount-editor"); dialog.id = "discount-editor"; dialog.setAttribute("aria-labelledby", "discount-editor-title");
  const heading = el("div", "admin-edit-heading"), headingCopy = el("div"); headingCopy.append(el("p", "admin-eyebrow", "A MOMENT WORTH MARKING"));
  const title = el("h2", "", "Create a discount"); title.id = "discount-editor-title"; headingCopy.append(title);
  const close = button("×", closeEditor, "admin-dialog-close"); close.setAttribute("aria-label", "Close discount editor"); heading.append(headingCopy, close); dialog.append(heading);
  const form = el("form", "discount-editor-form"); form.id = "discount-editor-form";
  const fields = {};
  function field(name, label, type, options) {
    const wrap = el("label", `admin-field discount-field-${name}`, label), input = el(type === "select" ? "select" : "input");
    input.id = `discount-${name}`; input.name = name;
    if (type === "select") options.forEach(([value, text]) => { const option = el("option", "", text); option.value = value; input.append(option); }); else input.type = type;
    wrap.append(input); fields[name] = input; form.append(wrap); return input;
  }
  field("name", "Campaign name", "text").required = true; fields.name.maxLength = 100;
  field("theme", "Theme", "select", presets.map((item) => [item.id, item.name]));
  field("code", "Discount code", "text"); fields.code.maxLength = 40; fields.code.pattern = "[A-Za-z0-9-]{3,40}"; fields.code.autocomplete = "off"; fields.code.placeholder = "Leave blank to generate a code";
  field("type", "Offer type", "select", [["percent", "Percentage off"], ["fixed", "Fixed amount in EUR"]]);
  field("amount", "Discount amount", "number").required = true; fields.amount.step = ".01";
  field("minSubtotal", "Minimum spend (EUR)", "number"); fields.minSubtotal.min = "0"; fields.minSubtotal.max = "1000000"; fields.minSubtotal.step = ".01";
  field("startsAt", "Starts at (your local time)", "datetime-local"); field("endsAt", "Ends at (your local time)", "datetime-local");
  const enabled = el("label", "discount-enabled"), checkbox = el("input"); checkbox.type = "checkbox"; checkbox.id = "discount-active"; checkbox.name = "active"; fields.active = checkbox;
  const enabledCopy = el("span"); enabledCopy.append(el("strong", "", "Activate this code"), el("small", "", "Inactive drafts cannot be applied. Dates and minimum spend still apply when activated.")); enabled.append(checkbox, enabledCopy); form.append(enabled);
  const notice = el("p", "discount-editor-note", "A template is a starting point. Review the offer and choose when it should be available."); form.append(notice);
  const feedback = el("p", "discount-feedback"); feedback.id = "discount-editor-message"; feedback.setAttribute("role", "status"); feedback.setAttribute("aria-live", "polite"); form.append(feedback);
  const actions = el("div", "discount-editor-actions"), cancel = button("Cancel", closeEditor), save = el("button", "admin-button", "Save code"); save.type = "submit"; save.id = "discount-save"; actions.append(cancel, save); form.append(actions); dialog.append(form); document.body.append(dialog);
  function syncAmount() { fields.amount.min = fields.type.value === "percent" ? "1" : ".01"; fields.amount.max = fields.type.value === "percent" ? "100" : "100000"; }
  function busy(value) { state.saving = value; form.setAttribute("aria-busy", String(value)); form.querySelectorAll("input,select,button").forEach((input) => { input.disabled = value; }); close.disabled = value; save.textContent = value ? "Saving code…" : "Save code"; }
  function closeEditor() { if (!state.saving) { dialog.close(); form.reset(); state.editing = null; } }
  function openEditor(discount = null, preset = null) {
    if (state.saving) return;
    const template = preset || presets[presets.length - 1]; state.editing = discount?.id || null; form.reset();
    fields.name.value = discount?.name || (preset ? `${template.name} edit` : ""); fields.theme.value = discount?.theme || template.id;
    fields.code.value = discount?.code || template.code; fields.type.value = discount?.type || "percent"; fields.amount.value = discount?.amount ?? template.amount;
    fields.minSubtotal.value = discount?.minSubtotal ?? 0; fields.startsAt.value = localDate(discount?.startsAt); fields.endsAt.value = localDate(discount?.endsAt); fields.active.checked = discount?.active || false;
    title.textContent = discount ? "Edit this occasion" : "Create a discount"; fields.endsAt.setCustomValidity(""); message("", true); syncAmount(); dialog.showModal(); fields.name.focus();
  }
  fields.type.addEventListener("change", syncAmount);
  fields.code.addEventListener("input", () => { fields.code.value = fields.code.value.toUpperCase(); });
  fields.endsAt.addEventListener("input", () => fields.endsAt.setCustomValidity("")); fields.startsAt.addEventListener("input", () => fields.endsAt.setCustomValidity(""));
  dialog.addEventListener("cancel", (event) => { if (state.saving) event.preventDefault(); });
  form.addEventListener("submit", async (event) => {
    event.preventDefault(); if (state.saving) return;
    if (fields.startsAt.value && fields.endsAt.value && Date.parse(fields.endsAt.value) <= Date.parse(fields.startsAt.value)) fields.endsAt.setCustomValidity("Choose an end time after the start time.");
    if (!form.reportValidity()) return;
    const payload = { name: fields.name.value.trim(), code: fields.code.value.trim().toUpperCase(), theme: fields.theme.value, type: fields.type.value,
      amount: Number(fields.amount.value), minSubtotal: Number(fields.minSubtotal.value || 0), startsAt: fields.startsAt.value ? new Date(fields.startsAt.value).toISOString() : null,
      endsAt: fields.endsAt.value ? new Date(fields.endsAt.value).toISOString() : null, active: fields.active.checked };
    busy(true); message("", true);
    try { await window.VeloraAuth.request(state.editing ? `/api/admin/discounts/${encodeURIComponent(state.editing)}` : "/api/admin/discounts", { method: state.editing ? "PATCH" : "POST", body: payload }); busy(false); closeEditor(); await load(true); message("Discount code saved.", false, true); }
    catch (error) { errorMessage(error, true); }
    finally { busy(false); render(); }
  });
  $("#discounts-templates").replaceChildren(...presets.map((preset) => {
    const template = button("", () => openEditor(null, preset), `discount-template theme-${preset.id}`); template.setAttribute("aria-label", `Create a ${preset.name} discount draft`);
    template.append(el("span", "discount-template-mark", preset.mark), el("strong", "", preset.name), el("span", "discount-template-caption", preset.caption), el("span", "discount-template-link", "Use theme ↗")); return template;
  }));
  $("#discounts-new").addEventListener("click", () => openEditor()); $("#discounts-refresh").addEventListener("click", () => load(true)); $("#discounts-search").addEventListener("input", render);
  document.addEventListener("velora:admin-section", (event) => { if (event.detail?.section === "discounts") load(); });
  window.VeloraAuth.ready.then((user) => { if (user?.role === "admin" && location.hash === "#discounts") load(); }).catch(() => {});
  window.addEventListener("pagehide", () => { dialog.close(); form.reset(); });
})();
