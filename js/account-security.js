/* Private account controls. Setup keys and recovery codes stay in this page only. */
(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  if (!$("#account-security")) return;
  const state = { status: null, sessions: [], enrollment: null, recoveryCodes: [], busy: false, loading: null, expiryTimer: null, active: true };
  const dates = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Amsterdam" });

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function dateValue(value) {
    return new Date(typeof value === "number" ? (value < 1e12 ? value * 1000 : value) : value);
  }

  function dateLabel(value) {
    const date = dateValue(value);
    return Number.isNaN(date.getTime()) ? "—" : dates.format(date);
  }

  function message(text, success = false) {
    const node = $("#security-message");
    node.textContent = text;
    node.classList.toggle("is-success", Boolean(text) && success);
    node.classList.toggle("is-error", Boolean(text) && !success);
    node.setAttribute("role", text && !success ? "alert" : "status");
  }

  function handleError(error) {
    if (error?.status === 401) {
      // A wrong current password is a form error; an expired account session is
      // identified by checking the session rather than discarding a valid one.
      window.VeloraAuth.request("/api/auth/me").then(({ user }) => {
        if (!user) location.assign("login.html?next=account.html");
        else message(error.message);
      }).catch(() => message(error.message));
      return;
    }
    message(error?.message || "We couldn't update your account security. Please try again.");
  }

  function syncButtons() {
    $("#security").querySelectorAll("button").forEach((button) => { button.disabled = state.busy; });
    $("#security-revoke-others").disabled = state.busy || !state.sessions.some((session) => !session.current);
    $("#mfa-copy-secret").disabled = state.busy || !state.enrollment;
    $("#mfa-recovery-download").disabled = state.busy || !state.recoveryCodes.length;
    $("#mfa-recovery-saved").disabled = state.busy || !state.recoveryCodes.length;
    $("#security-content").setAttribute("aria-busy", String(state.busy));
  }

  async function perform(action) {
    if (state.busy) return;
    state.busy = true;
    message("");
    syncButtons();
    try { await action(); }
    catch (error) { handleError(error); }
    finally { state.busy = false; syncButtons(); }
  }

  function renderMfa() {
    if (!state.status) return;
    const enabled = state.status.mfaEnabled;
    const recovering = state.recoveryCodes.length > 0;
    const badge = $("#security-mfa-badge");
    badge.textContent = enabled ? "Enabled" : "Not enabled";
    badge.classList.toggle("is-enabled", enabled);
    $("#mfa-disabled").hidden = enabled || Boolean(state.enrollment);
    $("#mfa-enrollment").hidden = enabled || !state.enrollment;
    $("#mfa-enabled").hidden = !enabled || recovering;
    $("#mfa-recovery-panel").hidden = !recovering;
    const remaining = state.status.recoveryCodesRemaining;
    $("#mfa-recovery-remaining").textContent = `${remaining} unused recovery ${remaining === 1 ? "code" : "codes"} available.`;
    $("#security-admin-timeout").hidden = window.VeloraAuth.user?.role !== "admin";
    syncButtons();
  }

  function renderSessions() {
    $("#security-session-count").textContent = `${state.sessions.length} ${state.sessions.length === 1 ? "session" : "sessions"}`;
    const rows = state.sessions.map((session) => {
      const row = element("article", "security-session");
      const copy = element("div", "security-session-copy");
      copy.append(element("h4", "", session.device || "Signed-in device"));
      if (session.ip) copy.append(element("p", "", `IP address ${session.ip}`));
      copy.append(element("p", "", `Signed in ${dateLabel(session.created_at)}`));
      copy.append(element("p", "", `Last active ${dateLabel(session.last_seen)}`));
      copy.append(element("p", "", `Expires ${dateLabel(session.expires_at)}`));
      if (session.current) copy.append(element("span", "security-current-session", "This device"));
      const button = element("button", "security-text-button", session.current ? "Sign out here" : "Sign out device");
      button.type = "button";
      button.dataset.revokeSession = session.id;
      button.setAttribute("aria-label", `Sign out ${session.current ? "this device" : session.device || "device"}`);
      button.disabled = state.busy;
      row.append(copy, button);
      return row;
    });
    $("#security-sessions").replaceChildren(...(rows.length ? rows : [element("p", "security-session-empty", "No active sessions were returned. Refresh your account security.")]));
    syncButtons();
  }

  async function refreshSecurity() {
    if (state.loading) return state.loading;
    state.loading = (async () => {
      try {
        const [status, result] = await Promise.all([
          window.VeloraAuth.request("/api/security/status"),
          window.VeloraAuth.request("/api/security/sessions"),
        ]);
        if (!state.active) return;
        if (typeof status.mfaEnabled !== "boolean" || !Array.isArray(result.sessions)) throw new Error("We couldn't read your account security. Please try again.");
        state.status = status;
        state.sessions = result.sessions;
        $("#security-content").hidden = false;
        renderMfa();
        renderSessions();
      } finally {
        $("#security-loading").hidden = true;
        state.loading = null;
      }
    })();
    return state.loading;
  }

  function clearEnrollment(render = true) {
    clearTimeout(state.expiryTimer);
    state.expiryTimer = null;
    state.enrollment = null;
    $("#mfa-secret").textContent = "";
    $("#mfa-qr").replaceChildren();
    $("#mfa-setup-expiry").textContent = "";
    $("#mfa-enable-form").reset();
    if (render) renderMfa();
  }

  function drawQr(uri) {
    const container = $("#mfa-qr");
    container.replaceChildren();
    const qrApi = window.qrcodegen;
    if (!qrApi) return;
    try {
      const qr = qrApi.QrCode.encodeText(uri, qrApi.QrCode.Ecc.MEDIUM);
      const margin = 4;
      const extent = qr.size + margin * 2;
      const namespace = "http://www.w3.org/2000/svg";
      const svg = document.createElementNS(namespace, "svg");
      svg.setAttribute("viewBox", `0 0 ${extent} ${extent}`);
      svg.setAttribute("shape-rendering", "crispEdges");
      svg.setAttribute("aria-hidden", "true");
      const background = document.createElementNS(namespace, "rect");
      background.setAttribute("width", String(extent));
      background.setAttribute("height", String(extent));
      background.setAttribute("fill", "#fff");
      const path = document.createElementNS(namespace, "path");
      const squares = [];
      for (let y = 0; y < qr.size; y += 1) {
        for (let x = 0; x < qr.size; x += 1) {
          if (qr.getModule(x, y)) squares.push(`M${x + margin},${y + margin}h1v1h-1z`);
        }
      }
      path.setAttribute("d", squares.join(""));
      path.setAttribute("fill", "#161512");
      svg.append(background, path);
      container.append(svg);
    } catch {
      // Manual key entry remains available if the QR library cannot render.
      container.replaceChildren();
    }
  }

  function showEnrollment(result) {
    if (typeof result.secret !== "string" || !/^[A-Z2-7]{16,128}$/.test(result.secret) || typeof result.otpauthUri !== "string" || !result.otpauthUri.startsWith("otpauth://totp/")) throw new Error("We couldn't prepare your authenticator. Please start setup again.");
    clearEnrollment(false);
    state.enrollment = { secret: result.secret };
    $("#mfa-secret").textContent = result.secret;
    drawQr(result.otpauthUri);
    const expiration = dateValue(result.expiresAt);
    const duration = expiration.getTime() - Date.now();
    if (Number.isFinite(duration) && duration > 0) {
      $("#mfa-setup-expiry").textContent = `Complete this setup before ${dateLabel(result.expiresAt)}. Your app will then create a new code every 30 seconds.`;
      state.expiryTimer = setTimeout(() => {
        if (!state.enrollment) return;
        clearEnrollment();
        message("This authenticator setup expired. Confirm your password to start a new setup.");
      }, Math.min(duration, 10 * 60 * 1000));
    } else {
      $("#mfa-setup-expiry").textContent = "Complete setup with a fresh code from your authenticator app.";
    }
    renderMfa();
    $("#mfa-enable-code").focus();
  }

  function showRecovery(codes) {
    if (!Array.isArray(codes) || !codes.length || codes.length > 20 || codes.some((code) => typeof code !== "string" || code.length > 64)) throw new Error("We couldn't display the new recovery codes. Replace them from your security settings before signing out.");
    state.recoveryCodes = [...codes];
    $("#mfa-recovery-codes").replaceChildren(...state.recoveryCodes.map((code) => element("li", "", code)));
    renderMfa();
    $("#mfa-recovery-panel").scrollIntoView({ block: "nearest", behavior: "auto" });
  }

  function clearRecovery() {
    state.recoveryCodes = [];
    $("#mfa-recovery-codes").replaceChildren();
    $("#mfa-recovery-panel").hidden = true;
    renderMfa();
  }

  $("#mfa-setup-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    if (!form.reportValidity()) return;
    perform(async () => {
      try {
        const password = new FormData(form).get("password");
        const result = await window.VeloraAuth.request("/api/security/mfa/setup", { method: "POST", body: { password } });
        if (!state.active) return;
        showEnrollment(result);
      } finally { form.reset(); }
    });
  });

  $("#mfa-enable-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    if (!form.reportValidity()) return;
    perform(async () => {
      try {
        const code = new FormData(form).get("code").trim();
        const result = await window.VeloraAuth.request("/api/security/mfa/enable", { method: "POST", body: { code } });
        if (!state.active) return;
        clearEnrollment(false);
        state.status = { ...state.status, mfaEnabled: true, recoveryCodesRemaining: result.recoveryCodes?.length || 0 };
        showRecovery(result.recoveryCodes);
        await refreshSecurity();
        message("Two-factor sign-in is enabled. Save your recovery codes before leaving this page.", true);
        window.dispatchEvent(new Event("velora-security-change"));
      } finally { form.reset(); }
    });
  });

  $("#mfa-manage-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const action = event.submitter?.value;
    if (!["disable", "regenerate"].includes(action) || !form.reportValidity()) return;
    perform(async () => {
      try {
        const values = new FormData(form);
        const body = { password: values.get("password"), code: values.get("code").trim() };
        const result = await window.VeloraAuth.request(`/api/security/mfa/${action === "disable" ? "disable" : "recovery-codes"}`, { method: "POST", body });
        if (!state.active) return;
        $("#mfa-manage").open = false;
        if (action === "regenerate") showRecovery(result.recoveryCodes);
        else { clearRecovery(); state.status.mfaEnabled = false; }
        await refreshSecurity();
        message(action === "disable" ? "Two-factor sign-in has been turned off. Your other sessions have been signed out." : "Your recovery codes have been replaced. Save this new set; the previous codes no longer work.", true);
        window.dispatchEvent(new Event("velora-security-change"));
      } finally { form.reset(); }
    });
  });

  $("#mfa-cancel-setup").addEventListener("click", () => {
    if (state.busy) return;
    clearEnrollment();
    message("Setup cancelled. Two-factor sign-in has not been enabled.", true);
    $("#mfa-password").focus();
  });

  $("#mfa-copy-secret").addEventListener("click", async () => {
    if (!state.enrollment) return;
    try {
      await navigator.clipboard.writeText(state.enrollment.secret);
      message("Setup key copied. Add it to your authenticator app.", true);
    } catch {
      message("Select the setup key and copy it into your authenticator app manually.", true);
    }
  });

  $("#mfa-recovery-download").addEventListener("click", () => {
    if (!state.recoveryCodes.length) return;
    const content = "Velora recovery codes\n\nKeep this file somewhere private. Each code can be used once in place of your authenticator code.\n\n" + state.recoveryCodes.join("\n") + "\n";
    const url = URL.createObjectURL(new Blob([content], { type: "text/plain;charset=utf-8" }));
    const link = element("a");
    link.href = url;
    link.download = "velora-recovery-codes.txt";
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  $("#mfa-recovery-saved").addEventListener("click", () => {
    clearRecovery();
    message("Your recovery codes are no longer displayed. Keep your saved copy private.", true);
  });

  $("#security-refresh").addEventListener("click", () => perform(async () => {
    await refreshSecurity();
    message("Your account security is up to date.", true);
  }));

  $("#security-revoke-others").addEventListener("click", () => perform(async () => {
    const result = await window.VeloraAuth.request("/api/security/sessions/revoke-others", { method: "POST", body: {} });
    await refreshSecurity();
    message(`${result.revoked} other ${result.revoked === 1 ? "session has" : "sessions have"} been signed out. This device stays signed in.`, true);
  }));

  $("#security-sessions").addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-revoke-session]") : null;
    if (!button) return;
    const session = state.sessions.find((item) => item.id === button.dataset.revokeSession);
    if (!session) return;
    perform(async () => {
      const result = await window.VeloraAuth.request(`/api/security/sessions/${encodeURIComponent(session.id)}`, { method: "DELETE", body: {} });
      if (result.current) { location.assign("login.html"); return; }
      await refreshSecurity();
      message("That device has been signed out.", true);
    });
  });

  window.addEventListener("velora:security-changed", async (event) => {
    if (!state.active || !window.VeloraAuth?.user || $("#account-content").hidden) return;
    if (event.detail?.passwordChanged === true) {
      clearEnrollment(false);
      clearRecovery();
      $("#mfa-setup-form").reset();
      $("#mfa-manage-form").reset();
      message("Your password changed. Other sessions have been signed out.", true);
    }
    // An earlier status request can contain the session ID from before a token
    // rotation. Let it settle, then load the replacement session from the server.
    const pending = state.loading;
    if (pending) { try { await pending; } catch { /* The fresh request below can recover. */ } }
    if (!state.active || !window.VeloraAuth.user || $("#account-content").hidden) return;
    try { await refreshSecurity(); }
    catch (error) { handleError(error); }
  });

  window.addEventListener("pagehide", () => {
    state.active = false;
    clearEnrollment(false);
    state.recoveryCodes = [];
    $("#mfa-recovery-codes").replaceChildren();
    $("#mfa-recovery-panel").hidden = true;
    $("#security-content").hidden = true;
    $("#mfa-setup-form").reset();
    $("#mfa-manage-form").reset();
  });

  if (window.VeloraAuth) {
    window.VeloraAuth.ready.then(async (user) => {
      if (!user) return;
      try { await refreshSecurity(); }
      catch (error) { handleError(error); }
    }).catch(() => { $("#security-loading").hidden = true; });
  }
})();
