/* Accounts are backed by the Velora server; credentials never go into browser storage. */
(() => {
  "use strict";

  const unavailable = "We couldn't connect to account services. Please try again shortly.";
  const auth = { user: null, csrfToken: null, ready: null, request, logout };
  window.VeloraAuth = auth;

  function connectionError() {
    const local = location.protocol === "file:" || ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
    const error = new Error(local
      ? "This preview can't connect to accounts. Open Velora's account server to continue."
      : unavailable);
    error.code = "ACCOUNT_SERVICE_UNAVAILABLE";
    if (!local) return error;

    const page = document.body.dataset.authPage;
    const next = new URLSearchParams(location.search).get("next");
    const target = new URL("http://127.0.0.1:8000/login.html");
    if (page === "register") target.pathname = "/register.html";
    else if (document.body.classList.contains("admin-page") || next === "admin.html") target.searchParams.set("next", "admin.html");
    else if (next === "intranet.html") target.searchParams.set("next", "intranet.html");
    else if (["account.html", "reviews.html"].includes(next)) target.searchParams.set("next", next);
    else if (page === "account") target.searchParams.set("next", "account.html");

    document.querySelectorAll("[data-auth-link]").forEach((link) => { link.href = "http://127.0.0.1:8000/login.html"; });
    // Keep account navigation on the server that implements it when the collection
    // is being previewed by a static IDE server. Form values are never transferred.
    document.querySelectorAll('a[href="admin.html"], a[href="account.html"], a[href="register.html"], a[href^="login.html"]').forEach((link) => {
      const [filename, query = ""] = link.getAttribute("href").split("?");
      if (!["admin.html", "account.html", "register.html", "login.html"].includes(filename)) return;
      const destination = new URL(filename, "http://127.0.0.1:8000/");
      const nextPage = new URLSearchParams(query).get("next");
      if (["admin.html", "account.html", "reviews.html", "intranet.html"].includes(nextPage)) destination.searchParams.set("next", nextPage);
      link.href = destination.href;
    });
    const status = document.querySelector("#auth-message, #account-loading, #admin-access-message");
    if (status && !document.querySelector("#account-connection-help")) {
      const help = document.createElement("div");
      help.id = "account-connection-help";
      help.className = "account-connection-help";
      const link = document.createElement("a");
      link.id = "account-server-link";
      link.href = target.href;
      link.textContent = page === "register" ? "Open Velora registration ↗" : "Open Velora sign in ↗";
      const hint = document.createElement("p");
      hint.textContent = "If the page doesn't open, run Start-Velora.cmd in the project folder first.";
      help.append(link, hint);
      status.after(help);
    }
    return error;
  }

  async function request(path, options = {}) {
    if (typeof path !== "string" || !path.startsWith("/api/") || /[\\\u0000-\u0020\u007f]/.test(path)) {
      throw new Error("Invalid account request.");
    }
    if (!/^https?:$/.test(location.protocol)) throw connectionError();
    const url = new URL(path, location.origin);
    // Canonicalization must not move a credentialed request outside the API.
    if (url.origin !== location.origin || !url.pathname.startsWith("/api/") || url.hash) {
      throw new Error("Invalid account request.");
    }
    const method = typeof options.method === "string" ? options.method.toUpperCase() : options.method === undefined ? "GET" : "";
    if (!["GET", "POST", "PATCH", "DELETE"].includes(method)) throw new Error("Invalid account request.");
    const headers = new Headers(options.headers);
    headers.set("Accept", "application/json");
    if (options.body !== undefined) headers.set("Content-Type", "application/json");
    if (auth.csrfToken && method !== "GET") headers.set("X-CSRF-Token", auth.csrfToken);
    let response;
    try {
      response = await fetch(url.pathname + url.search, {
        method, headers, credentials: "same-origin", cache: "no-store", redirect: "error",
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        signal: AbortSignal.timeout(15000),
      });
    } catch {
      throw connectionError();
    }
    let result;
    try {
      result = await response.json();
    } catch {
      throw connectionError();
    }
    document.querySelector("#account-connection-help")?.remove();
    if (!response.ok) {
      const error = new Error(result.error || "Something went wrong. Please try again.");
      error.status = response.status;
      throw error;
    }
    if (Object.hasOwn(result, "user")) {
      auth.user = result.user;
      if (!result.user) auth.csrfToken = null;
      updateAccountLinks();
    }
    if (Object.hasOwn(result, "csrfToken")) auth.csrfToken = result.csrfToken;
    if (Object.hasOwn(result, "user")) window.dispatchEvent(new CustomEvent("velora:auth-changed", { detail: { user: auth.user } }));
    return result;
  }

  function updateAccountLinks() {
    document.querySelectorAll("[data-auth-link]").forEach((link) => {
      link.href = auth.user ? "account.html" : "login.html";
      const label = link.querySelector("[data-auth-label]");
      const fullName = auth.user?.name || "My account";
      const compactName = auth.user?.firstName || fullName.split(/\s+/)[0];
      const text = auth.user ? fullName : "Sign in";
      if (label) label.textContent = text;
      else link.textContent = text;
      const compactLabel = link.querySelector("[data-auth-compact-label]");
      if (compactLabel) compactLabel.textContent = auth.user ? compactName : "Sign in";
      link.classList.toggle("is-signed-in", Boolean(auth.user));
      link.setAttribute("aria-label", auth.user ? `My account: ${fullName}` : text);
    });
    document.querySelectorAll("[data-admin-link]").forEach((link) => {
      link.hidden = auth.user?.role !== "admin";
    });
  }

  function message(text, success = false) {
    const node = document.querySelector("#auth-message");
    if (!node) return;
    node.textContent = text;
    node.classList.toggle("is-success", success);
    node.classList.toggle("is-error", Boolean(text) && !success);
    node.setAttribute("role", success ? "status" : "alert");
  }

  function destination(user) {
    const next = new URLSearchParams(location.search).get("next");
    if (next === "admin.html" && user.role === "admin") return "admin.html";
    if (next === "intranet.html" && user.role === "admin") return "intranet.html";
    if (["account.html", "reviews.html"].includes(next)) return next;
    return user.role === "admin" ? "admin.html" : "account.html";
  }

  function busy(form, working) {
    const button = form.querySelector('button[type="submit"]');
    if (!button) return;
    if (!button.dataset.originalLabel) button.dataset.originalLabel = button.textContent;
    button.disabled = working;
    button.textContent = working ? "Please wait…" : button.dataset.originalLabel;
    form.setAttribute("aria-busy", String(working));
  }

  // Keep the return to reviews when a visitor switches between sign-in and registration.
  if (new URLSearchParams(location.search).get("next") === "reviews.html") {
    document.querySelectorAll('.auth-switch a[href="register.html"], .auth-switch a[href="login.html"]').forEach((link) => {
      link.href = link.getAttribute("href") + "?next=reviews.html";
    });
  }

  async function logout() {
    await request("/api/auth/logout", { method: "POST", body: {} });
    auth.user = null;
    auth.csrfToken = null;
    location.assign("login.html");
  }

  document.querySelectorAll("[data-toggle-password]").forEach((button) => {
    button.addEventListener("click", () => {
      const field = document.getElementById(button.dataset.togglePassword);
      if (!(field instanceof HTMLInputElement)) return;
      const reveal = field.type === "password";
      field.type = reveal ? "text" : "password";
      button.textContent = reveal ? "Hide" : "Show";
      button.setAttribute("aria-label", `${reveal ? "Hide" : "Show"} password`);
      button.setAttribute("aria-pressed", String(reveal));
    });
  });

  document.querySelectorAll("[data-auth-logout]").forEach((button) => {
    button.addEventListener("click", async () => {
      button.disabled = true;
      try { await logout(); }
      catch (error) { message(error.message); button.disabled = false; }
    });
  });

  const loginForm = document.querySelector("#login-form");
  const mfaForm = document.querySelector("#login-mfa-form");
  let pendingChallenge = null;
  let challengeExpiry = null;

  function resetSignIn() {
    pendingChallenge = null;
    clearTimeout(challengeExpiry);
    challengeExpiry = null;
    mfaForm?.reset();
    const code = document.querySelector("#login-mfa-code");
    if (code) code.inputMode = "numeric";
    const label = document.querySelector("#login-mfa-code-label");
    if (label) label.textContent = "Authenticator code";
    const hint = document.querySelector("#login-mfa-hint");
    if (hint) hint.textContent = "Codes change every 30 seconds. Each code can be used once.";
    const verification = document.querySelector("#login-mfa");
    if (verification) verification.hidden = true;
    if (loginForm) loginForm.hidden = false;
    document.querySelector("#login-password")?.focus();
  }

  document.querySelector("#login-use-recovery")?.addEventListener("change", (event) => {
    const recovery = event.target.checked;
    const field = document.querySelector("#login-mfa-code");
    field.value = "";
    field.inputMode = recovery ? "text" : "numeric";
    document.querySelector("#login-mfa-code-label").textContent = recovery ? "Recovery code" : "Authenticator code";
    document.querySelector("#login-mfa-hint").textContent = recovery
      ? "Enter one of the recovery codes you saved. A recovery code works only once."
      : "Codes change every 30 seconds. Each code can be used once.";
    field.focus();
  });
  document.querySelector("#login-mfa-back")?.addEventListener("click", () => { resetSignIn(); message(""); });

  mfaForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!mfaForm.reportValidity()) return;
    if (!pendingChallenge) { resetSignIn(); message("Please enter your email and password again."); return; }
    busy(mfaForm, true);
    message("");
    try {
      const { user } = await request("/api/auth/verify", {
        method: "POST", body: { challenge: pendingChallenge, code: new FormData(mfaForm).get("code").trim() },
      });
      pendingChallenge = null;
      clearTimeout(challengeExpiry);
      mfaForm.reset();
      location.assign(destination(user));
    } catch (error) {
      message(error.message);
      document.querySelector("#login-mfa-code").value = "";
      document.querySelector("#login-mfa-code").focus();
    } finally {
      busy(mfaForm, false);
    }
  });

  loginForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!loginForm.reportValidity()) return;
    message("");
    busy(loginForm, true);
    const fields = new FormData(loginForm);
    try {
      const result = await request("/api/auth/login", {
        method: "POST",
        body: { email: fields.get("email").trim(), password: fields.get("password"), remember: fields.get("remember") !== null },
      });
      if (result.requiresTwoFactor) {
        pendingChallenge = result.challenge;
        loginForm.elements.namedItem("password").value = "";
        loginForm.hidden = true;
        document.querySelector("#login-mfa").hidden = false;
        document.querySelector("#login-mfa-code").focus();
        clearTimeout(challengeExpiry);
        challengeExpiry = setTimeout(() => {
          resetSignIn();
          message("Your verification time has expired. Please sign in again.");
        }, Math.min(result.expiresIn || 300, 300) * 1000);
      } else {
        location.assign(destination(result.user));
      }
    } catch (error) {
      message(error.message);
    } finally {
      busy(loginForm, false);
    }
  });

  const registerForm = document.querySelector("#register-form");
  const confirmation = registerForm?.elements.namedItem("confirmPassword");
  function validateConfirmation() {
    if (!(confirmation instanceof HTMLInputElement)) return;
    confirmation.setCustomValidity(confirmation.value === registerForm.elements.namedItem("password").value ? "" : "Your passwords don't match.");
  }
  registerForm?.addEventListener("input", validateConfirmation);
  registerForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    validateConfirmation();
    if (!registerForm.reportValidity()) return;
    message("");
    busy(registerForm, true);
    const fields = new FormData(registerForm);
    try {
      const { user } = await request("/api/auth/register", {
        method: "POST",
        body: {
          firstName: fields.get("firstName").trim(),
          lastName: fields.get("lastName").trim(),
          city: fields.get("city").trim(),
          country: fields.get("country").trim(),
          email: fields.get("email").trim(),
          password: fields.get("password"),
          terms: fields.get("terms") !== null,
          ageConfirmed: fields.get("ageConfirmed") !== null,
        },
      });
      location.assign(destination(user));
    } catch (error) {
      message(error.message);
    } finally {
      busy(registerForm, false);
    }
  });

  function populateAccount(user) {
    const name = document.querySelector("#account-name");
    const email = document.querySelector("#account-email");
    const since = document.querySelector("#account-since");
    const avatar = document.querySelector("#account-avatar");
    if (name) name.textContent = user.name;
    if (email) email.textContent = user.email;
    if (since) since.textContent = new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric" }).format(new Date(user.created_at));
    if (avatar) avatar.textContent = user.name.trim().split(/\s+/).slice(0, 2).map((part) => Array.from(part)[0]).join("").toUpperCase();
    for (const field of ["firstName", "lastName", "city", "country"]) {
      const input = document.querySelector(`#profile-form [name="${field}"]`);
      if (input) input.value = user[field] || "";
    }
    updateAccountLinks();
  }

  const profileForm = document.querySelector("#profile-form");
  profileForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!profileForm.reportValidity()) return;
    const fields = new FormData(profileForm);
    const body = {
      firstName: fields.get("firstName").trim(),
      lastName: fields.get("lastName").trim(),
      city: fields.get("city").trim(),
      country: fields.get("country").trim(),
    };
    if (fields.get("newPassword")) {
      if (!fields.get("currentPassword")) {
        message("Enter your current password to choose a new one.");
        profileForm.elements.namedItem("currentPassword").focus();
        return;
      }
      body.currentPassword = fields.get("currentPassword");
      body.newPassword = fields.get("newPassword");
    }
    message("");
    busy(profileForm, true);
    try {
      const { user } = await request("/api/account", { method: "PATCH", body });
      populateAccount(user);
      profileForm.elements.namedItem("currentPassword").value = "";
      profileForm.elements.namedItem("newPassword").value = "";
      message("Your account details have been updated.", true);
      if (body.newPassword) window.dispatchEvent(new CustomEvent("velora:security-changed", { detail: { passwordChanged: true } }));
    } catch (error) {
      if (error.status === 401) location.assign("login.html?next=account.html");
      else message(error.message);
    } finally {
      busy(profileForm, false);
    }
  });

  auth.ready = request("/api/auth/me").then(({ user }) => user);
  // Some public pages only need the account link and can remain available offline.
  auth.ready.catch(() => {});
  window.addEventListener("pagehide", () => {
    if (document.body.dataset.authPage === "account") {
      const content = document.querySelector("#account-content");
      if (content) content.hidden = true;
    }
    if (document.body.classList.contains("admin-page")) {
      const shell = document.querySelector("#admin-shell");
      if (shell) shell.hidden = true;
    }
    pendingChallenge = null;
    clearTimeout(challengeExpiry);
    mfaForm?.reset();
  });
  // A page restored with Back must check its session instead of revealing cached
  // account information after another tab or device has signed it out.
  window.addEventListener("pageshow", (event) => {
    if (event.persisted && (document.body.dataset.authPage === "account" || document.body.classList.contains("admin-page"))) location.reload();
  });
  const page = document.body.dataset.authPage;
  if (page === "login" && new URLSearchParams(location.search).get("deleted") === "1") {
    message("Your account has been deleted and all account sessions have been signed out.", true);
  }
  if (page) {
    auth.ready.then((user) => {
      if (page === "account") {
        if (!user) { location.replace("login.html?next=account.html"); return; }
        populateAccount(user);
        document.querySelector("#account-content").hidden = false;
        document.querySelector("#account-loading").hidden = true;
      } else if (user) {
        location.replace(destination(user));
      }
    }).catch((error) => {
      if (page === "account") document.querySelector("#account-loading").textContent = error.message;
      else message(error.message);
    });
  }
  if (!document.body.classList.contains("admin-page")) {
    const supportStyle = document.createElement("link");
    supportStyle.rel = "stylesheet";
    supportStyle.href = "support-chat.css?v=1";
    const supportScript = document.createElement("script");
    supportScript.src = "support-chat.js?v=1";
    supportScript.defer = true;
    document.head.append(supportStyle, supportScript);
  }
})();
