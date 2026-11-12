/* A private staff inbox. Only an active, visible inbox advertises availability. */
(() => {
  "use strict";
  const $ = (selector) => document.querySelector(selector);
  const root = $("#admin-support");
  if (!root) return;
  const state = {
    active: false, stopped: false, denied: false, timer: null, ticking: false,
    conversations: [], cursor: null, unread: 0, listBusy: false, selected: null,
    conversation: null, messages: [], after: 0, before: null, hasEarlier: false,
    threadBusy: false, threadGeneration: 0, sending: false, statusBusy: false,
    drafts: new Map(), retries: new Map(), readBusy: false, readAck: 0,
    presenceBusy: false, presenceQueued: false, presencePosted: false, heartbeat: 0,
  };
  const request = (path, options) => window.VeloraAuth.request(path, options);
  const timeFormat = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  function node(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined) item.textContent = text;
    return item;
  }
  function timestamp(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "" : timeFormat.format(date);
  }
  function authorized() {
    return window.VeloraAuth?.user?.role === "admin" && ["owner", "manager"].includes(window.veloraCommerceRole);
  }
  function visible() {
    return !state.stopped && !state.denied && authorized() && !$("#admin-shell").hidden && !root.hidden && !document.hidden;
  }
  function errorMessage(error, fallback) {
    if (error.status === 401) {
      state.denied = true;
      location.assign("login.html?next=admin.html");
    } else if (error.status === 403) {
      state.denied = true;
      $("#support-reply-send").disabled = true;
      $("#support-available").disabled = true;
      $("#support-inbox-state").textContent = "Your staff role no longer has access to customer conversations.";
      $("#support-conversations").replaceChildren();
      $("#support-messages").replaceChildren();
      $("#support-thread").hidden = true;
      $("#support-conversation-empty").hidden = false;
      $("#support-thread-name").textContent = "";
      $("#support-reply").value = "";
      state.messages = [];
      state.drafts.clear();
      state.retries.clear();
      state.selected = null;
      state.conversation = null;
      syncActive();
    }
    return error.message || fallback;
  }
  function replyMessage(text, success = false) {
    const item = $("#support-reply-message");
    item.textContent = text;
    item.classList.toggle("is-success", success);
    item.setAttribute("role", text && !success ? "alert" : "status");
  }
  function renderBadge() {
    $("#support-unread-count").textContent = String(state.unread);
    $("#support-unread-count").hidden = !state.unread;
  }
  function updateConversation(conversation) {
    if (!conversation) return;
    if (state.selected === conversation.id) {
      state.conversation = conversation;
      renderHeader();
    }
    const index = state.conversations.findIndex((item) => item.id === conversation.id);
    if (index !== -1) state.conversations[index] = conversation;
  }
  function invalidateConversation(id) {
    state.drafts.delete(id);
    state.retries.delete(id);
    const previous = state.conversations.find((item) => item.id === id);
    state.unread = Math.max(0, state.unread - (previous?.unreadCount || 0));
    state.conversations = state.conversations.filter((item) => item.id !== id);
    if (state.selected === id) {
      ++state.threadGeneration;
      state.threadBusy = false;
      state.selected = null;
      state.conversation = null;
      state.messages = [];
      state.after = 0;
      state.before = null;
      state.hasEarlier = false;
      $("#support-messages").replaceChildren();
      $("#support-thread-name").textContent = "";
      $("#support-reply").value = "";
      $("#support-thread").hidden = true;
      $("#support-conversation-empty").hidden = false;
      $("#support-conversation-empty h2").textContent = "This conversation is no longer available.";
      $("#support-conversation-empty p").textContent = "It may have been deleted. Choose another conversation to continue.";
      replyMessage("");
    }
    renderInbox();
  }
  function renderInbox() {
    const focused = document.activeElement?.closest("[data-conversation-id]")?.dataset.conversationId;
    const list = state.conversations.map((conversation) => {
      const button = node("button", "support-conversation");
      button.type = "button";
      button.dataset.conversationId = conversation.id;
      button.setAttribute("aria-current", String(conversation.id === state.selected));
      button.setAttribute("aria-label", `${conversation.customerName}, ${conversation.status}${conversation.unreadCount ? `, ${conversation.unreadCount} unread messages` : ""}`);
      const date = node("time", "support-conversation-date", timestamp(conversation.updatedAt));
      date.dateTime = conversation.updatedAt;
      const bottom = node("span", "support-conversation-bottom");
      bottom.append(node("span", "support-conversation-status", conversation.status === "closed" ? "Closed" : "Open"));
      if (conversation.unreadCount) bottom.append(node("span", "support-conversation-badge", String(conversation.unreadCount)));
      button.append(node("strong", "support-conversation-name", conversation.customerName), date,
        node("span", "support-conversation-preview", conversation.lastMessage?.body || "No messages yet"), bottom);
      button.addEventListener("click", () => selectConversation(conversation));
      return button;
    });
    $("#support-conversations").replaceChildren(...list);
    if (focused) {
      const next = [...$("#support-conversations").children].find((item) => item.dataset.conversationId === focused);
      next?.focus({ preventScroll: true });
    }
    $("#support-inbox-load-more").hidden = !state.cursor;
    renderBadge();
  }
  async function loadInbox(append = false) {
    if (state.listBusy || !visible()) return;
    state.listBusy = true;
    $("#support-inbox-load-more").disabled = true;
    const filter = $("#support-inbox-filter").value;
    const generation = state.listGeneration || 0;
    try {
      const query = `?status=${encodeURIComponent(filter)}&limit=50${append && state.cursor ? `&before=${encodeURIComponent(state.cursor)}` : ""}`;
      const result = await request("/api/admin/support" + query);
      if (!visible() || generation !== (state.listGeneration || 0) || filter !== $("#support-inbox-filter").value) return;
      const previous = JSON.stringify(state.conversations);
      if (append) {
        state.conversations = [...new Map([...state.conversations, ...result.conversations].map((item) => [item.id, item])).values()];
        state.expanded = true;
        state.cursor = result.nextCursor;
      } else if (state.expanded && result.nextCursor) {
        // Refresh the live end without collapsing the older pages a staff member opened.
        state.conversations = [...new Map([...state.conversations, ...result.conversations].map((item) => [item.id, item])).values()]
          .filter((item) => filter === "all" || item.status === filter)
          .sort((a, b) => String(b.updatedAt).localeCompare(String(a.updatedAt)) || (b.lastMessage?.id || 0) - (a.lastMessage?.id || 0));
      } else {
        state.conversations = result.conversations;
        state.cursor = result.nextCursor;
        state.expanded = false;
      }
      state.unread = result.unreadCount;
      if (previous !== JSON.stringify(state.conversations)) renderInbox();
      else { $("#support-inbox-load-more").hidden = !state.cursor; renderBadge(); }
      $("#support-inbox-state").textContent = state.conversations.length
        ? `${state.conversations.length} ${state.conversations.length === 1 ? "conversation" : "conversations"} shown.`
        : filter === "closed" ? "No closed conversations yet." : filter === "open" ? "No open conversations. New customer messages will appear here." : "No customer conversations yet.";
    } catch (error) {
      $("#support-inbox-state").textContent = errorMessage(error, "The inbox couldn't refresh. We'll try again shortly.");
    } finally {
      state.listBusy = false;
      $("#support-inbox-load-more").disabled = false;
    }
  }
  function renderHeader() {
    const conversation = state.conversation;
    if (!conversation) return;
    $("#support-thread-name").textContent = conversation.customerName;
    $("#support-thread-status").textContent = conversation.status === "closed" ? "Closed · sending a reply reopens this conversation." : "Open conversation";
    $("#support-conversation-status").textContent = conversation.status === "closed" ? "Reopen conversation" : "Close conversation";
    $("#support-conversation-status").disabled = state.statusBusy;
  }
  function nearBottom() {
    const log = $("#support-messages");
    return log.scrollHeight - log.scrollTop - log.clientHeight < 65;
  }
  function renderMessages(forceBottom = false, prepend = false) {
    const log = $("#support-messages");
    const bottom = nearBottom(), height = log.scrollHeight, top = log.scrollTop;
    state.messages.sort((a, b) => a.id - b.id);
    let added = false;
    for (let index = 0; index < state.messages.length; index++) {
      const message = state.messages[index];
      const current = log.children[index];
      if (Number(current?.dataset.messageId) === message.id) continue;
      let bubble = [...log.children].find((item) => Number(item.dataset.messageId) === message.id);
      if (!bubble) {
        bubble = node("article", "support-message");
        bubble.dataset.messageId = String(message.id);
        bubble.dataset.sender = message.sender;
        const heading = node("div", "support-message-heading");
        const date = node("time", "", timestamp(message.createdAt));
        date.dateTime = message.createdAt;
        heading.append(node("strong", "", message.authorName), date);
        bubble.append(heading, node("p", "", message.body));
        added = true;
      }
      log.insertBefore(bubble, current || null);
    }
    if (prepend) log.scrollTop = top + log.scrollHeight - height;
    else if (bottom || forceBottom) { log.scrollTop = log.scrollHeight; $("#support-new-messages").hidden = true; }
    else if (added) $("#support-new-messages").hidden = false;
    requestAnimationFrame(markRead);
  }
  function mergeMessages(messages) {
    state.messages = [...new Map([...state.messages, ...messages].map((message) => [message.id, message])).values()];
  }
  async function refreshThread(initial = false, earlier = false) {
    if (!state.selected || state.threadBusy || !visible()) return;
    const id = state.selected, generation = state.threadGeneration;
    state.threadBusy = true;
    $("#support-load-earlier").disabled = true;
    try {
      const query = earlier ? `?before=${state.before}&limit=50` : initial ? "?limit=50" : `?after=${state.after}&limit=50`;
      const result = await request(`/api/admin/support/${id}${query}`);
      if (!visible() || id !== state.selected || generation !== state.threadGeneration) return;
      mergeMessages(result.messages);
      updateConversation(result.conversation);
      if (earlier || initial) {
        state.before = result.nextBefore;
        state.hasEarlier = result.hasEarlier;
      }
      // Only GET advances this cursor. A POST could race with a lower-ID customer message.
      if (!earlier) state.after = result.nextAfter;
      renderMessages(initial, earlier);
      $("#support-load-earlier").hidden = !state.hasEarlier;
      $("#support-thread-state").textContent = "";
      if (result.hasMore && !earlier) {
        state.threadBusy = false;
        await refreshThread();
      }
    } catch (error) {
      if (error.status === 404) invalidateConversation(id);
      else if (id === state.selected) $("#support-thread-state").textContent = errorMessage(error, "Messages couldn't refresh. Your reply is still here.");
    } finally {
      if (generation === state.threadGeneration) state.threadBusy = false;
      $("#support-load-earlier").disabled = false;
    }
  }
  function selectConversation(conversation) {
    if (state.selected === conversation.id) return;
    if (state.selected) state.drafts.set(state.selected, $("#support-reply").value);
    state.selected = conversation.id;
    state.conversation = conversation;
    state.messages = [];
    state.after = 0;
    state.before = null;
    state.hasEarlier = false;
    state.readAck = 0;
    ++state.threadGeneration;
    state.threadBusy = false;
    $("#support-messages").replaceChildren();
    $("#support-conversation-empty").hidden = true;
    $("#support-thread").hidden = false;
    $("#support-load-earlier").hidden = true;
    $("#support-new-messages").hidden = true;
    $("#support-reply").value = state.drafts.get(conversation.id) || "";
    $("#support-thread-state").textContent = "Loading conversation…";
    replyMessage("");
    renderHeader();
    renderInbox();
    refreshThread(true);
    if (matchMedia("(max-width: 760px)").matches) $("#support-thread").scrollIntoView({ block: "start" });
  }
  async function markRead() {
    if (!visible() || !document.hasFocus() || !state.selected || state.readBusy || state.after <= state.readAck || !nearBottom()) return;
    const box = $("#support-messages").getBoundingClientRect();
    if (box.bottom <= 0 || box.top >= innerHeight || box.height < 1) return;
    const id = state.selected, through = state.after, generation = state.threadGeneration;
    state.readBusy = true;
    try {
      const result = await request(`/api/admin/support/${id}/read`, { method: "POST", body: { through } });
      if (id !== state.selected || generation !== state.threadGeneration) return;
      state.readAck = through;
      const previous = state.conversations.find((item) => item.id === id)?.unreadCount || 0;
      updateConversation(result.conversation);
      state.unread = Math.max(0, state.unread - previous + result.conversation.unreadCount);
      renderInbox();
    } catch (error) {
      if (error.status === 404) invalidateConversation(id);
      else if (error.status === 401 || error.status === 403) errorMessage(error, "Your staff session could not be verified.");
    } finally { state.readBusy = false; }
  }
  function presenceUI(text, online = false) {
    $("#support-presence-state").textContent = text;
    $(".support-availability").classList.toggle("is-online", online);
  }
  async function syncPresence(force = false) {
    if (!authorized() || state.denied) return;
    const available = visible() && $("#support-available").checked;
    if (!force && available && Date.now() - state.heartbeat < 20000) return;
    if (!force && !available && !state.presencePosted) return;
    if (state.presenceBusy) { state.presenceQueued = true; return; }
    state.presenceBusy = true;
    try {
      await request("/api/admin/support/presence", { method: "POST", body: { available } });
      state.presencePosted = available;
      state.heartbeat = Date.now();
      presenceUI(available ? "You are available while this inbox is visible." : "You are not advertising live availability.", available);
    } catch (error) {
      presenceUI(errorMessage(error, "Connection lost. Availability expires automatically."));
    } finally {
      state.presenceBusy = false;
      if (state.presenceQueued || available !== (visible() && $("#support-available").checked)) {
        state.presenceQueued = false;
        syncPresence(true);
      }
    }
  }
  async function tick() {
    if (state.ticking || !visible()) return;
    state.ticking = true;
    try { await Promise.allSettled([loadInbox(), refreshThread(), syncPresence()]); }
    finally { state.ticking = false; }
  }
  function syncActive() {
    const active = visible();
    if (active === state.active) return;
    state.active = active;
    clearInterval(state.timer);
    if (active) {
      state.staffIdentity = window.VeloraAuth.user.id;
      presenceUI("Updating your availability…");
      syncPresence(true);
      tick();
      state.timer = setInterval(tick, 3000);
      requestAnimationFrame(markRead);
    } else {
      syncPresence(true);
      presenceUI("Live availability is paused while this inbox is hidden.");
    }
  }
  $("#support-inbox-filter").addEventListener("change", () => {
    state.listGeneration = (state.listGeneration || 0) + 1;
    state.conversations = [];
    state.cursor = null;
    state.expanded = false;
    renderInbox();
    $("#support-inbox-state").textContent = "Loading conversations…";
    if (state.listBusy) setTimeout(() => loadInbox(), 100);
    else loadInbox();
  });
  $("#support-inbox-load-more").addEventListener("click", () => loadInbox(true));
  $("#support-available").addEventListener("change", () => syncPresence(true));
  $("#support-thread-refresh").addEventListener("click", () => refreshThread());
  $("#support-load-earlier").addEventListener("click", () => refreshThread(false, true));
  $("#support-new-messages").addEventListener("click", () => {
    $("#support-messages").scrollTop = $("#support-messages").scrollHeight;
    $("#support-new-messages").hidden = true;
    markRead();
  });
  $("#support-messages").addEventListener("scroll", () => {
    if (nearBottom()) { $("#support-new-messages").hidden = true; markRead(); }
  }, { passive: true });
  window.addEventListener("scroll", markRead, { passive: true });
  window.addEventListener("focus", markRead);
  $("#support-reply").addEventListener("input", () => {
    if (state.selected) state.drafts.set(state.selected, $("#support-reply").value);
  });
  $("#support-reply").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      $("#support-reply-form").requestSubmit();
    }
  });
  $("#support-reply-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.sending || !state.selected || !visible()) return;
    const id = state.selected, body = $("#support-reply").value.trim();
    if (!body || body.length > 2000) { replyMessage("Write a reply between 1 and 2,000 characters."); return; }
    let retry = state.retries.get(id);
    if (!retry || retry.body !== body) retry = { body, clientId: crypto.randomUUID() };
    state.retries.set(id, retry);
    state.sending = true;
    $("#support-reply-send").disabled = true;
    replyMessage("Sending your reply…", true);
    try {
      const result = await request(`/api/admin/support/${id}/messages`, { method: "POST", body: retry });
      state.retries.delete(id);
      if ((state.drafts.get(id) || "").trim() === body) state.drafts.delete(id);
      if (state.selected === id) {
        if ($("#support-reply").value.trim() === body) $("#support-reply").value = "";
        mergeMessages([result.message]);
        updateConversation(result.conversation);
        renderMessages(true);
        replyMessage("Reply sent.", true);
        await refreshThread();
      }
      await loadInbox();
    } catch (error) {
      if (error.status === 404) invalidateConversation(id);
      const text = errorMessage(error, "Your reply couldn't be sent. Your words are still here; try again.");
      if (state.selected === id) replyMessage(text);
    } finally {
      state.sending = false;
      $("#support-reply-send").disabled = state.denied;
    }
  });
  $("#support-conversation-status").addEventListener("click", async () => {
    if (!state.selected || state.statusBusy || !visible()) return;
    const id = state.selected, status = state.conversation.status === "closed" ? "open" : "closed";
    state.statusBusy = true;
    renderHeader();
    try {
      const result = await request(`/api/admin/support/${id}`, { method: "PATCH", body: { status } });
      updateConversation(result.conversation);
      await loadInbox();
    } catch (error) {
      if (error.status === 404) invalidateConversation(id);
      else if (state.selected === id) $("#support-thread-state").textContent = errorMessage(error, "The conversation status couldn't be changed.");
    } finally { state.statusBusy = false; renderHeader(); }
  });
  document.addEventListener("velora:admin-section", syncActive);
  window.addEventListener("velora:auth-changed", () => {
    // An in-memory reply from a previous staff identity must never be posted as another account.
    if (state.staffIdentity === undefined || window.VeloraAuth.user?.id === state.staffIdentity) return;
    state.denied = true;
    ++state.threadGeneration;
    state.listGeneration = (state.listGeneration || 0) + 1;
    clearInterval(state.timer);
    state.drafts.clear();
    state.retries.clear();
    state.messages = [];
    state.conversations = [];
    state.selected = null;
    state.conversation = null;
    $("#support-reply").value = "";
    $("#support-messages").replaceChildren();
    $("#support-conversations").replaceChildren();
    $("#support-thread-name").textContent = "";
    $("#admin-shell").hidden = true;
    if (window.VeloraAuth.user?.role === "admin") location.reload();
    else location.assign("login.html?next=admin.html");
  });
  document.addEventListener("visibilitychange", syncActive);
  new MutationObserver(syncActive).observe($("#admin-shell"), { attributes: true, attributeFilter: ["hidden"] });
  window.VeloraAuth.ready.then(syncActive).catch(() => {});
  window.addEventListener("pagehide", () => {
    state.stopped = true;
    clearInterval(state.timer);
    if (state.presencePosted && authorized()) {
      fetch("/api/admin/support/presence", { method: "POST", credentials: "same-origin", keepalive: true,
        headers: { "Content-Type": "application/json", "X-CSRF-Token": window.VeloraAuth.csrfToken },
        body: JSON.stringify({ available: false }) }).catch(() => {});
    }
    state.drafts.clear();
    state.retries.clear();
    $("#support-reply").value = "";
    $("#support-messages").replaceChildren();
    $("#support-conversations").replaceChildren();
  });
})();
