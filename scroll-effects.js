(() => {
  "use strict";

  const root = document.documentElement;
  const header = document.querySelector(".site-header");
  const hero = document.querySelector(".hero");
  const heroVisual = hero?.querySelector(".hero-visual");
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const desktop = matchMedia("(min-width: 901px)");
  let frame = 0;
  let headerHeight = 0;
  let heroTop = 0;
  let heroHeight = 0;
  let previousDrift = null;

  function updateScroll() {
    frame = 0;
    const position = window.scrollY;
    header?.classList.toggle("is-scrolled", position > 80);
    header?.classList.toggle("is-over-hero", Boolean(hero && position < heroTop + heroHeight - headerHeight));

    if (heroVisual && desktop.matches && !reducedMotion.matches) {
      const drift = Math.round(Math.max(0, Math.min(position - heroTop, heroHeight)) * .08);
      if (drift !== previousDrift) {
        heroVisual.style.setProperty("--hero-drift", `${drift}px`);
        previousDrift = drift;
      }
    }
  }

  function scheduleScroll() {
    if (!frame) frame = requestAnimationFrame(updateScroll);
  }

  function measure() {
    headerHeight = header?.offsetHeight || 0;
    if (hero) {
      const bounds = hero.getBoundingClientRect();
      heroTop = bounds.top + window.scrollY;
      heroHeight = bounds.height;
    }
    if (header) root.style.setProperty("--anchor-offset", `${headerHeight + 20}px`);
    scheduleScroll();
  }

  function updateMotion() {
    const enabled = desktop.matches && !reducedMotion.matches;
    heroVisual?.classList.toggle("has-scroll-depth", enabled);
    if (!enabled) {
      heroVisual?.style.removeProperty("--hero-drift");
      previousDrift = null;
    }
    scheduleScroll();
  }

  // Keep wheel, touch, keyboard, and dialog scrolling under browser control.
  if (header || heroVisual) {
    window.addEventListener("scroll", scheduleScroll, { passive: true });
    window.addEventListener("resize", measure, { passive: true });
    window.addEventListener("pageshow", measure);
    if ("ResizeObserver" in window) {
      const resizeObserver = new ResizeObserver(measure);
      if (header) resizeObserver.observe(header);
      if (hero) resizeObserver.observe(hero);
    }
    document.fonts?.ready.then(measure);
    reducedMotion.addEventListener("change", updateMotion);
    desktop.addEventListener("change", updateMotion);
    measure();
    updateMotion();
  }

  if (!("IntersectionObserver" in window) || reducedMotion.matches) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(({ target, isIntersecting }) => {
      if (isIntersecting) reveal(target);
    });
  }, { rootMargin: "0px 0px -32px 0px", threshold: 0 });

  function reveal(target) {
    target.classList.add("is-revealed");
    observer.unobserve(target);
  }

  function revealAll() {
    document.querySelectorAll("[data-scroll-reveal]").forEach(reveal);
    observer.disconnect();
  }

  const targets = document.querySelectorAll(
    ".section-heading, .story-visual, .story-copy, .founder-card, .newsletter, " +
    ".vacancy-list-heading, .vacancy-tile, .vacancy-note, .vacancy-detail-section, .vacancy-detail-note"
  );
  targets.forEach((target) => {
    // Content already in view (including restored pages) stays immediately visible.
    if (target.getBoundingClientRect().top < window.innerHeight + 24) return;
    if (target.matches(".founder-card, .vacancy-tile")) {
      const index = Array.from(target.parentElement.children).indexOf(target);
      target.style.setProperty("--reveal-delay", `${index % 4 * 45}ms`);
    }
    target.setAttribute("data-scroll-reveal", "");
    observer.observe(target);
  });

  document.addEventListener("focusin", ({ target }) => {
    const pending = target.closest("[data-scroll-reveal]");
    if (pending) reveal(pending);
  });
  window.addEventListener("hashchange", () => {
    try {
      const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      const pending = target?.closest("[data-scroll-reveal]");
      if (pending) reveal(pending);
    } catch {
      // Malformed URL fragments do not affect navigation or content visibility.
    }
  });
  reducedMotion.addEventListener("change", () => {
    if (reducedMotion.matches) revealAll();
  });
  window.addEventListener("beforeprint", revealAll);
})();
