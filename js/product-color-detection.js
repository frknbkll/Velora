/* Clothing-color estimates stay in this browser. Backgrounds and skin are not product swatches. */
(function (root) {
  "use strict";

  const MAX_FILE_BYTES = 8 * 1024 * 1024;
  const MAX_IMAGE_PIXELS = 40 * 1000 * 1000;
  const SAMPLE_EDGE = 192;
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const median = (values) => values.sort((a, b) => a - b)[Math.floor(values.length / 2)];

  function hsv(r, g, b) {
    const maximum = Math.max(r, g, b), minimum = Math.min(r, g, b), delta = maximum - minimum;
    let hue = delta === 0 ? 0 : maximum === r ? ((g - b) / delta) % 6 : maximum === g ? (b - r) / delta + 2 : (r - g) / delta + 4;
    hue = (hue * 60 + 360) % 360;
    return { h: hue, s: maximum ? delta / maximum : 0, v: maximum / 255, delta };
  }

  function nameColor(r, g, b) {
    const { h, s, v, delta } = hsv(r, g, b);
    const warm = r - b > 8 && r >= g - 3 && h < 70;
    if (v < 0.12 || (v < 0.25 && delta < 10 && s < 0.20)) return "Black";
    if (s < 0.085 || delta < 12) {
      if (v > 0.86) return warm ? "Ivory" : "White";
      if (v > 0.72 && warm) return "Beige";
      return "Grey";
    }
    if (h < 50 || h >= 345) {
      if (v > 0.82 && s < 0.20) return "Ivory";
      if (h >= 12 && h < 50 && s < 0.40 && v > 0.66) return "Beige";
      if (h >= 14 && h < 50 && s < 0.31 && v >= 0.40) return "Taupe";
      if (h < 50 && v < 0.70 && g - b >= 2 && r - g <= (g - b) * 8 && s < 0.75) return "Brown";
      if (h >= 12 && h < 50 && v < 0.70) return "Brown";
      if (h < 15 || h >= 345) {
        if (v < 0.62) return "Burgundy";
        if (s < 0.52 && v > 0.71) return "Pink";
        return "Red";
      }
      if (v > 0.80 && s < 0.50) return "Pink";
      return h < 43 ? "Orange" : "Yellow";
    }
    if (h < 75) {
      if (v > 0.82 && s < 0.20) return "Ivory";
      if (v < 0.70 || s < 0.36) return "Olive";
      return "Yellow";
    }
    if (h < 175) return h < 100 && v < 0.65 ? "Olive" : "Green";
    if (h < 265) return v < 0.46 ? "Navy" : "Blue";
    if (h < 335) return v > 0.70 && s < 0.48 ? "Pink" : "Purple";
    return v < 0.62 ? "Burgundy" : "Pink";
  }

  function pixel(data, width, x, y) {
    const index = (y * width + x) * 4;
    return [data[index], data[index + 1], data[index + 2], data[index + 3]];
  }
  function distance(a, b) {
    // A luminance component prevents a dark shadow becoming a separate hue.
    return Math.sqrt((a[0] - b[0]) ** 2 * 0.30 + (a[1] - b[1]) ** 2 * 0.59 + (a[2] - b[2]) ** 2 * 0.11);
  }
  function backgroundForRow(data, width, height, y) {
    const values = [[], [], []];
    for (const fraction of [0.025, 0.06, 0.10, 0.90, 0.94, 0.975]) {
      const rgb = pixel(data, width, Math.min(width - 1, Math.floor(width * fraction)), y);
      if (rgb[3] < 128) continue;
      for (let c = 0; c < 3; c++) values[c].push(rgb[c]);
    }
    return values[0].length ? values.map(median) : null;
  }

  function regionFor(width, height, options) {
    const name = String(options.productName || "").toLowerCase();
    const portrait = height / width > 1.22;
    const bottoms = /\b(trousers?|pants?|jeans|skirts?|shorts?)\b/.test(name) && !/\b(set|suit|look|coord|co-ord|ensemble)\b/.test(name);
    const outer = /\b(blazer|jacket|cardigan|blouse|shirt|sweater|jumper|top)\b/.test(name) && !/\b(set|suit|look|coord|co-ord|ensemble)\b/.test(name);
    const coat = /\b(coat|trench)\b/.test(name);
    if (!portrait) return { left: 0.19, right: 0.81, top: 0.22, bottom: 0.80, mode: "flat" };
    if (bottoms) return { left: 0.27, right: 0.73, top: 0.53, bottom: 0.85, mode: "bottoms" };
    if (coat) return { left: 0.25, right: 0.75, top: 0.30, bottom: 0.67, mode: "upper" };
    if (outer) return { left: 0.25, right: 0.75, top: 0.25, bottom: 0.43, mode: "upper" };
    return { left: 0.27, right: 0.73, top: 0.38, bottom: 0.80, mode: "outfit" };
  }

  function analyzePixels(data, width, height, options = {}) {
    if (!Number.isInteger(width) || !Number.isInteger(height) || width < 16 || height < 16 || width * height > SAMPLE_EDGE * SAMPLE_EDGE || data.length !== width * height * 4) return null;
    const region = regionFor(width, height, options), groups = new Map();
    let possible = 0, foreground = 0, total = 0, strong = 0;
    const startY = Math.floor(region.top * height), endY = Math.floor(region.bottom * height);
    for (let y = startY; y < endY; y++) {
      const background = backgroundForRow(data, width, height, y);
      for (let x = Math.floor(region.left * width); x < region.right * width; x++) {
        const rgba = pixel(data, width, x, y), [r, g, b, alpha] = rgba;
        if (alpha < 200) continue;
        const nx = x / width, ny = y / height;
        let weight = 0.6 + 0.4 * (1 - Math.abs(nx - 0.5) / 0.32);
        if (region.mode === "upper") {
          // Open jackets have a different-colored top in the middle; their lower side panels carry the garment color.
          weight *= 0.15 + 2.0 * Math.min(1, Math.abs(nx - 0.5) / 0.13);
          if (ny < 0.33) weight *= 0.55;
        }
        possible += weight;
        const bgDistance = background ? distance(rgba, background) : 255;
        // Keep subtle off-white cloth, but strongly discount truly uniform studio backdrops.
        const separation = clamp((bgDistance - 2) / 15, 0, 1);
        foreground += weight * separation;
        if (bgDistance > 14) strong += weight;
        weight *= 0.10 + 0.90 * separation;
        const color = hsv(r, g, b);
        const skinLike = color.h >= 5 && color.h <= 43 && color.s > 0.18 && color.s < 0.67 && r > 80 && r > g && g > b;
        if (skinLike && ((ny < 0.34 && Math.abs(nx - 0.5) < 0.12) || (region.mode !== "upper" && Math.abs(nx - 0.5) > 0.19))) weight *= 0.16;
        if (ny < 0.34 && color.h >= 12 && color.h < 48 && color.v < 0.33) weight *= 0.30;
        const name = nameColor(r, g, b);
        if (!groups.has(name)) groups.set(name, { name, weight: 0, pixels: [] });
        const group = groups.get(name);
        group.weight += weight;
        group.pixels.push({ rgb: [r, g, b], weight, x: nx, y: ny });
        total += weight;
      }
    }
    if (possible < 80 || foreground / possible < 0.09 || strong / possible < 0.035 || !total) return null;
    const ranked = [...groups.values()].sort((a, b) => b.weight - a.weight), winner = ranked[0];
    if (!winner || winner.pixels.length < 35) return null;
    const share = winner.weight / total, margin = (winner.weight - (ranked[1]?.weight || 0)) / total;
    if (share < 0.31 || margin < 0.055) return null;
    // Use the actual image's weighted median, never a fixed palette hex.
    const rgb = [0, 1, 2].map((channel) => {
      const samples = winner.pixels.slice().sort((a, b) => a.rgb[channel] - b.rgb[channel]);
      let sum = 0;
      for (const sample of samples) { sum += sample.weight; if (sum >= winner.weight / 2) return sample.rgb[channel]; }
      return samples[samples.length - 1].rgb[channel];
    });
    const hex = "#" + rgb.map((value) => value.toString(16).padStart(2, "0")).join("");
    const coverage = clamp(foreground / possible, 0, 1);
    const confidence = Math.min(0.93, 0.28 + share * 0.40 + margin * 0.20 + coverage * 0.12);
    return { name: winner.name, hex, confidence: Number(confidence.toFixed(3)) };
  }

  function loadImage(source) {
    return new Promise((resolve) => {
      let image = null, reader = null, finished = false;
      const timer = setTimeout(() => finish(null), 8000);
      function finish(value) {
        if (finished) return;
        finished = true; clearTimeout(timer);
        if (reader?.readyState === 1) reader.abort();
        if (image) { image.onload = null; image.onerror = null; if (!value) image.removeAttribute("src"); }
        resolve(value);
      }
      function open(url) {
        if (finished) return;
        image = new Image();
        image.onload = () => finish(image.naturalWidth * image.naturalHeight <= MAX_IMAGE_PIXELS && image.naturalWidth >= 16 && image.naturalHeight >= 16 ? image : null);
        image.onerror = () => finish(null);
        image.src = url;
      }
      try {
        if (typeof Blob !== "undefined" && source instanceof Blob) {
          if (!source.size || source.size > MAX_FILE_BYTES || !["image/jpeg", "image/png", "image/webp"].includes(source.type)) return finish(null);
          // Data URLs also work with Velora's restrictive img-src policy; no object URLs are retained.
          reader = new FileReader(); reader.onload = () => open(reader.result); reader.onerror = () => finish(null); reader.onabort = () => finish(null);
          reader.readAsDataURL(source);
        } else if (typeof source === "string") {
          const url = new URL(source, root.location.href);
          if (url.origin !== root.location.origin || !["http:", "https:"].includes(url.protocol) || url.username || url.password) return finish(null);
          open(url.href);
        } else finish(null);
      } catch (_) { finish(null); }
    });
  }

  async function detect(source, options = {}) {
    const image = await loadImage(source);
    if (!image) return null;
    const canvas = document.createElement("canvas");
    try {
      const scale = Math.min(1, SAMPLE_EDGE / Math.max(image.naturalWidth, image.naturalHeight));
      canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
      canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
      const context = canvas.getContext("2d", { willReadFrequently: true });
      if (!context) return null;
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      return analyzePixels(context.getImageData(0, 0, canvas.width, canvas.height).data, canvas.width, canvas.height, options);
    } catch (_) { return null; }
    finally { canvas.width = 0; canvas.height = 0; image.removeAttribute("src"); }
  }

  root.VeloraProductColor = Object.freeze({ detect });
  // A pure entry point lets regression checks use the same classifier without DOM or network mocks.
  if (typeof module !== "undefined" && module.exports) module.exports = { analyzePixels, nameColor };
})(typeof window === "undefined" ? globalThis : window);
