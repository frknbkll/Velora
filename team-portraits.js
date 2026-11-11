/* An alternate moment from each portrait session, on hover, tap or keyboard. */
(() => {
  "use strict";

  const finePointer = matchMedia("(hover: hover) and (pointer: fine)");
  const states = [];
  let active = null;

  function render(state) {
    const shown = state.wanted && state.ready && !state.failed;
    state.button.dataset.portrait = shown ? "alternate" : "original";
    state.button.setAttribute("aria-pressed", String(shown));
    state.label.textContent = shown ? "Back to portrait" : "Another side";
    state.button.setAttribute("aria-label", `${state.label.textContent}: ${state.name}`);
  }

  function show(state, wanted) {
    if (state.failed) return;
    if (wanted && active && active !== state) {
      active.wanted = false;
      render(active);
    }
    state.wanted = wanted;
    if (wanted) {
      active = state;
      load(state, true);
    } else if (active === state) active = null;
    render(state);
  }

  function load(state, intentional = false) {
    if (intentional) state.alternate.fetchPriority = "high";
    if (state.loading || state.ready || state.failed) return;
    state.loading = true;
    state.button.setAttribute("aria-busy", "true");
    state.alternate.addEventListener("load", async () => {
      try { await state.alternate.decode(); } catch { /* Loaded pixels remain usable. */ }
      state.loading = false;
      state.ready = true;
      state.button.removeAttribute("aria-busy");
      render(state);
    }, { once: true });
    state.alternate.addEventListener("error", () => {
      state.loading = false;
      state.failed = true;
      state.wanted = false;
      if (active === state) active = null;
      state.button.removeAttribute("aria-busy");
      state.button.dataset.portraitUnavailable = "true";
      state.button.disabled = true;
      state.button.setAttribute("aria-label", `Portrait of ${state.name}`);
      state.button.setAttribute("aria-pressed", "false");
      state.alternate.remove();
    }, { once: true });
    if (window.VeloraImageSources) window.VeloraImageSources.apply(state.alternate, state.source, "(max-width: 650px) 90vw, 28vw");
    else state.alternate.src = state.source;
  }

  document.querySelectorAll(".team-profile-portrait").forEach((wrapper) => {
    const original = wrapper.querySelector("img");
    const name = wrapper.closest(".team-profile")?.querySelector("h3")?.textContent.trim();
    const source = original?.dataset.originalSrc || original?.getAttribute("src");
    if (!name || !/^assets\/team\/[a-z0-9-]+\.jpg$/.test(source || "")) return;

    const button = document.createElement("button");
    button.type = "button";
    button.className = `${wrapper.className} team-portrait-swap`;
    button.dataset.teamName = name;
    button.setAttribute("aria-describedby", "team-portraits-help");
    original.classList.add("team-portrait-original");

    const alternate = document.createElement("img");
    alternate.className = "team-portrait-alternate";
    alternate.alt = "";
    alternate.setAttribute("aria-hidden", "true");
    alternate.width = original.width || 768;
    alternate.height = original.height || 960;
    alternate.decoding = "async";
    alternate.fetchPriority = "low";

    const hint = document.createElement("span");
    hint.className = "team-portrait-hint";
    hint.setAttribute("aria-hidden", "true");
    const mark = document.createElement("span");
    mark.className = "team-portrait-hint-mark";
    mark.textContent = "+";
    const label = document.createElement("span");
    hint.append(mark, label);
    button.append(original, alternate, hint);
    wrapper.replaceWith(button);

    const state = { button, original, alternate, label, name, source: source.replace("assets/team/", "assets/team/hover/"), ready: false, loading: false, failed: false, wanted: false, hovering: false };
    states.push(state);
    render(state);
    button.addEventListener("pointerenter", (event) => {
      if (event.pointerType === "touch" || !finePointer.matches) return;
      state.hovering = true;
      show(state, true);
    });
    button.addEventListener("pointerleave", (event) => {
      if (event.pointerType === "touch") return;
      state.hovering = false;
      show(state, false);
    });
    button.addEventListener("click", () => show(state, !state.wanted));
    button.addEventListener("focus", () => load(state, true));
    button.addEventListener("blur", () => { if (!state.hovering) show(state, false); });
    button.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      show(state, false);
      event.preventDefault();
    });
  });

  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const state = states.find((item) => item.button === entry.target);
        if (state) load(state);
        observer.unobserve(entry.target);
      });
    }, { rootMargin: "350px" });
    states.forEach((state) => observer.observe(state.button));
  }

  window.addEventListener("pagehide", () => {
    states.forEach((state) => { state.wanted = false; state.hovering = false; render(state); });
    active = null;
  });
})();
