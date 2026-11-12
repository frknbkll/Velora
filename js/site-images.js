/* Responsive fallbacks for dynamic public images; original URLs stay available for zoom. */
(() => {
  "use strict";
  const sources = window.VeloraImageSources;
  if (!sources) return;
  function optimize(image) {
    if (!(image instanceof HTMLImageElement) || image.closest("#image-zoom-dialog,#velora-photo-inspector,[data-photo-original]")) return;
    const original = image.getAttribute("src");
    // Optimized src URLs are not manifest keys, so our own mutations stop here.
    if (!sources.get(original)) return;
    const sizes = image.sizes || (image.closest(".admin-product-name,.admin-photo-card,.shop-item,.product-gallery-thumbnails") ? "100px" :
      image.closest(".team-profile-portrait") ? "(max-width: 650px) 90vw, 28vw" : "(max-width: 760px) 100vw, 50vw");
    sources.apply(image, original, sizes);
  }
  function scan(root) {
    if (root instanceof HTMLImageElement) optimize(root);
    root.querySelectorAll?.("img").forEach(optimize);
  }
  scan(document);
  new MutationObserver((records) => {
    records.forEach((record) => {
      if (record.type === "attributes") optimize(record.target);
      else record.addedNodes.forEach(scan);
    });
  }).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["src"] });
})();
