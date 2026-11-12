/* Customer care: private account/guest conversations, with live staff replies. */
(() => {
  "use strict";
  if (document.querySelector("#support-chat")) return;
  const state = { active: true, initialized: false, connecting: null, polling: false, sending: false, deleting: false, token: null, customer: null, conversation: null, messages: [], nodes: new Map(), after: 0, before: null, lastRead: 0, timer: null, generation: 0, authId: window.VeloraAuth?.user?.id, pending: null };
  const storageKey = "velora-support-panel";
  const timeFormat = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  function el(tag, className, text) { const node = document.createElement(tag); if (className) node.className = className; if (text !== undefined) node.textContent = text; return node; }
  function identified(tag, id, className, text) { const node = el(tag, className, text); node.id = id; return node; }
  function button(id, className, text) { const node = identified("button", id, className, text); node.type = "button"; return node; }
  const launcher = button("support-launcher", "support-launcher", "Chat with us");
  launcher.dataset.supportOpen = "";
  launcher.setAttribute("aria-controls", "support-chat");
  launcher.setAttribute("aria-expanded", "false");
  launcher.setAttribute("aria-haspopup", "dialog");
  const badge = identified("span", "support-unread", "support-unread", "");
  badge.hidden = true;
  badge.setAttribute("aria-live", "polite");
  launcher.append(badge);
  const panel = identified("dialog", "support-chat", "support-chat");
  panel.setAttribute("aria-labelledby", "support-title");
  panel.setAttribute("aria-describedby", "support-status");
  const header = el("div", "support-header");
  const heading = el("div");
  heading.append(el("p", "support-eyebrow", "VELORA CUSTOMER CARE"), identified("h2", "support-title", "", "A little help, right here."));
  const close = button("support-close", "support-close", "×");
  close.setAttribute("aria-label", "Close support chat");
  header.append(heading, close);
  const status = identified("p", "support-status", "support-status", "Connect with our team");
  status.setAttribute("role", "status");
  const context = identified("p", "support-context", "support-context", "");
  const error = identified("p", "support-error", "support-error", "");
  error.setAttribute("role", "alert");
  const refresh = button("support-refresh", "support-text-button", "Reconnect");
  refresh.hidden = true;
  const older = button("support-older", "support-older", "Load earlier messages");
  older.hidden = true;
  const log = identified("div", "support-messages", "support-messages");
  log.setAttribute("role", "log"); log.setAttribute("aria-label", "Support messages"); log.setAttribute("aria-live", "polite"); log.setAttribute("aria-relevant", "additions"); log.tabIndex = 0;
  const empty = identified("p", "support-empty", "support-empty", "Tell us what you need help with. Our team will reply here when available.");
  log.append(empty);
  const form = identified("form", "support-form", "support-form");
  const guestFields = identified("div", "support-guest-fields", "support-guest-fields");
  const nameLabel = el("label", "", "Your name (optional)"); nameLabel.htmlFor = "support-name";
  const name = identified("input", "support-name"); name.type = "text"; name.maxLength = 80; name.autocomplete = "given-name"; name.placeholder = "Guest";
  guestFields.append(nameLabel, name);
  const messageLabel = el("label", "sr-only", "Your message to support"); messageLabel.htmlFor = "support-message";
  const input = identified("textarea", "support-message"); input.name = "message"; input.required = true; input.maxLength = 2000; input.rows = 3; input.placeholder = "How can we help?";
  input.setAttribute("aria-describedby", "support-help");
  const send = button("support-send", "support-send", "Send message"); send.type = "submit";
  const help = identified("p", "support-help", "support-help", "Please keep passwords and payment details out of this chat.");
  form.append(guestFields, messageLabel, input, send, help);
  const footer = el("div", "support-footer");
  const remove = button("support-delete", "support-text-button", "Delete conversation"); remove.disabled = true; remove.setAttribute("aria-haspopup", "dialog");
  const privacy = el("a", "", "Privacy"); privacy.href = "privacy.html";
  footer.append(remove, privacy);
  panel.append(header, status, context, error, refresh, older, log, form, footer);
  const deleteDialog = identified("dialog", "support-delete-dialog", "support-delete-dialog");
  deleteDialog.setAttribute("aria-labelledby", "support-delete-title");
  deleteDialog.append(identified("h2", "support-delete-title", "", "Delete this conversation?"), el("p", "", "Your saved messages will be removed from this support conversation. You can start a new chat later."));
  const deleteActions = el("div", "support-delete-actions");
  const cancelDelete = button("support-delete-cancel", "support-cancel", "Keep conversation");
  const confirmDelete = button("support-delete-confirm", "support-send", "Delete conversation");
  deleteActions.append(cancelDelete, confirmDelete); deleteDialog.append(deleteActions);
  document.body.append(launcher, panel, deleteDialog);

  function remember(value) { try { sessionStorage.setItem(storageKey, value); } catch { /* Chat still works without tab storage. */ } }
  function savedPanel() { try { return sessionStorage.getItem(storageKey); } catch { return null; } }
  function showError(text) { error.textContent = text; refresh.hidden = !text; }
  function updateBusy() {
    const unavailable = !state.initialized || state.sending || state.deleting;
    input.disabled = unavailable; name.disabled = unavailable; send.disabled = unavailable;
    remove.disabled = !state.conversation || state.sending || state.deleting;
    send.textContent = state.sending ? "Sending…" : "Send message";
    form.setAttribute("aria-busy", String(state.sending || state.deleting));
  }
  function updateBadge(count) {
    badge.hidden = !count;
    badge.textContent = count ? String(Math.min(count, 99)) + (count > 99 ? "+" : "") : "";
    launcher.setAttribute("aria-label", count ? `Chat with us, ${count} unread ${count === 1 ? "message" : "messages"}` : "Chat with us");
  }
  function updateSummary(conversation, availability) {
    state.conversation = conversation;
    updateBadge(conversation?.unreadCount || 0);
    status.classList.toggle("is-online", Boolean(availability?.online));
    status.textContent = availability?.online ? "Support team online" : "Leave a message — our team will reply here";
    context.textContent = conversation?.status === "closed" ? "This conversation is resolved. Send a message to reopen it." : state.customer?.guest ? "A private guest chat, saved on this browser. No email is needed." : `Signed in as ${state.customer?.name || "your account"}. Your conversation is private.`;
    updateBusy();
  }
  function eraseConversation() {
    state.conversation = null; state.messages = []; state.nodes.clear(); state.after = 0; state.before = null; state.lastRead = 0; state.pending = null;
    log.replaceChildren(empty); empty.hidden = false; older.hidden = true; updateBadge(0); input.value = ""; name.value = ""; updateBusy();
  }
  async function request(path, options = {}) {
    if (!/^https?:$/.test(location.protocol)) throw new Error("Start Velora and open http://127.0.0.1:8000 to use customer support.");
    const method = options.method || "GET";
    const headers = { Accept: "application/json" };
    if (method !== "GET") { headers["Content-Type"] = "application/json"; headers["X-CSRF-Token"] = state.token || ""; }
    let response;
    try { response = await fetch(path, { method, headers, body: options.body === undefined ? undefined : JSON.stringify(options.body), credentials: "same-origin", cache: "no-store", redirect: "error", signal: AbortSignal.timeout(12000) }); }
    catch { throw new Error("We couldn't connect to support. Your unsent message is still here. Please reconnect and try again."); }
    let result;
    try { result = await response.json(); } catch { throw new Error("Support is unavailable. Please reconnect and try again."); }
    if (!response.ok) { const failure = new Error(result.error || "This chat request couldn't be completed."); failure.status = response.status; throw failure; }
    return result;
  }
  function nearBottom() { return log.scrollHeight - log.scrollTop - log.clientHeight < 72; }
  function mergeMessages(messages, mode = "new") {
    const wasBottom = nearBottom();
    const oldHeight = log.scrollHeight, oldTop = log.scrollTop;
    const all = new Map(state.messages.map((message) => [message.id, message]));
    messages.forEach((message) => all.set(message.id, message));
    state.messages = [...all.values()].sort((a, b) => a.id - b.id);
    if (state.messages.length) { empty.hidden = true; empty.remove(); }
    if (mode === "initial" || mode === "earlier") log.setAttribute("aria-live", "off");
    for (let index = 0; index < state.messages.length; index++) {
      const message = state.messages[index];
      if (state.nodes.has(message.id)) continue;
      const article = el("article", `support-message is-${message.sender}`); article.dataset.messageId = String(message.id);
      const meta = el("div", "support-message-meta");
      const date = new Date(message.createdAt);
      const time = el("time", "", Number.isNaN(date.getTime()) ? "" : timeFormat.format(date)); time.dateTime = message.createdAt;
      meta.append(el("strong", "", message.sender === "customer" ? "You" : message.authorName), time);
      article.append(meta, el("p", "support-message-body", message.body));
      const following = state.messages.slice(index + 1).map((item) => state.nodes.get(item.id)).find(Boolean);
      log.insertBefore(article, following || null); state.nodes.set(message.id, article);
    }
    if (mode === "earlier") log.scrollTop = oldTop + log.scrollHeight - oldHeight;
    else if (mode === "initial" || mode === "sent" || wasBottom) log.scrollTop = log.scrollHeight;
    requestAnimationFrame(() => log.setAttribute("aria-live", "polite"));
  }
  async function markRead() {
    if (!state.initialized || !panel.open || document.hidden || !nearBottom() || state.reading || !state.messages.length) return;
    const through = state.messages.at(-1).id;
    if (through <= state.lastRead) return;
    state.reading = true;
    const generation = state.generation;
    try {
      await request("/api/support/read", { method: "POST", body: { through } });
      if (generation === state.generation) { state.lastRead = through; updateBadge(0); }
    } catch { /* The next visible refresh retries the read acknowledgement. */ }
    finally { state.reading = false; }
  }
  function schedule(delay) {
    clearTimeout(state.timer);
    if (!state.active || !state.initialized || document.hidden) return;
    state.timer = setTimeout(() => poll(), delay ?? (panel.open ? 3000 : 10000));
  }
  async function connect() {
    if (state.connecting) return state.connecting;
    const generation = state.generation;
    if (state.customer || state.messages.length) { eraseConversation(); state.customer = null; context.textContent = ""; }
    status.textContent = "Connecting to customer care…";
    showError(""); updateBusy();
    state.connecting = (async () => {
      try {
        await window.VeloraAuth?.ready.catch(() => {});
        await window.VeloraAuth.request("/api/auth/me");
        const session = await request("/api/support/session");
        if (!state.active || generation !== state.generation) return;
        state.token = session.csrfToken; state.customer = session.customer; state.authId = window.VeloraAuth?.user?.id;
        state.initialized = true; guestFields.hidden = !session.customer.guest;
        name.value = session.customer.guest && session.customer.name !== "Guest" ? session.customer.name : "";
        updateSummary(session.conversation, session.availability);
        await poll(true);
      } catch (failure) {
        if (generation !== state.generation || !state.active) return;
        status.textContent = "Support connection unavailable"; showError(failure.message);
      } finally { if (generation === state.generation) updateBusy(); }
    })();
    try { await state.connecting; } finally {
      state.connecting = null;
      if (generation !== state.generation && panel.open && state.active && !state.initialized) queueMicrotask(connect);
    }
  }
  async function poll(initial = false) {
    if (state.polling || !state.initialized || document.hidden || !state.active) return;
    state.polling = true;
    const generation = state.generation;
    let nextDelay;
    try {
      let more = false;
      for (let batch = 0; batch < 3; batch++) {
        const data = await request(`/api/support/conversation?limit=50${initial ? "" : `&after=${state.after}`}`);
        if (generation !== state.generation || !state.active) return;
        if (!initial && state.conversation?.id && data.conversation?.id !== state.conversation.id) {
          state.generation++; state.initialized = false; eraseConversation(); status.textContent = "Your chat session changed. Reconnect to continue."; showError("Reconnect to open your current private conversation."); return;
        }
        mergeMessages(data.messages, initial ? "initial" : "new");
        state.after = data.nextAfter;
        if (initial) { state.before = data.nextBefore; older.hidden = !data.hasEarlier; }
        updateSummary(data.conversation, data.availability);
        showError(""); more = data.hasMore;
        if (!more) break;
        initial = false;
      }
      if (!more) await markRead();
      if (more) nextDelay = 100;
    } catch (failure) {
      if (generation !== state.generation || !state.active) return;
      if (failure.status === 401) {
        state.generation++; state.initialized = false; state.token = null; state.customer = null; eraseConversation();
        context.textContent = "";
      }
      status.textContent = "Connection interrupted"; status.classList.remove("is-online"); showError(failure.message);
    } finally { state.polling = false; schedule(nextDelay); }
  }
  async function openChat(opener) {
    state.opener = opener;
    remember("open");
    if (!panel.open) panel.show();
    log.scrollTop = log.scrollHeight;
    launcher.setAttribute("aria-expanded", "true");
    close.focus({ preventScroll: true });
    if (!state.initialized) await connect();
    else await poll();
    log.scrollTop = log.scrollHeight;
    await markRead();
  }
  function closeChat() { panel.close(); remember("closed"); launcher.setAttribute("aria-expanded", "false"); state.opener?.focus({ preventScroll: true }); schedule(); }
  document.addEventListener("click", (event) => { const trigger = event.target instanceof Element ? event.target.closest("[data-support-open]") : null; if (trigger) openChat(trigger); });
  close.addEventListener("click", closeChat);
  panel.addEventListener("keydown", (event) => { if (event.key === "Escape") { event.preventDefault(); closeChat(); } });
  refresh.addEventListener("click", async () => { if (!state.initialized) await connect(); else await poll(); });
  log.addEventListener("scroll", () => { if (nearBottom()) markRead(); });
  older.addEventListener("click", async () => {
    if (older.disabled || !state.before) return;
    older.disabled = true;
    const generation = state.generation;
    try {
      const data = await request(`/api/support/conversation?limit=50&before=${state.before}`);
      if (generation !== state.generation || !state.active) return;
      mergeMessages(data.messages, "earlier"); state.before = data.nextBefore; older.hidden = !data.hasEarlier;
    } catch (failure) { showError(failure.message); }
    finally { older.disabled = false; }
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.initialized || state.sending || state.deleting || !form.reportValidity()) return;
    const body = input.value.trim();
    if (!body) { showError("Write a message before sending it."); input.focus(); return; }
    const guestName = state.customer.guest ? name.value.trim() : "";
    const sameDraft = state.pending?.body === body && state.pending?.name === guestName;
    const pending = sameDraft ? state.pending : { body, name: guestName, clientId: crypto.randomUUID() };
    state.pending = pending; state.sending = true; updateBusy(); showError("");
    const generation = state.generation;
    try {
      // A sign-out/account switch in another tab must never turn this draft into
      // a message from a different account or an earlier guest identity.
      await window.VeloraAuth.request("/api/auth/me");
      if (generation !== state.generation || !state.active) return;
      const payload = { body, clientId: pending.clientId };
      if (state.customer.guest && guestName) payload.name = guestName;
      const result = await request("/api/support/messages", { method: "POST", body: payload });
      if (generation !== state.generation || !state.active) return;
      input.value = ""; state.pending = null;
      mergeMessages([result.message], "sent");
      state.conversation = result.conversation;
      // Poll from the previous cursor, preserving any concurrent staff message.
      await poll();
    } catch (failure) {
      if (generation !== state.generation || !state.active) return;
      showError(failure.message);
      if (failure.status === 401 || failure.status === 403) {
        state.initialized = false; state.token = null;
        status.textContent = "Reconnect before sending your message";
      }
    } finally { state.sending = false; updateBusy(); if (panel.open && state.initialized) input.focus({ preventScroll: true }); }
  });
  remove.addEventListener("click", () => { if (remove.disabled) return; deleteDialog.showModal(); cancelDelete.focus(); });
  function cancelRemoval() { if (state.deleting) return; deleteDialog.close(); remove.focus(); }
  cancelDelete.addEventListener("click", cancelRemoval);
  deleteDialog.addEventListener("cancel", (event) => { event.preventDefault(); cancelRemoval(); });
  confirmDelete.addEventListener("click", async () => {
    if (state.deleting || !state.conversation) return;
    state.deleting = true; confirmDelete.disabled = true; cancelDelete.disabled = true; updateBusy();
    try {
      await request("/api/support/conversation", { method: "DELETE", body: {} });
      state.generation++; eraseConversation(); deleteDialog.close();
      showError(""); await poll(true);
    } catch (failure) { deleteDialog.close(); showError(failure.message); }
    finally { state.deleting = false; confirmDelete.disabled = false; cancelDelete.disabled = false; updateBusy(); input.focus(); }
  });
  function identityChanged(user) {
    const nextId = user?.id;
    if (state.authId === nextId) return;
    state.authId = nextId;
    if (!state.initialized && !state.customer) return;
    state.generation++; state.initialized = false; state.token = null; state.customer = null;
    clearTimeout(state.timer); eraseConversation(); context.textContent = "";
    if (panel.open) { connect().then(() => { if (!state.initialized) showError("Your sign-in changed. Reconnect to customer support."); }); }
  }
  window.addEventListener("velora:auth-changed", (event) => identityChanged(event.detail.user));
  async function resume() {
    if (!state.active || document.hidden) return;
    if (state.initialized) {
      try { await window.VeloraAuth.request("/api/auth/me"); } catch { /* The support endpoint checks the session too. */ }
      if (state.initialized) poll();
    }
  }
  document.addEventListener("visibilitychange", () => { if (document.hidden) clearTimeout(state.timer); else resume(); });
  window.addEventListener("focus", resume);
  window.addEventListener("pagehide", () => { state.active = false; state.generation++; clearTimeout(state.timer); state.initialized = false; state.customer = null; state.token = null; eraseConversation(); context.textContent = ""; if (deleteDialog.open) deleteDialog.close(); });
  window.addEventListener("pageshow", (event) => { if (event.persisted) { state.active = true; state.connecting = null; state.polling = false; if (savedPanel()) { if (savedPanel() === "open" && !panel.open) panel.show(); connect(); } } });
  function fitVisualViewport() {
    const viewport = window.visualViewport;
    if (!viewport) return;
    panel.style.setProperty("--support-viewport-height", `${viewport.height}px`);
    panel.style.setProperty("--support-viewport-top", `${viewport.offsetTop}px`);
  }
  window.visualViewport?.addEventListener("resize", fitVisualViewport);
  window.visualViewport?.addEventListener("scroll", fitVisualViewport);
  fitVisualViewport();
  updateBusy();
  const previous = savedPanel();
  if (previous === "open") openChat(launcher);
  else if (previous === "closed") connect();
})();
