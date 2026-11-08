/* Security data loads on demand and never gates catalog operations. */
(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const state = { events: [], loaded: false, loading: null, updatedAt: null };
  const eventLabels = {
    login_success: "Successful sign-in", login_failed: "Failed sign-in", login_failure: "Failed sign-in",
    login_blocked: "Sign-in blocked", login_rate_limited: "Sign-in attempt limited", logout: "Signed out",
    password_changed: "Password changed", mfa_setup: "Two-factor setup started", mfa_enabled: "Two-factor enabled",
    mfa_disabled: "Two-factor disabled", mfa_failed: "Two-factor check failed", mfa_recovery_used: "Recovery code used",
    recovery_used: "Recovery code used", mfa_recovery_regenerated: "Recovery codes replaced", session_revoked: "Session signed out",
    csrf_rejected: "Request verification rejected", permission_denied: "Access denied", account_register: "Account created",
    folder_access_changed: "Colleague folder access changed", folder_access_denied: "Shared-folder access denied",
    folder_file_uploaded: "Shared file added", folder_file_deleted: "Shared file deleted",
    folder_file_cleanup_pending: "Shared-file storage cleanup needed",
    colleague_created: "Velora colleague created", colleague_access_changed: "Colleague access changed",
    discount_created: "Discount code created", discount_updated: "Discount code updated", discount_deleted: "Discount code deleted",
  };
  const dateFormat = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function labelFor(event) {
    if (eventLabels[event.event_type]) return eventLabels[event.event_type];
    const text = String(event.event_type || "Security event").replaceAll("_", " ");
    return text[0]?.toUpperCase() + text.slice(1);
  }

  function dateLabel(value) {
    const date = new Date(typeof value === "number" ? value * 1000 : value);
    return Number.isNaN(date.getTime()) ? "Unknown time" : dateFormat.format(date);
  }

  function renderEvents() {
    const search = $("#admin-security-search").value.trim().toLocaleLowerCase();
    const severity = $("#admin-security-severity").value;
    const matches = state.events.filter((event) => {
      const text = [labelFor(event), event.event_type, event.actor_name, event.email_hint, event.ip, event.detail].filter(Boolean).join(" ").toLocaleLowerCase();
      return (severity === "all" || severity === event.severity) && text.includes(search);
    });
    const rows = matches.map((event) => {
      const row = element("tr");
      const eventCell = element("td", "admin-security-event-copy");
      eventCell.append(element("strong", "", labelFor(event)));
      if (event.detail) eventCell.append(element("small", "", event.detail));
      const account = element("td", "admin-security-person");
      account.append(element("strong", "", event.actor_name || "Unrecognized account"));
      if (event.email_hint) account.append(element("small", "", event.email_hint));
      const severityCell = element("td");
      const level = ["info", "warning", "critical"].includes(event.severity) ? event.severity : "info";
      severityCell.append(element("span", `admin-security-level is-${level}`, level === "info" ? "Information" : level[0].toUpperCase() + level.slice(1)));
      const time = element("time", "", dateLabel(event.created_at));
      time.dateTime = String(event.created_at || "");
      const timeCell = element("td", "admin-security-when");
      timeCell.append(time);
      row.append(eventCell, account, element("td", "admin-security-ip", event.ip || "Unknown"), severityCell, timeCell);
      return row;
    });
    $("#admin-security-events-body").replaceChildren(...rows);
    $("#admin-security-empty").hidden = Boolean(rows.length);
    $("#admin-security-empty").textContent = search || severity !== "all"
      ? "No security events match these filters. Try another search or severity."
      : "No security events have been recorded yet.";
    $("#admin-security-event-count").textContent = state.loaded ? `${matches.length} of ${state.events.length} recent events` : "";
  }

  function showError(error) {
    if (error?.status === 401) { location.replace("login.html?next=admin.html"); return; }
    if (error?.status === 403) { location.replace("account.html"); return; }
    $("#admin-security-error-message").textContent = error?.status === 404
      ? "The account server needs the latest security update. Restart Velora, then try again."
      : error?.message || "We couldn't load security activity. Please try again.";
    $("#admin-security-error").hidden = false;
  }

  async function refreshSecurity() {
    if (state.loading) return state.loading;
    $("#admin-security").setAttribute("aria-busy", "true");
    $("#admin-security-refresh").disabled = true;
    $("#admin-security-retry").disabled = true;
    $("#admin-security-updated").textContent = "Checking recent security activity…";
    state.loading = (async () => {
      try {
        const result = await window.VeloraAuth.request("/api/admin/security");
        const summary = result.summary;
        if (!summary || !Array.isArray(result.events)) throw new Error("The security response could not be read. Please try again.");
        $("#admin-security-failed").textContent = summary.failedLogins24h;
        $("#admin-security-blocked").textContent = summary.blockedAttempts24h;
        $("#admin-security-sessions").textContent = summary.activeAdminSessions;
        $("#admin-security-mfa").textContent = `${summary.mfaEnabledAdmins} / ${summary.totalAdmins}`;
        const recommended = summary.mfaEnabledAdmins < summary.totalAdmins;
        $("#admin-security-recommendation").hidden = !recommended;
        $("#admin-security-mfa-guidance").textContent = recommended
          ? "Some administrator accounts still use password-only sign-in. Add an authenticator app to your account and keep recovery codes somewhere safe."
          : "Every administrator currently has two-factor sign-in enabled. Review your own devices, sessions, and recovery options whenever you need.";
        state.events = result.events;
        state.loaded = true;
        state.updatedAt = new Date();
        $("#admin-security-error").hidden = true;
        renderEvents();
      } catch (error) {
        showError(error);
      } finally {
        $("#admin-security").removeAttribute("aria-busy");
        $("#admin-security-refresh").disabled = false;
        $("#admin-security-retry").disabled = false;
        $("#admin-security-updated").textContent = state.updatedAt ? `Last updated ${dateFormat.format(state.updatedAt)}. Refresh to check for new activity.` : "Security details haven't loaded yet.";
        state.loading = null;
      }
    })();
    return state.loading;
  }

  document.addEventListener("velora:admin-section", (event) => {
    if (event.detail?.section === "security" && !state.loaded) refreshSecurity();
  });
  $("#admin-security-refresh").addEventListener("click", refreshSecurity);
  $("#admin-security-retry").addEventListener("click", refreshSecurity);
  $("#admin-security-search").addEventListener("input", renderEvents);
  $("#admin-security-severity").addEventListener("change", renderEvents);
  window.VeloraAuth?.ready.then((user) => {
    if (user?.role === "admin" && location.hash === "#security") refreshSecurity();
  }).catch(() => {});
})();
