const menuToggle = document.querySelector(".menu-toggle");
const primaryNav = document.querySelector(".primary-nav");
const menuToggleLabel = document.querySelector(".menu-toggle-label");
menuToggle?.addEventListener("click", () => {
  const isExpanded = menuToggle.getAttribute("aria-expanded") === "true";
  menuToggle.setAttribute("aria-expanded", String(!isExpanded));
  if (menuToggleLabel) menuToggleLabel.textContent = isExpanded ? "Open menu" : "Close menu";
  primaryNav?.classList.toggle("is-open", !isExpanded);
});

primaryNav?.querySelectorAll("a").forEach((link) => {
  link.addEventListener("click", () => {
    menuToggle?.setAttribute("aria-expanded", "false");
    if (menuToggleLabel) menuToggleLabel.textContent = "Open menu";
    primaryNav.classList.remove("is-open");
  });
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || menuToggle?.getAttribute("aria-expanded") !== "true") return;
  menuToggle.setAttribute("aria-expanded", "false");
  if (menuToggleLabel) menuToggleLabel.textContent = "Open menu";
  primaryNav?.classList.remove("is-open");
  menuToggle.focus();
});

const lookPhotoGroups = [
  {
    upload: 1,
    founder: "Victoria Mendez",
    collage: true,
    collection: "THE WEEKEND EDIT",
    names: [
      "The Off-Duty Bandeau",
      "The Lilac Hour Mini",
      "The City-Light Knit Set",
      "The After-Dark Zip Dress",
      "The Weekend Denim Set",
      "The Soft-Sage Bandeau",
      "The Rosewater Mini Dress",
      "The Merlot Evening Dress",
      "The Clean-Slate Slip Dress",
    ],
  },
  {
    upload: 3,
    founder: "Luna Moretti",
    collage: true,
    collection: "THE SLOW MORNING EDIT",
    names: [
      "The Espresso Wrap Dress",
      "The Sunday Silk Set",
      "The Quiet-Luxe Knit Dress",
      "The Midnight Loungewear Set",
      "The Ivory City Trouser",
      "The Weekend Wrap Set",
      "The Soft-Taupe Wrap Set",
      "The Chocolate Lounge Set",
      "The Little-Black Shirt Dress",
    ],
  },
  {
    upload: 4,
    founder: "Derya Kasal",
    collage: true,
    collection: "THE EVERYDAY EDIT",
    names: [
      "The Ivory Linen Set",
      "The Sage Linen Set",
      "The Ivory Tailored Look",
      "The Sunday White Shirt",
      "The After-Dark Trouser Set",
      "The Espresso Day Dress",
      "The Modern Utility Co-ord",
      "The Midnight Tailored Set",
      "The Sandstone Wrap Set",
    ],
    imageFiles: [
      "derya-ivory-linen-set.jpg",
      "derya-sage-linen-set.jpg",
      "derya-ivory-tailored-look.jpg",
      null,
      null,
      null,
      null,
      null,
      null,
    ],
  },
  {
    upload: 5,
    founder: "Victoria Mendez",
    collage: true,
    collection: "THE AFTER-HOURS EDIT",
    names: [
      "The Sculpted Satin Dress",
      "The Off-Duty Halter Set",
      "The City-Ready Black Dress",
      "The Sunday Knit Co-ord",
      "The Soft-Focus Satin Set",
      "The Chocolate Evening Dress",
      "The Wildflower Chiffon Dress",
      "The Ivory Satin Co-ord",
      "The Sage-Tone City Set",
    ],
  },
  {
    upload: 6,
    founder: "Derya Kasal",
    collage: true,
    collection: "THE POLISHED EDIT",
    names: [
      "The Emerald Tailored Suit",
      "The Ivory Power Suit",
      "The Chocolate Longline Blazer",
      "The Olive Trench Ensemble",
      "The Taupe Tailored Set",
      "The Chocolate Blazer Co-ord",
      "The Soft-Taupe Dress",
      "The Cocoa Evening Set",
      "The Everyday Neutral Blazer",
    ],
    imageFiles: [
      "derya-emerald-tailoring.jpg",
      "derya-ivory-tailoring.jpg",
      "derya-chocolate-tailoring.jpg",
      "derya-olive-trench.jpg",
      "derya-taupe-tailoring.jpg",
      "derya-chocolate-coord.jpg",
      null,
      null,
      null,
    ],
  },
  {
    upload: 7,
    founder: "Derya Kasal",
    collage: true,
    collection: "THE REFINED EDIT",
    names: [
      "The Ivory Knit Twin Set",
      "The Espresso Lounge Dress",
      "The Modern Black Blazer",
      "The Evening Trouser Look",
      "The Ivory City Trench",
      "The Soft-Silk Set",
      "The Sculpted Mocha Dress",
      "The Dark-Romance Gown",
      "The Taupe Tailored Set",
    ],
  },
  {
    upload: 8,
    founder: "Beyza Keskinci",
    collage: true,
    collection: "THE MODEST EDIT",
    names: [
      "The Rosewater Occasion Abaya",
      "The Sandstone Drape Abaya",
      "The Espresso Evening Abaya",
      "The Mocha Belted Abaya",
      "The Champagne Occasion Abaya",
      "The Espresso Trench Look",
      "The Stone Tailored Look",
      "The Espresso City Dress",
      "The Soft-White Lounge Set",
    ],
    imageFiles: [
      "rosewater-occasion-abaya.jpg",
      "modest-drape-abaya.jpg",
      "espresso-evening-abaya.jpg",
      "mocha-belted-abaya.jpg",
      "champagne-occasion-abaya.jpg",
      "espresso-trench-look.jpg",
      "stone-tailored-look.jpg",
      null,
    ],
  },
  { upload: 9, founder: "Beyza Keskinci", collage: false, collection: "THE EVERYDAY EDIT", names: ["The Sculpted Wrap Blouse"] },
  {
    upload: 10,
    founder: "Beyza Keskinci",
    collage: true,
    collection: "THE OCCASION EDIT",
    names: [
      "The Merlot Sculpted Gown",
      "The Midnight Occasion Dress",
      "The Pearl Drape Dress",
      "The Olive Evening Gown",
      "The Rose-Taupe Occasion Set",
      "The Chocolate Hour Dress",
      "The Sandstone Wrap Gown",
      "The Black-Tie Evening Dress",
      "The Lavender Drape Dress",
    ],
  },
  { upload: 11, founder: "Beyza Keskinci", collage: false, collection: "THE TAILORED EDIT", names: ["The Heritage Blazer"] },
  { upload: 12, founder: "Beyza Keskinci", collage: false, collection: "THE TAILORED EDIT", names: ["The After-Hours Power Suit"] },
];

const individualLooks = lookPhotoGroups.flatMap(({ upload, founder, collage, collection, names, imageFiles }) =>
  Array.from({ length: collage ? 9 : 1 }, (_, index) => {
    const suppliedImage = imageFiles?.[index];
    if (collage && !suppliedImage) return null;

    const imageName = suppliedImage ?? (collage
      ? `look-${String(upload).padStart(2, "0")}-${String(index + 1).padStart(2, "0")}.jpg`
      : `look-${String(upload).padStart(2, "0")}.jpg`);

    return {
      image: imageName.startsWith("assets/") ? imageName : `assets/gallery/${imageName}`,
      founder,
      collection,
      name: names[index],
      number: collage ? `${String(upload).padStart(2, "0")} · ${String(index + 1).padStart(2, "0")}` : String(upload).padStart(2, "0"),
    };
  }).filter((look) => look !== null),
);

individualLooks.push(
  {
    image: "assets/gallery/derya-city-cream-look.jpg",
    founder: "Derya Kasal",
    collection: "THE EVERYDAY EDIT",
    name: "The City-Cream Trouser Set",
    number: "14 · 01",
  },
  {
    image: "assets/gallery/derya-soft-knit-lounge-set.jpg",
    founder: "Derya Kasal",
    collection: "THE SOFT EDIT",
    name: "The Cloud-Knit Lounge Set",
    number: "14 · 02",
  },
  {
    image: "assets/gallery/derya-rose-stripe-pajama-set.jpg",
    founder: "Derya Kasal",
    collection: "THE SOFT EDIT",
    name: "The Rose-Stripe Pajama Set",
    number: "14 · 03",
  },
  {
    image: "assets/gallery/luna-ivory-tie-neck-set.jpg",
    founder: "Luna Moretti",
    collection: "THE EVERYDAY EDIT",
    name: "The Ivory Tie-Neck Set",
    number: "15 · 01",
  },
  {
    image: "assets/gallery/luna-cloud-knit-layer-set.jpg",
    founder: "Luna Moretti",
    collection: "THE SOFT EDIT",
    name: "The Cloud-Knit Layer Set",
    number: "15 · 02",
  },
  {
    image: "assets/gallery/luna-taupe-satin-lounge-set-hd.jpg",
    founder: "Luna Moretti",
    collection: "THE SOFT EDIT",
    name: "The Taupe Satin Lounge Set",
    number: "15 · 03",
  },
  {
    image: "assets/gallery/luna-weekend-denim-look-hd.jpg",
    founder: "Luna Moretti",
    collection: "THE EVERYDAY EDIT",
    name: "The Weekend Denim Look",
    number: "15 · 04",
  },
  {
    image: "assets/gallery/luna-midnight-satin-gown-hd.jpg",
    founder: "Luna Moretti",
    collection: "THE EVENING EDIT",
    name: "The Midnight Satin Gown",
    number: "15 · 05",
  },
  {
    image: "assets/gallery/luna-champagne-satin-evening-dress.jpg",
    founder: "Luna Moretti",
    collection: "THE EVENING EDIT",
    name: "The Champagne Satin Evening Dress",
    number: "15 · 06",
  },
  {
    image: "assets/gallery/luna-ivory-tailored-suit.jpg",
    founder: "Luna Moretti",
    collection: "THE EVERYDAY EDIT",
    name: "The Ivory Tailored Suit",
    number: "15 · 07",
  },
  {
    image: "assets/gallery/luna-high-neck-ivory-trouser-set.jpg",
    founder: "Luna Moretti",
    collection: "THE EVERYDAY EDIT",
    name: "The High-Neck Ivory Trouser Set",
    number: "15 · 08",
  },
  {
    image: "assets/gallery/luna-beige-trench-tailored-look.jpg",
    founder: "Luna Moretti",
    collection: "THE EVERYDAY EDIT",
    name: "The Beige Trench Tailored Look",
    number: "15 · 09",
  },
  {
    image: "assets/gallery/victoria-ivory-executive-suit.jpg",
    founder: "Victoria Mendez",
    collection: "THE TAILORED EDIT",
    name: "The Ivory Executive Suit",
    number: "16 · 01",
  },
  {
    image: "assets/gallery/victoria-cloud-ribbed-lounge-set.jpg",
    founder: "Victoria Mendez",
    collection: "THE SOFT EDIT",
    name: "The Cloud Ribbed Lounge Set",
    number: "16 · 02",
  },
  {
    image: "assets/gallery/victoria-off-shoulder-denim-look.jpg",
    founder: "Victoria Mendez",
    collection: "THE EVERYDAY EDIT",
    name: "The Off-Shoulder Denim Look",
    number: "16 · 03",
  },
  {
    image: "assets/gallery/victoria-soft-neutral-knit-set.jpg",
    founder: "Victoria Mendez",
    collection: "THE EVERYDAY EDIT",
    name: "The Soft-Neutral Knit Set",
    number: "16 · 04",
  },
  {
    image: "assets/gallery/victoria-ivory-knit-tailored-set.jpg",
    founder: "Victoria Mendez",
    collection: "THE TAILORED EDIT",
    name: "The Ivory Knit-Tailored Set",
    number: "16 · 05",
  },
  {
    image: "assets/gallery/victoria-champagne-halter-gown.jpg",
    founder: "Victoria Mendez",
    collection: "THE EVENING EDIT",
    name: "The Champagne Halter Gown",
    number: "16 · 06",
  },
  {
    image: "assets/gallery/victoria-midnight-satin-slip-gown.jpg",
    founder: "Victoria Mendez",
    collection: "THE EVENING EDIT",
    name: "The Midnight Satin Slip Gown",
    number: "16 · 07",
  },
  {
    image: "assets/gallery/victoria-ivory-trench-ensemble.jpg",
    founder: "Victoria Mendez",
    collection: "THE TAILORED EDIT",
    name: "The Ivory Trench Ensemble",
    number: "16 · 08",
  },
  {
    image: "assets/gallery/victoria-champagne-blouse-black-trousers.jpg",
    founder: "Victoria Mendez",
    collection: "THE EVENING EDIT",
    name: "The Champagne Blouse & Black Trousers",
    number: "16 · 09",
  },
  {
    image: "assets/gallery/beyza-taupe-knit-trouser-look.jpg",
    founder: "Beyza Keskinci",
    collection: "THE EVERYDAY EDIT",
    name: "The Taupe Knit & Trouser Set",
    number: "17 · 01",
  },
  {
    image: "assets/gallery/beyza-ivory-cardigan-trouser-set.jpg",
    founder: "Beyza Keskinci",
    collection: "THE SOFT EDIT",
    name: "The Ivory Cardigan Trouser Set",
    number: "17 · 02",
  },
  {
    image: "assets/gallery/beyza-ivory-longline-coat-look.jpg",
    founder: "Beyza Keskinci",
    collection: "THE TAILORED EDIT",
    name: "The Ivory Longline Coat",
    number: "17 · 03",
  },
  {
    image: "assets/gallery/beyza-taupe-longline-coat-set.jpg",
    founder: "Beyza Keskinci",
    collection: "THE TAILORED EDIT",
    name: "The Taupe Longline Coat Set",
    number: "17 · 04",
  },
  {
    image: "assets/gallery/beyza-champagne-satin-occasion-gown.jpg",
    founder: "Beyza Keskinci",
    collection: "THE OCCASION EDIT",
    name: "The Champagne Satin Occasion Gown",
    number: "17 · 05",
  },
  {
    image: "assets/gallery/beyza-weekend-denim-jacket-look.jpg",
    founder: "Beyza Keskinci",
    collection: "THE EVERYDAY EDIT",
    name: "The Weekend Denim Jacket Look",
    number: "17 · 06",
  },
  {
    image: "assets/gallery/beyza-espresso-tailored-suit.jpg",
    founder: "Beyza Keskinci",
    collection: "THE TAILORED EDIT",
    name: "The Espresso Tailored Suit",
    number: "17 · 07",
  },
);

const productDetails = {
  "The Ivory Tie-Neck Set": { price: 135, description: "An airy ivory blouse and softly tailored trousers, finished with a graceful tie neckline for understated polish." },
  "The Cloud-Knit Layer Set": { price: 115, description: "A relaxed knit layer and matching soft separates create an easy, tactile look for slower days." },
  "The Taupe Satin Lounge Set": { price: 95, description: "A fluid taupe satin set with delicate lace details, made for a quietly elevated evening in." },
  "The Weekend Denim Look": { price: 150, description: "Relaxed blue denim and warm chocolate layers give this off-duty look a confident city feel." },
  "The Midnight Satin Gown": { price: 180, description: "A striking black satin gown with a fluid silhouette, made for an elegant evening out." },
  "The Champagne Satin Evening Dress": { price: 195, description: "A luminous champagne satin gown with graceful draping, designed for memorable evenings." },
  "The Ivory Tailored Suit": { price: 240, description: "A beautifully composed ivory blazer and trouser suit for polished, modern dressing." },
  "The High-Neck Ivory Trouser Set": { price: 150, description: "A soft high-neck blouse and flowing ivory trousers create an effortlessly refined silhouette." },
  "The Beige Trench Tailored Look": { price: 275, description: "A fluid beige trench layered over tonal tailoring brings timeless polish to the city." },
  "The Ivory Executive Suit": { price: 240, description: "A softly structured ivory blazer and wide-leg trousers bring quiet confidence to modern tailoring." },
  "The Cloud Ribbed Lounge Set": { price: 110, description: "A ribbed knit top and relaxed trousers make this creamy lounge set an easy choice for slower days." },
  "The Off-Shoulder Denim Look": { price: 145, description: "An easy off-shoulder knit and relaxed blue denim create a polished take on casual dressing." },
  "The Soft-Neutral Knit Set": { price: 130, description: "A fine neutral knit paired with fluid ivory trousers makes a graceful, everyday combination." },
  "The Ivory Knit-Tailored Set": { price: 145, description: "A fitted high-neck knit and tailored ivory trousers balance softness with a clean, considered line." },
  "The Champagne Halter Gown": { price: 195, description: "A luminous champagne halter gown drapes elegantly for celebrations and evenings out." },
  "The Midnight Satin Slip Gown": { price: 180, description: "A sleek black satin gown with a fluid silhouette brings understated drama after dark." },
  "The Ivory Trench Ensemble": { price: 285, description: "A long ivory trench layered over tonal separates makes a striking, timeless city look." },
  "The Champagne Blouse & Black Trousers": { price: 150, description: "A lustrous champagne blouse and fluid black trousers create an effortless evening-ready pairing." },
  "The Taupe Knit & Trouser Set": { price: 155, description: "A soft ivory knit and flowing taupe trousers make a graceful, polished look for everyday wear." },
  "The Ivory Cardigan Trouser Set": { price: 185, description: "A longline cardigan layers over an ivory knit-look top and tailored trousers in a tonal outfit concept." },
  "The Ivory Longline Coat": { price: 295, description: "A softly structured longline coat brings timeless polish to a light, tonal outfit." },
  "The Taupe Longline Coat Set": { price: 295, description: "A warm taupe coat and fluid trousers create an elegant layered silhouette with a modern finish." },
  "The Champagne Satin Occasion Gown": { price: 225, description: "A luminous champagne satin gown falls in fluid folds for an occasion-ready statement." },
  "The Weekend Denim Jacket Look": { price: 175, description: "A relaxed brown jacket and pale wide-leg denim make an effortless, city-ready pairing." },
  "The Espresso Tailored Suit": { price: 245, description: "Rich espresso tailoring pairs a softly structured blazer with fluid trousers for confident dressing." },
  "The City-Cream Trouser Set": { price: 175, description: "A sunlit cream blazer and flowing trousers create a polished city look with an easy, contemporary feel." },
  "The Cloud-Knit Lounge Set": { price: 110, description: "A tactile knit and relaxed matching layers bring a soft, considered finish to slow days at home." },
  "The Rose-Stripe Pajama Set": { price: 85, description: "A delicate rose stripe and relaxed pajama silhouette make unwinding feel quietly special." },
  "The Ivory Linen Set": { price: 115, description: "An ivory two-piece concept with a linen-look texture and clean, relaxed lines." },
  "The Sage Linen Set": { price: 120, description: "A sage two-piece concept with a linen-look texture and a coordinated silhouette." },
  "The Ivory Tailored Look": { price: 190, description: "A crisp ivory silhouette with considered tailoring for a fresh, quietly confident finish." },
  "The Emerald Tailored Suit": { price: 245, description: "Rich emerald color and confident structure give this modern suit a memorable, elegant presence." },
  "The Ivory Power Suit": { price: 230, description: "A light, refined take on power dressing, shaped with a clean line and softly defined structure." },
  "The Chocolate Longline Blazer": { price: 165, description: "A longline chocolate blazer brings depth and graceful structure to a versatile wardrobe layer." },
  "The Olive Trench Ensemble": { price: 260, description: "A modern olive trench look with a fluid finish, designed to move easily between seasons." },
  "The Taupe Tailored Set": { price: 185, description: "Soft taupe tailoring balances a composed silhouette with the ease of a set made to wear together." },
  "The Chocolate Blazer Co-ord": { price: 175, description: "A tonal chocolate co-ord with an easy, pulled-together shape and understated polish." },
  "The Rosewater Occasion Abaya": { price: 190, description: "A graceful rosewater abaya with fluid draping and an occasion-ready sense of softness." },
  "The Sandstone Drape Abaya": { price: 210, description: "Sculptural sandstone draping creates an elegant, modest silhouette with movement in every step." },
  "The Espresso Evening Abaya": { price: 230, description: "Deep espresso tones and a sweeping line bring quiet drama to this refined evening abaya." },
  "The Mocha Belted Abaya": { price: 215, description: "A softly defined waist and rich mocha palette lend this modest look a beautifully balanced shape." },
  "The Champagne Occasion Abaya": { price: 225, description: "Luminous champagne color and graceful coverage make this a considered choice for special moments." },
  "The Espresso Trench Look": { price: 255, description: "A refined espresso layer with a long, clean line for a confident city-ready finish." },
  "The Stone Tailored Look": { price: 185, description: "Soft stone tailoring brings a modern, understated ease to an elegant, covered silhouette." },
  "The Sculpted Wrap Blouse": { price: 65, description: "A sculpted wrap shape gives this versatile blouse a flattering line and a little everyday distinction." },
  "The Heritage Blazer": { price: 165, description: "A timeless blazer with considered proportions, made to anchor both tailored and relaxed looks." },
  "The After-Hours Power Suit": { price: 245, description: "Evening-ready tailoring pairs a sharp silhouette with a confident, modern finish." },
};

const currency = window.VeloraShopping.currency;
const productKey = (look) => `${look.name}:${look.image}`;
const colorPalette = [
  { name: "Ivory", hex: "#e8e2d6", tokens: ["ivory", "cream", "white", "pearl", "cloud"] },
  { name: "Black", hex: "#252321", tokens: ["black", "midnight"] },
  { name: "Sage", hex: "#9b9d83", tokens: ["sage", "olive", "emerald", "green"] },
  { name: "Blue", hex: "#7b93b5", tokens: ["blue", "denim"] },
  { name: "Taupe", hex: "#9c897d", tokens: ["taupe", "beige", "sandstone", "stone", "mocha", "chocolate", "espresso", "cocoa", "brown"] },
  { name: "Rose", hex: "#b87978", tokens: ["rosewater", "rose", "merlot", "burgundy"] },
  { name: "Lavender", hex: "#aaa0bd", tokens: ["lilac", "lavender"] },
  { name: "Champagne", hex: "#d8c6a5", tokens: ["champagne"] },
  { name: "Grey", hex: "#999894", tokens: ["grey", "gray"] },
];
const colorAlternates = {
  Ivory: ["Ivory", "Champagne", "Black"],
  Black: ["Black", "Ivory", "Champagne"],
  Sage: ["Sage", "Ivory", "Black"],
  Blue: ["Blue", "Ivory", "Black"],
  Taupe: ["Taupe", "Ivory", "Black"],
  Rose: ["Rose", "Ivory", "Black"],
  Lavender: ["Lavender", "Ivory", "Black"],
  Champagne: ["Champagne", "Ivory", "Black"],
  Grey: ["Grey", "Ivory", "Black"],
};
const productColorOverrides = {
  "The Ivory Executive Suit": ["Red", "Blue", "Grey", "Beige"],
};
const colorSwatches = {
  Red: "#9f3c3c",
  Beige: "#cdbda7",
};

function getProductColors(look) {
  const images = window.veloraColorImages?.[look.color_key || look.image];
  const primary = {
    name: look.base_color && look.base_color !== "Original" ? look.base_color : images?.[0]?.name || "Original",
    hex: look.base_color && look.base_color !== "Original" ? look.color_hex : images?.[0]?.hex || look.color_hex || "#d1c8bd",
    image: look.image,
    poses: images?.[0]?.poses || [],
  };
  if (look.managed || images || look.color_variants?.length) {
    const managedNames = new Set((look.color_variants || []).map((color) => color.name.toLocaleLowerCase()));
    const alternates = [
      ...(images || []).slice(1).filter((color) => !managedNames.has(color.name.toLocaleLowerCase())),
      ...(look.color_variants || []),
    ];
    const seen = new Set([primary.name.toLocaleLowerCase()]);
    return [
      primary,
      ...alternates.filter((color) => {
        const key = color.name.toLocaleLowerCase();
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      }),
    ];
  }
  const override = productColorOverrides[look.name];
  if (override) {
    return override.map((name) => ({
      name,
      hex: colorPalette.find((color) => color.name === name)?.hex ?? colorSwatches[name],
    }));
  }

  const text = `${look.name} ${look.description ?? ""}`.toLowerCase();
  const matchedColor = colorPalette.find((color) =>
    color.tokens.some((token) => new RegExp(`(?:^|[^a-z])${token}(?:$|[^a-z])`).test(text)),
  );
  const names = colorAlternates[matchedColor?.name ?? "Ivory"];
  return names.map((name) => ({
    name,
    hex: colorPalette.find((color) => color.name === name)?.hex ?? "#cfc8bd",
  }));
}

const founderOrder = [...new Set([
  "Victoria Mendez",
  "Luna Moretti",
  "Derya Kasal",
  "Beyza Keskinci",
  ...individualLooks.map((look) => look.founder),
])];
const looksByFounder = new Map(
  founderOrder.map((founder) => [founder, individualLooks.filter((look) => look.founder === founder)]),
);
const mixedLooks = [];
const longestFounderCollection = Math.max(...[...looksByFounder.values()].map((looks) => looks.length));

for (let index = 0; index < longestFounderCollection; index += 1) {
  founderOrder.forEach((founder) => {
    const look = looksByFounder.get(founder)[index];
    if (look) mixedLooks.push(look);
  });
}

individualLooks.splice(0, individualLooks.length, ...mixedLooks);

individualLooks.forEach((look) => {
  const details = productDetails[look.name];
  if (!details) throw new Error(`Missing product details for ${look.name}`);
  Object.assign(look, details, {
    key: productKey(look),
    colors: getProductColors({ ...look, ...details }),
    sizes: ["XS", "S", "M", "L"],
  });
});

const lookByKey = new Map(individualLooks.map((look) => [look.key, look]));
const selectedVariants = new Map();
const productKeyAliases = new Map();
let galleryImageSequence = 0;
const defaultSize = "M";

function getVariantSelection(look) {
  const selected = selectedVariants.get(look.key);
  if (selected && look.colors.some((color) => color.name === selected.color) && look.sizes.includes(selected.size)) return selected;
  const initial = { color: look.colors[0].name, size: look.sizes.includes(defaultSize) ? defaultSize : look.sizes[0] };
  selectedVariants.set(look.key, initial);
  return initial;
}

function getProductImage(look, color = getVariantSelection(look).color) {
  return look.colors.find((variant) => variant.name === color)?.image ?? look.image;
}

function setProductImage(image, look, color = getVariantSelection(look).color) {
  image.dataset.variantProductKey = look.key;
  setProductPhotoSource(image, getProductImage(look, color));
  const garmentOnly = look.colors.find((variant) => variant.name === color)?.garmentOnly;
  image.alt = garmentOnly
    ? `${look.name} — ${color}, garment-only preview`
    : `${look.name} — ${color}, modeled by ${look.founder}`;
}

function setProductPhotoSource(image, source) {
  image.dataset.originalSrc = source;
  const responsive = !image.classList.contains("product-dialog-image") && window.VeloraResponsiveImages?.[source];
  if (responsive) {
    image.srcset = responsive.srcset;
    image.sizes ||= "(max-width: 650px) 100vw, (max-width: 1100px) 33vw, 25vw";
    image.src = responsive.src;
    image.width = responsive.width;
    image.height = responsive.height;
  } else {
    image.removeAttribute("srcset");
    image.src = source;
  }
}

function updateProductColor(look) {
  const { color } = getVariantSelection(look);
  document.querySelectorAll("img[data-variant-product-key]").forEach((image) => {
    if (image.dataset.variantProductKey === look.key && !image.closest(".shop-line-item")) {
      setProductImage(image, look, color);
    }
  });
  document.querySelectorAll(".product-options").forEach((group) => {
    if (group.dataset.productKey !== look.key) return;
    group.querySelector(".product-color-label").textContent = `Color: ${color}`;
    group.closest(".look-tile")?.querySelectorAll(".look-photo-trigger, .look-quick-view, .look-tile-caption a").forEach((link) => {
      link.href = productPageUrl(look);
    });
  });
  document.querySelectorAll("[data-gallery-product-key]").forEach((gallery) => {
    if (gallery.dataset.galleryProductKey === look.key) attachProductGallery(gallery, look);
  });
}

function galleryImages(look) {
  const selection = getVariantSelection(look);
  const color = look.colors.find((variant) => variant.name === selection.color);
  const first = color?.image || getProductImage(look);
  const primaryColor = selection.color === look.colors[0].name;
  return [...new Set([
    first,
    ...(color?.poses || []),
    ...(primaryColor ? look.images || [look.image] : []),
  ])];
}

function attachProductGallery(container, look) {
  const image = container.querySelector("img");
  if (!image) return;
  container.classList.add("product-gallery");
  container.dataset.galleryProductKey = look.key;
  container.dataset.currentGalleryIndex = "0";
  image.dataset.galleryMain = "";
  image.id ||= `gallery-image-${++galleryImageSequence}`;
  container.querySelectorAll(".product-gallery-controls, .product-gallery-thumbnails, .product-gallery-count").forEach((node) => node.remove());
  const photos = galleryImages(look);
  if (photos.length < 2) return;
  const controls = document.createElement("div");
  controls.className = "product-gallery-controls";
  for (const [action, text, label] of [["previous", "‹", "Previous photo"], ["next", "›", "Next photo"]]) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "product-gallery-arrow";
    button.dataset.galleryAction = action;
    button.textContent = text;
    button.setAttribute("aria-label", `${label} of ${look.name}`);
    button.setAttribute("aria-controls", image.id);
    controls.append(button);
  }
  const count = document.createElement("span");
  count.className = "product-gallery-count";
  count.setAttribute("aria-live", "polite");
  count.textContent = `1 / ${photos.length}`;
  const thumbnails = document.createElement("div");
  thumbnails.className = "product-gallery-thumbnails";
  thumbnails.setAttribute("role", "group");
  thumbnails.setAttribute("aria-label", `Photos of ${look.name}`);
  photos.forEach((src, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.galleryIndex = String(index);
    button.setAttribute("aria-label", `Show photo ${index + 1} of ${look.name}`);
    button.setAttribute("aria-pressed", String(index === 0));
    button.setAttribute("aria-controls", image.id);
    const thumbnail = document.createElement("img");
    thumbnail.src = src;
    thumbnail.alt = "";
    thumbnail.loading = "lazy";
    thumbnail.decoding = "async";
    button.append(thumbnail);
    thumbnails.append(button);
  });
  container.append(controls, count, thumbnails);
}

function selectGalleryPhoto(container, look, index) {
  const photos = galleryImages(look);
  const current = (index + photos.length) % photos.length;
  const image = container.querySelector("[data-gallery-main]");
  if (!image) return;
  container.dataset.currentGalleryIndex = String(current);
  setProductPhotoSource(image, photos[current]);
  image.alt = `${look.name} — ${getVariantSelection(look).color}, photo ${current + 1} of ${photos.length}`;
  const count = container.querySelector(".product-gallery-count");
  if (count) count.textContent = `${current + 1} / ${photos.length}`;
  container.querySelectorAll("button[data-gallery-index]").forEach((button) => button.setAttribute("aria-pressed", String(Number(button.dataset.galleryIndex) === current)));
}

function variantAvailableStock(look, selection = getVariantSelection(look)) {
  if (look.variant_stock && Object.keys(look.variant_stock).length) return look.variant_stock[selection.color.toLowerCase() + "|" + selection.size.toLowerCase()] || 0;
  return look.stock;
}

function configurePurchaseButton(button, look) {
  const soldOut = variantAvailableStock(look) === 0;
  button.disabled = soldOut;
  button.textContent = soldOut ? "Sold out" : "Add to bag";
}

function canAddToBag(look, selection = getVariantSelection(look)) {
  const stock = variantAvailableStock(look, selection);
  if (stock === null || stock === undefined) return true;
  const byVariant = look.variant_stock && Object.keys(look.variant_stock).length;
  const quantity = [...shoppingCart].reduce((total, [key, count]) => {
    const item = getCartItem(key);
    const itemSelection = item && { color: item.color || getVariantSelection(item.look).color, size: item.size || getVariantSelection(item.look).size };
    const matchesVariant = itemSelection && itemSelection.color.toLowerCase() === selection.color.toLowerCase() && itemSelection.size.toLowerCase() === selection.size.toLowerCase();
    return total + (item?.look.key === look.key && (!byVariant || matchesVariant) ? count : 0);
  }, 0);
  if (quantity < stock) return true;
  showShoppingNotice(stock === 0 ? "This size and color is currently sold out." : `Only ${stock} of this selection can be added to your bag.`, "neutral");
  return false;
}

function createProductOptions(look, { photoPreviews = false } = {}) {
  const selection = getVariantSelection(look);
  const options = document.createElement("div");
  options.className = "product-options";
  options.dataset.productKey = look.key;

  const colorGroup = document.createElement("div");
  colorGroup.className = "product-option-group";
  const colorLabel = document.createElement("span");
  colorLabel.className = "product-option-label product-color-label";
  colorLabel.textContent = `Color: ${selection.color}`;
  const swatches = document.createElement("div");
  swatches.className = "product-color-options";
  swatches.setAttribute("role", "group");
  swatches.setAttribute("aria-label", `Color options for ${look.name}`);
  if (photoPreviews) swatches.classList.add("has-photo-previews");
  look.colors.forEach((color) => {
    const button = document.createElement("button");
    button.className = "product-option product-color-option";
    button.type = "button";
    button.dataset.optionType = "color";
    button.dataset.optionValue = color.name;
    button.style.setProperty("--swatch-color", color.hex);
    const colorName = color.image === look.image ? `${color.name} (original photo)` : color.name;
    button.title = colorName;
    button.setAttribute("aria-label", colorName);
    button.setAttribute("aria-pressed", String(selection.color === color.name));
    if (photoPreviews) {
      button.classList.add("product-color-preview");
      const preview = document.createElement("img");
      setProductPhotoSource(preview, color.image || look.image);
      preview.alt = "";
      preview.loading = "lazy";
      preview.decoding = "async";
      preview.sizes = "72px";
      const label = document.createElement("span");
      label.textContent = color.name;
      button.append(preview, label);
    }
    swatches.append(button);
  });
  colorGroup.append(colorLabel, swatches);

  const sizeGroup = document.createElement("div");
  sizeGroup.className = "product-option-group";
  const sizeLabel = document.createElement("span");
  sizeLabel.className = "product-option-label";
  sizeLabel.textContent = "Size";
  const sizes = document.createElement("div");
  sizes.className = "product-size-options";
  sizes.setAttribute("role", "group");
  sizes.setAttribute("aria-label", `Size options for ${look.name}`);
  look.sizes.forEach((size) => {
    const button = document.createElement("button");
    button.className = "product-option product-size-option";
    button.type = "button";
    button.dataset.optionType = "size";
    button.dataset.optionValue = size;
    button.textContent = size;
    button.setAttribute("aria-pressed", String(selection.size === size));
    sizes.append(button);
  });
  sizeGroup.append(sizeLabel, sizes);
  const sizeHelp = document.createElement("button");
  sizeHelp.type = "button";
  sizeHelp.className = "product-size-help";
  sizeHelp.dataset.productKey = look.key;
  sizeHelp.dataset.fitFocus = "true";
  sizeHelp.textContent = "Size & fit guide";
  sizeHelp.setAttribute("aria-haspopup", "dialog");
  sizeGroup.append(sizeHelp);

  const note = document.createElement("p");
  note.className = "product-options-note";
  note.textContent = look.managed && !window.veloraColorImages?.[look.color_key]
    ? (look.stock === 0 ? "Currently sold out" : look.stock === null ? "Open the product page for details" : "Available in the sizes shown")
    : "AI-created color previews · availability unconfirmed";
  options.append(colorGroup, sizeGroup, note);
  return options;
}

function renderProductInformation(look, showFit = false) {
  const information = document.querySelector(".product-information");
  if (!information) return;
  information.replaceChildren();
  function accordion(title, paragraphs, open = false) {
    const details = document.createElement("details");
    details.className = "product-accordion";
    details.open = open;
    const summary = document.createElement("summary");
    summary.textContent = title;
    const content = document.createElement("div");
    content.className = "product-accordion-content";
    for (const text of paragraphs) {
      const paragraph = document.createElement("p");
      paragraph.textContent = text;
      content.append(paragraph);
    }
    details.append(summary, content);
    information.append(details);
    return { details, summary, content };
  }
  const fit = accordion("Size & fit", [
    look.fit || "Product-specific fit and garment measurements have not been supplied yet.",
    ...(look.size_guide ? [look.size_guide] : ["Size labels are illustrative in this concept collection. A size label alone cannot confirm your fit."]),
  ], showFit);
  fit.details.dataset.sizeFit = "";
  const measurements = document.createElement("ul");
  for (const text of [
    "Bust: measure around the fullest part, keeping the tape level.",
    "Waist: measure around your natural waist without pulling the tape tight.",
    "Hips: measure around the fullest part of your hips.",
    "For trousers, also measure the inside leg from crotch to your preferred hem.",
  ]) {
    const item = document.createElement("li");
    item.textContent = text;
    measurements.append(item);
  }
  fit.content.append(measurements);
  const compare = document.createElement("p");
  compare.textContent = "Use a flexible tape and compare your measurements with the product's own chart when available. Body measurements and garment measurements are different; check which a guide uses.";
  fit.content.append(compare);
  const specifications = accordion("Fabric & product details", []);
  const list = document.createElement("dl");
  for (const [label, value] of [["Material / composition", look.material], ["Fabric weight", look.fabric_weight], ["Country of manufacture", look.origin]]) {
    const term = document.createElement("dt");
    term.textContent = label;
    const definition = document.createElement("dd");
    definition.textContent = value || "Not supplied yet";
    list.append(term, definition);
  }
  specifications.content.append(list);
  const conceptNote = document.createElement("p");
  conceptNote.textContent = "This is a concept collection with AI-created imagery. Fabric names in product titles describe the visual style; consult supplied specifications for composition.";
  specifications.content.append(conceptNote);
  const shopping = accordion("Delivery & returns", ["The collection is currently a showcase. Adding a piece to your preview bag does not place an order. Payment, delivery and returns are not yet available."]);
  const links = document.createElement("nav");
  links.className = "shopping-help-links";
  links.setAttribute("aria-label", "Product shopping information");
  for (const [href, text] of [["shopping-info.html", "Shopping information"], ["refund-policy.html", "Return information"]]) {
    const link = document.createElement("a");
    link.href = href;
    link.textContent = text;
    links.append(link);
  }
  shopping.content.append(links);
  if (showFit) requestAnimationFrame(() => { fit.summary.focus(); fit.details.scrollIntoView({ block: "nearest" }); });
}

function createCartKey(look, selection = getVariantSelection(look)) {
  return `${look.key}::${encodeURIComponent(selection.color)}::${encodeURIComponent(selection.size)}`;
}

function getCartItem(cartKey) {
  const look = lookByKey.get(cartKey);
  if (look) return look.published === false ? null : { look, color: null, size: null };
  const sizeSeparator = cartKey.lastIndexOf("::");
  const colorSeparator = sizeSeparator > -1 ? cartKey.lastIndexOf("::", sizeSeparator - 1) : -1;
  if (colorSeparator < 0 || sizeSeparator < 0) return null;
  const product = lookByKey.get(cartKey.slice(0, colorSeparator));
  if (!product || product.published === false) return null;
  try {
    return {
      look: product,
      color: decodeURIComponent(cartKey.slice(colorSeparator + 2, sizeSeparator)),
      size: decodeURIComponent(cartKey.slice(sizeSeparator + 2)),
    };
  } catch (error) {
    console.error("Could not read a saved product variant.", error);
    return null;
  }
}

function readShoppingState() {
  const state = window.VeloraShopping.read();
  shoppingStateReadError = state.readError;
  return state;
}

let shoppingStateReadError = false;
const { wishlist: savedLooks, cart: shoppingCart } = readShoppingState();

function persistShoppingState() {
  return window.VeloraShopping.save({ wishlist: savedLooks, cart: shoppingCart });
}

const founderRecommendations = [
  { founder: "Beyza Keskinci", name: "The Sandstone Drape Abaya", note: "Graceful modestwear" },
  { founder: "Derya Kasal", name: "The Emerald Tailored Suit", note: "A confident color story" },
  { founder: "Luna Moretti", name: "The Cloud-Knit Layer Set", note: "Soft layers, thoughtfully styled" },
  { founder: "Victoria Mendez", name: "The Midnight Satin Slip Gown", note: "A modern after-hours classic" },
];
founderRecommendations.forEach((recommendation) => {
  const look = individualLooks.find((item) => item.founder === recommendation.founder && item.name === recommendation.name);
  recommendation.image = look?.image;
  recommendation.legacyKey = look?.key;
});

const recommendationsGrid = document.querySelector("#founder-recommendations");
function productPageUrl(look) {
  const selection = getVariantSelection(look);
  const params = new URLSearchParams();
  if (look.id) {
    params.set("id", look.id);
  } else {
    params.set("preview", JSON.stringify({
      key: look.key,
      name: look.name,
      image: look.image,
      images: look.images,
      founder: look.founder,
      collection: look.collection,
      price: look.price,
      description: look.description,
      sizes: look.sizes,
      colors: look.colors,
      stock: look.stock,
      variant_stock: look.variant_stock,
      sku: look.sku,
      base_color: look.base_color,
      color_hex: look.color_hex,
      color_key: look.color_key,
      color_variants: look.color_variants,
      fit: look.fit,
      material: look.material,
      fabric_weight: look.fabric_weight,
      origin: look.origin,
      size_guide: look.size_guide,
      discount_tag: look.discount_tag,
      managed: look.managed,
    }));
  }
  params.set("color", selection.color);
  params.set("size", selection.size);
  return `product.html?${params}`;
}

function renderRecommendations() {
  if (!recommendationsGrid) return;
  const recommendationCards = founderRecommendations.map((recommendation) => {
    const look = individualLooks.find(
      (item) => item.managed ? item.legacy_key === recommendation.legacyKey : item.image === recommendation.image,
    );
    if (!look || look.published === false) return null;

    const card = document.createElement("article");
    card.className = "recommendation-card";
    if (look.id) card.dataset.productId = look.id;
    const media = document.createElement("div");
    media.className = "recommendation-media";

    const imageLink = document.createElement("a");
    imageLink.className = "recommendation-image look-photo-trigger";
    imageLink.href = productPageUrl(look);
    imageLink.setAttribute("aria-label", `View product: ${look.name}, chosen by ${look.founder}`);

    const image = document.createElement("img");
    setProductImage(image, look);
    image.loading = "lazy";
    image.decoding = "async";

    const founderLabel = document.createElement("span");
    founderLabel.className = "recommendation-founder";
    founderLabel.textContent = look.founder;
    imageLink.append(image, founderLabel);

    const copy = document.createElement("div");
    copy.className = "recommendation-copy";
    const note = document.createElement("p");
    note.textContent = recommendation.note;
    const title = document.createElement("h3");
    const titleLink = document.createElement("a");
    titleLink.href = productPageUrl(look);
    titleLink.textContent = look.name;
    title.append(titleLink);
    const description = document.createElement("p");
    description.className = "recommendation-description";
    description.textContent = look.description;
    const price = document.createElement("strong");
    price.className = "product-price";
    price.textContent = currency.format(look.price);
    copy.append(note, title, description, price, createProductOptions(look));

    const actions = document.createElement("div");
    actions.className = "product-card-actions";

    const quickView = document.createElement("a");
    quickView.className = "look-quick-view";
    quickView.href = productPageUrl(look);
    quickView.textContent = "Discover the look";

    const saveButton = document.createElement("button");
    saveButton.className = "save-look";
    saveButton.type = "button";
    saveButton.dataset.image = look.image;
    saveButton.dataset.name = look.name;
    saveButton.dataset.productKey = look.key;
    const isSaved = savedLooks.has(look.key);
    saveButton.setAttribute("aria-pressed", String(isSaved));
    saveButton.textContent = isSaved ? "♥ Saved" : "♡ Wishlist";

    const addButton = document.createElement("button");
    addButton.className = "shop-primary add-to-bag";
    addButton.type = "button";
    addButton.dataset.productKey = look.key;
    configurePurchaseButton(addButton, look);

    actions.append(quickView, saveButton, addButton);
    media.append(imageLink);
    attachProductGallery(media, look);
    card.append(media, copy, actions);
    return card;
  });

  recommendationsGrid.replaceChildren(...recommendationCards.filter(Boolean));
  const section = recommendationsGrid.closest(".founder-picks");
  if (section) section.hidden = !recommendationsGrid.childElementCount;
}
renderRecommendations();

const looksGrid = document.querySelector("#looks-grid");
const lookFilters = document.querySelectorAll(".look-filters");
const showMoreLooks = document.querySelector("#show-more-looks");
const looksCount = document.querySelector("#looks-count");
const looksPerPage = 15;
let activeFounder = "all";
let activeCategory = "all";
let visibleLookCount = looksPerPage;
const collectionFields = Object.fromEntries(["search", "size", "color", "price", "occasion", "sort"].map((key) => [key, document.querySelector(`#collection-${key}`)]));
const collectionFilterStatus = document.querySelector("#collection-filter-status");
const refinementCount = document.querySelector("#refinement-count");
const occasionCollections = {
  everyday: ["THE EVERYDAY EDIT", "THE SOFT EDIT", "THE MODEST EDIT"],
  work: ["THE POLISHED EDIT", "THE TAILORED EDIT"],
  evening: ["THE AFTER-HOURS EDIT", "THE EVENING EDIT", "THE OCCASION EDIT"],
};

function collectionValue(key) {
  return collectionFields[key]?.value || (key === "search" ? "" : key === "sort" ? "featured" : "all");
}

function renderFacetOptions() {
  for (const [key, values] of [
    ["size", individualLooks.flatMap((look) => look.sizes || [])],
    ["color", individualLooks.flatMap((look) => (look.colors || []).map((color) => color.name))],
  ]) {
    const field = collectionFields[key];
    if (!field) continue;
    const selected = field.value;
    const unique = [...new Map(values.map((value) => [value.toLocaleLowerCase(), value])).values()];
    const sizeOrder = ["XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL"];
    unique.sort((a, b) => key === "size" && sizeOrder.includes(a) && sizeOrder.includes(b)
      ? sizeOrder.indexOf(a) - sizeOrder.indexOf(b) : a.localeCompare(b, "en", { numeric: true }));
    field.replaceChildren(new Option(key === "size" ? "All sizes" : "All colors", "all"), ...unique.map((value) => new Option(value, value)));
    field.value = unique.includes(selected) ? selected : "all";
  }
}

function resetCollectionFilters() {
  for (const [key, field] of Object.entries(collectionFields)) {
    if (field) field.value = key === "search" ? "" : key === "sort" ? "featured" : "all";
  }
  activeCategory = "all";
  activeFounder = "all";
  visibleLookCount = looksPerPage;
  renderCatalogFilters();
  renderLooks();
}

for (const [key, field] of Object.entries(collectionFields)) {
  field?.addEventListener(key === "search" ? "input" : "change", () => {
    visibleLookCount = looksPerPage;
    renderLooks();
  });
}
document.querySelector("#clear-collection-filters")?.addEventListener("click", resetCollectionFilters);
renderFacetOptions();

function renderLooks() {
  if (!(looksGrid instanceof HTMLElement) || !(showMoreLooks instanceof HTMLButtonElement)) return;

  const search = collectionValue("search").trim().toLocaleLowerCase();
  const size = collectionValue("size");
  const color = collectionValue("color");
  const price = collectionValue("price");
  const occasion = collectionValue("occasion");
  const filteredLooks = individualLooks.filter(
    (look) =>
      look.published !== false &&
      (activeFounder === "all" || look.founder === activeFounder) &&
      (activeCategory === "all" || look.collection === activeCategory) &&
      (!search || [look.name, look.description, look.founder, ...look.colors.map((variant) => variant.name)].join(" ").toLocaleLowerCase().includes(search)) &&
      (size === "all" || look.sizes.includes(size)) &&
      (color === "all" || look.colors.some((variant) => variant.name.toLocaleLowerCase() === color.toLocaleLowerCase())) &&
      (price === "all" || (price === "under-100" && look.price < 100) || (price === "100-200" && look.price >= 100 && look.price <= 200) || (price === "over-200" && look.price > 200)) &&
      (occasion === "all" || occasionCollections[occasion]?.includes(look.collection)),
  );
  const sort = collectionValue("sort");
  if (sort === "price-asc") filteredLooks.sort((a, b) => a.price - b.price);
  if (sort === "price-desc") filteredLooks.sort((a, b) => b.price - a.price);
  if (sort === "name") filteredLooks.sort((a, b) => a.name.localeCompare(b.name));
  const visibleLooks = filteredLooks.slice(0, visibleLookCount);
  const resultText = `Showing ${visibleLooks.length} of ${filteredLooks.length} ${filteredLooks.length === 1 ? "piece" : "pieces"}`;
  if (collectionFilterStatus) collectionFilterStatus.textContent = resultText;
  const filterCount = [search, size !== "all", color !== "all", price !== "all", occasion !== "all", activeFounder !== "all", activeCategory !== "all"].filter(Boolean).length;
  if (refinementCount) refinementCount.textContent = filterCount ? `${filterCount} active` : "";
  if (looksCount instanceof HTMLElement) {
    looksCount.textContent = resultText;
  }

  looksGrid.replaceChildren(
    ...visibleLooks.map((look) => {
      const selection = { ...getVariantSelection(look) };
      if (size !== "all") selection.size = size;
      if (color !== "all") selection.color = look.colors.find((variant) => variant.name.toLocaleLowerCase() === color.toLocaleLowerCase()).name;
      selectedVariants.set(look.key, selection);
      const tile = document.createElement("article");
      tile.className = "look-tile";
      if (look.id) tile.dataset.productId = look.id;
      const imageContainer = document.createElement("div");
      imageContainer.className = "look-tile-image";

      const image = document.createElement("img");
      setProductImage(image, look);
      image.loading = "lazy";
      image.decoding = "async";
      image.sizes = "(max-width: 360px) calc(100vw - 48px), (max-width: 799px) calc((100vw - 60px) / 2), (max-width: 1099px) 30vw, (max-width: 1499px) 23vw, (max-width: 1799px) 18vw, 15vw";
      if (look.number === "02" || look.number.startsWith("17 ·")) image.dataset.fullFrame = "true";

      const number = document.createElement("span");
      number.className = "look-tile-number";
      number.textContent = look.collection.replace(/^THE | EDIT$/g, "");

      const imageQuickView = document.createElement("a");
      imageQuickView.className = "look-photo-trigger";
      imageQuickView.href = productPageUrl(look);
      imageQuickView.setAttribute("aria-label", `View product: ${look.name}, modeled by ${look.founder}`);
      imageQuickView.append(image);

      const caption = document.createElement("div");
      caption.className = "look-tile-caption";
      const founder = document.createElement("strong");
      const titleLink = document.createElement("a");
      titleLink.href = productPageUrl(look);
      titleLink.textContent = look.name;
      founder.append(titleLink);
      const note = document.createElement("span");
      note.textContent = look.founder;
      const capsule = document.createElement("span");
      capsule.className = "look-tile-capsule";
      capsule.textContent = `${look.managed ? look.sku : `LOOK ${look.number}`} · ${look.collection}`;

      const description = document.createElement("p");
      description.className = "look-tile-description";
      description.textContent = look.description;
      const price = document.createElement("strong");
      price.className = "product-price";
      price.textContent = currency.format(look.price);

      const actions = document.createElement("div");
      actions.className = "product-card-actions";

      const quickView = document.createElement("a");
      quickView.className = "look-quick-view";
      quickView.href = productPageUrl(look);
      quickView.textContent = "View product";

      const saveButton = document.createElement("button");
      saveButton.className = "save-look";
      saveButton.type = "button";
      saveButton.dataset.image = look.image;
      saveButton.dataset.name = look.name;
      saveButton.dataset.productKey = look.key;
      saveButton.setAttribute("aria-label", `Save ${look.name}`);
      const isSaved = savedLooks.has(look.key);
      saveButton.setAttribute("aria-pressed", String(isSaved));
      saveButton.setAttribute("aria-label", `${isSaved ? "Remove saved" : "Save"} ${look.name}`);
      saveButton.textContent = isSaved ? "♥ Saved" : "♡ Wishlist";

      const addButton = document.createElement("button");
      addButton.className = "shop-primary add-to-bag";
      addButton.type = "button";
      addButton.dataset.productKey = look.key;
      configurePurchaseButton(addButton, look);

      imageContainer.append(imageQuickView, saveButton);
      attachProductGallery(imageContainer, look);
      actions.append(quickView, addButton);
      caption.append(founder, price, note);
      tile.append(imageContainer, caption, createProductOptions(look, {
        photoPreviews: true,
      }), actions);
      return tile;
    }),
  );

  if (!filteredLooks.length) {
    const empty = document.createElement("div");
    empty.className = "collection-empty";
    const title = document.createElement("h3");
    title.textContent = "A different direction?";
    const note = document.createElement("p");
    note.textContent = "No pieces match this combination. Clear your filters to explore the collection again.";
    const reset = document.createElement("button");
    reset.type = "button";
    reset.className = "shop-secondary";
    reset.textContent = "Clear all filters";
    reset.addEventListener("click", () => { resetCollectionFilters(); document.querySelector("#collection-search")?.focus(); });
    empty.append(title, note, reset);
    looksGrid.append(empty);
  }

  showMoreLooks.hidden = visibleLookCount >= filteredLooks.length;
}

lookFilters.forEach((filterGroup) => {
  filterGroup.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const filter = target.closest(".look-filter");
    if (!(filter instanceof HTMLButtonElement)) return;

    if (filter.hasAttribute("data-founder")) {
      activeFounder = filter.dataset.founder ?? "all";
    } else if (filter.hasAttribute("data-category")) {
      activeCategory = filter.dataset.category ?? "all";
      if (activeCategory === "all") activeFounder = "all";
    } else {
      return;
    }

    visibleLookCount = looksPerPage;
    lookFilters.forEach((group) => {
      const activeAttribute = group.dataset.filterGroup;
      const activeValue = activeAttribute === "founder" ? activeFounder : activeCategory;

      group.querySelectorAll(".look-filter[data-founder], .look-filter[data-category]").forEach((button) => {
        const buttonAttribute = activeAttribute === "founder" ? "data-founder" : "data-category";
        const isActive = button.hasAttribute(buttonAttribute) && button.getAttribute(buttonAttribute) === activeValue;
        button.classList.toggle("is-active", isActive);
        button.setAttribute("aria-pressed", String(isActive));
      });
    });

    renderLooks();
  });
});

showMoreLooks?.addEventListener("click", () => {
  visibleLookCount += looksPerPage;
  renderLooks();
});

const productDialog = document.querySelector("#product-dialog");
const productDialogImage = document.querySelector(".product-dialog-image");
const productDialogTitle = document.querySelector("#product-dialog-title");
const productDialogPrice = document.querySelector(".product-dialog-price");
const productDialogFounder = document.querySelector(".product-dialog-founder");
const productDialogNote = document.querySelector(".product-dialog-note");
const productDialogOptions = document.querySelector(".product-dialog-options");
const productDialogClose = document.querySelector(".product-dialog-close");
const productDialogLink = document.querySelector(".product-dialog-link");
const productDialogAdd = document.querySelector(".product-dialog-add");
const productDialogSave = document.querySelector(".product-dialog-save");
const imageZoomDialog = document.querySelector("#image-zoom-dialog");
const imageZoomViewport = document.querySelector(".image-zoom-viewport");
const imageZoomImage = document.querySelector(".image-zoom-image");
const imageZoomToggle = document.querySelector(".image-zoom-toggle");

document.querySelector(".product-zoom-open")?.addEventListener("click", () => {
  if (!(imageZoomDialog instanceof HTMLDialogElement) || !productDialogImage?.getAttribute("src")) return;
  imageZoomImage.src = productDialogImage.dataset.originalSrc || productDialogImage.src;
  imageZoomImage.alt = productDialogImage.alt;
  document.querySelector("#image-zoom-title").textContent = productDialogTitle.textContent;
  imageZoomViewport.classList.remove("is-zoomed");
  imageZoomToggle.setAttribute("aria-pressed", "false");
  imageZoomToggle.textContent = "Zoom in";
  imageZoomDialog.showModal();
  document.querySelector(".image-zoom-close")?.focus();
  imageZoomViewport.scrollTo(0, 0);
});
imageZoomToggle?.addEventListener("click", () => {
  const zoomed = imageZoomViewport.classList.toggle("is-zoomed");
  imageZoomToggle.setAttribute("aria-pressed", String(zoomed));
  imageZoomToggle.textContent = zoomed ? "Fit photo" : "Zoom in";
  imageZoomViewport.scrollTo(0, 0);
});
document.querySelector(".image-zoom-close")?.addEventListener("click", () => imageZoomDialog.close());
imageZoomDialog?.addEventListener("click", (event) => {
  if (event.target === imageZoomDialog) imageZoomDialog.close();
});
imageZoomDialog?.addEventListener("close", () => {
  imageZoomImage.removeAttribute("src");
  if (productDialog?.open) document.querySelector(".product-zoom-open")?.focus();
});
imageZoomDialog?.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  event.preventDefault();
  event.stopPropagation();
  imageZoomDialog.close();
});
const shopDialog = document.querySelector("#shop-dialog");
const shopDialogTitle = document.querySelector("#shop-dialog-title");
const shopDialogContent = document.querySelector("#shop-dialog-content");
const shopDialogFooter = document.querySelector("#shop-dialog-footer");
const shoppingNotice = document.querySelector("#shopping-notice");
const cartCount = document.querySelector("#cart-count");
const wishlistCount = document.querySelector("#wishlist-count");
let activeShopView = "cart";
let checkoutStage = "bag";
let checkoutError = "";
let shoppingNoticeTimer;
const bagDiscount = { code: "", draft: "", quote: null, fingerprint: "", requestedFingerprint: "", pending: false, generation: 0, checkedAt: 0, message: "", error: false };

function discountCartSnapshot() {
  const products = new Map();
  const signature = [];
  let subtotalCents = 0, unsupported = false;
  for (const [key, quantity] of shoppingCart) {
    const item = getCartItem(key);
    signature.push([key, quantity, item?.look.id || "", item?.look.price ?? null]);
    if (!item) continue;
    subtotalCents += Math.round(item.look.price * 100) * quantity;
    if (!item.look.id) { unsupported = true; continue; }
    products.set(item.look.id, (products.get(item.look.id) || 0) + quantity);
  }
  const items = [...products].sort(([left], [right]) => left.localeCompare(right)).map(([productId, quantity]) => ({ productId, quantity }));
  return { items, fingerprint: JSON.stringify(signature), subtotalCents, unsupported };
}

function removeBagDiscount(message = "Discount code removed.") {
  bagDiscount.generation++;
  Object.assign(bagDiscount, { code: "", draft: "", quote: null, fingerprint: "", requestedFingerprint: "", pending: false, checkedAt: 0, message, error: false });
  renderShopDialog();
}

async function validateBagDiscount(code, force = false) {
  const snapshot = discountCartSnapshot(), normalized = code.trim().toUpperCase();
  if (!normalized || !snapshot.items.length || snapshot.unsupported) {
    Object.assign(bagDiscount, { code: "", quote: null, pending: false, message: snapshot.unsupported ? "Discounts need the current collection. Refresh the page and try again." : "Add a piece to your bag before applying a code.", error: true });
    renderShopDialog(); return false;
  }
  if (!force && bagDiscount.quote && bagDiscount.code === normalized && bagDiscount.fingerprint === snapshot.fingerprint && Date.now() - bagDiscount.checkedAt < 30000) return true;
  const generation = ++bagDiscount.generation;
  Object.assign(bagDiscount, { code: normalized, draft: normalized, quote: null, pending: true, requestedFingerprint: snapshot.fingerprint, message: "Checking your code…", error: false });
  renderShopDialog();
  let applied = false;
  try {
    const response = await fetch("/api/discounts/validate", {
      method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({ code: normalized, items: snapshot.items }), signal: AbortSignal.timeout(12000),
    });
    const result = await response.json();
    if (generation !== bagDiscount.generation) return false;
    if (snapshot.fingerprint !== discountCartSnapshot().fingerprint) return false;
    if (!response.ok) throw new Error(result.error || "This code is not available for your bag.");
    if (result.currency !== "EUR" || ![result.subtotalCents, result.discountCents, result.totalCents].every((value) => Number.isSafeInteger(value) && value >= 0)
        || result.subtotalCents - result.discountCents !== result.totalCents) throw new Error("We couldn't verify this discount total. Please try again.");
    Object.assign(bagDiscount, { quote: result, code: result.code, draft: result.code, fingerprint: snapshot.fingerprint, checkedAt: Date.now(),
      message: result.subtotalCents === snapshot.subtotalCents ? `${result.code} applied to your preview bag.` : `${result.code} applied. Your total reflects the latest prices.`, error: false });
    applied = true;
  } catch (error) {
    if (generation === bagDiscount.generation && snapshot.fingerprint === discountCartSnapshot().fingerprint) {
      Object.assign(bagDiscount, { code: "", quote: null, fingerprint: "", message: error.message || "We couldn't check this code. Please try again.", error: true });
    }
  } finally {
    if (generation === bagDiscount.generation) { bagDiscount.pending = false; renderShopDialog(); }
  }
  return applied;
}

function syncBagDiscount() {
  if (!bagDiscount.code) return;
  const snapshot = discountCartSnapshot();
  if (!snapshot.items.length || snapshot.unsupported) {
    bagDiscount.generation++;
    Object.assign(bagDiscount, { code: "", quote: null, pending: false, fingerprint: "", message: snapshot.unsupported ? "Refresh the collection before using a discount code." : "Your code was removed because the bag is empty.", error: false });
    return;
  }
  if (bagDiscount.pending && bagDiscount.requestedFingerprint === snapshot.fingerprint) return;
  if (bagDiscount.fingerprint !== snapshot.fingerprint || Date.now() - bagDiscount.checkedAt >= 30000) {
    bagDiscount.quote = null;
    void validateBagDiscount(bagDiscount.code, true);
  }
}

function currentBagDiscount() {
  return !bagDiscount.pending && bagDiscount.fingerprint === discountCartSnapshot().fingerprint ? bagDiscount.quote : null;
}

function appendDiscountSummary(parent, subtotal, label) {
  const quote = currentBagDiscount();
  if (quote) {
    const summary = document.createElement("div"); summary.className = "shop-discount-summary";
    const line = (name, amount, className = "") => {
      const row = document.createElement("div"); row.className = className;
      const title = document.createElement("span"); title.textContent = name;
      const value = document.createElement("strong"); value.textContent = amount; row.append(title, value); return row;
    };
    summary.append(line("Subtotal", currency.format(quote.subtotalCents / 100)), line(quote.code, `−${currency.format(quote.discountCents / 100)}`, "shop-discount-saving"));
    parent.append(summary);
  }
  const total = document.createElement("strong"); total.className = "shop-subtotal";
  total.textContent = `${label} ${currency.format(quote ? quote.totalCents / 100 : subtotal)}`;
  parent.append(total);
}

function appendDiscountForm(parent) {
  const block = document.createElement("section"); block.className = "shop-discount-block"; block.setAttribute("aria-label", "Discount code");
  const form = document.createElement("form"); form.className = "shop-discount-form";
  const label = document.createElement("label"); label.htmlFor = "bag-discount-code"; label.textContent = "A code for your occasion?";
  const controls = document.createElement("div"); controls.className = "shop-discount-controls";
  const input = document.createElement("input"); input.id = "bag-discount-code"; input.name = "discountCode"; input.type = "text"; input.autocomplete = "off"; input.maxLength = 40; input.pattern = "[A-Za-z0-9-]{3,40}";
  input.placeholder = "Enter discount code"; input.value = bagDiscount.draft; input.required = true; input.disabled = bagDiscount.pending;
  input.addEventListener("input", () => { bagDiscount.draft = input.value; });
  const apply = document.createElement("button"); apply.type = "submit"; apply.className = "shop-secondary"; apply.textContent = bagDiscount.pending ? "Checking…" : "Apply code"; apply.disabled = bagDiscount.pending;
  controls.append(input, apply);
  if (bagDiscount.code || bagDiscount.quote) {
    const remove = document.createElement("button"); remove.type = "button"; remove.className = "shop-discount-remove"; remove.textContent = "Remove"; remove.setAttribute("aria-label", "Remove applied discount code"); remove.addEventListener("click", () => removeBagDiscount()); controls.append(remove);
  }
  form.append(label, controls);
  form.addEventListener("submit", (event) => { event.preventDefault(); if (!bagDiscount.pending && form.reportValidity()) void validateBagDiscount(input.value, true); });
  const feedback = document.createElement("p"); feedback.id = "bag-discount-message"; feedback.className = `shop-discount-message${bagDiscount.error ? " is-error" : ""}`; feedback.setAttribute("role", bagDiscount.error ? "alert" : "status"); feedback.textContent = bagDiscount.message;
  input.setAttribute("aria-describedby", feedback.id); block.append(form, feedback); parent.append(block);
}

function showShoppingNotice(message, type = "success") {
  if (!(shoppingNotice instanceof HTMLDialogElement)) return;
  window.clearTimeout(shoppingNoticeTimer);
  shoppingNotice.className = `shopping-notice shopping-notice--${type}`;
  shoppingNotice.setAttribute("role", type === "error" ? "alert" : "status");
  shoppingNotice.setAttribute("aria-live", type === "error" ? "assertive" : "polite");
  shoppingNotice.textContent = message;
  if (!shoppingNotice.open) shoppingNotice.show();
  shoppingNoticeTimer = window.setTimeout(() => {
    if (shoppingNotice.open) shoppingNotice.close();
  }, 2800);
}

function shoppingSaveNotice(saved, successMessage, successType = "success") {
  showShoppingNotice(
    saved ? successMessage : "Your change is active for this visit, but couldn't be saved on this device.",
    saved ? successType : "error",
  );
}

if (shoppingStateReadError) {
  showShoppingNotice("Some saved shopping details couldn't be loaded. Please check your bag before continuing.", "error");
}

function updateShopCounts() {
  const itemCount = [...shoppingCart.entries()].reduce((total, [key, quantity]) => total + (getCartItem(key) ? quantity : 0), 0);
  const savedCount = [...savedLooks].filter((key) => getCartItem(key)).length;
  if (cartCount) cartCount.textContent = String(itemCount);
  if (wishlistCount) wishlistCount.textContent = String(savedCount);
  document.querySelectorAll(".header-cart-count").forEach((count) => {
    count.textContent = String(itemCount);
  });
  document.querySelectorAll(".header-wishlist-count").forEach((count) => {
    count.textContent = String(savedCount);
  });
  document.querySelectorAll('[data-shop-view="cart"]').forEach((button) => {
    button.setAttribute("aria-label", `Shopping bag, ${itemCount} ${itemCount === 1 ? "item" : "items"}`);
  });
  document.querySelectorAll('[data-shop-view="wishlist"]').forEach((button) => {
    button.setAttribute("aria-label", `Wishlist, ${savedCount} ${savedCount === 1 ? "item" : "items"}`);
  });
}

function updateWishlistButtons(key) {
  const isSaved = savedLooks.has(key);
  document.querySelectorAll(".save-look, .product-dialog-save").forEach((button) => {
    if (button.dataset.productKey !== key) return;
    button.setAttribute("aria-pressed", String(isSaved));
    button.setAttribute("aria-label", `${isSaved ? "Remove from" : "Add to"} wishlist: ${lookByKey.get(key)?.name ?? "look"}`);
    button.textContent = isSaved ? "♥ Saved" : "♡ Wishlist";
  });
}

function createShopAction(label, action, key, className = "shop-secondary") {
  const button = document.createElement("button");
  button.className = className;
  button.type = "button";
  button.dataset.shopAction = action;
  button.dataset.productKey = key;
  button.textContent = label;
  return button;
}

function renderShopDialog() {
  if (
    !(shopDialogTitle instanceof HTMLElement) ||
    !(shopDialogContent instanceof HTMLElement) ||
    !(shopDialogFooter instanceof HTMLElement)
  ) return;

  syncBagDiscount();

  const isCart = activeShopView === "cart";
  shopDialogFooter.classList.toggle("has-discounts", isCart);
  shopDialogTitle.textContent = isCart
    ? checkoutStage === "bag" ? "Your shopping bag" : checkoutStage === "review" ? "Review your preview" : "Preview complete"
    : "Your wishlist";
  const eyebrow = shopDialog.querySelector(".shop-dialog-header .eyebrow");
  if (eyebrow) {
    const line = document.createElement("span");
    line.className = "eyebrow-line";
    eyebrow.replaceChildren(line, document.createTextNode(
      isCart && checkoutStage !== "bag" ? " No-charge preview" : " Kept close",
    ));
  }
  const tabs = shopDialog.querySelector(".shop-dialog-tabs");
  if (tabs) tabs.hidden = isCart && checkoutStage !== "bag";
  document.querySelectorAll(".shop-dialog-tab").forEach((tab) => {
    const isActive = tab.dataset.shopView === activeShopView;
    tab.classList.toggle("is-active", isActive);
    tab.setAttribute("aria-pressed", String(isActive));
  });

  const entries = isCart ? [...shoppingCart.entries()] : [...savedLooks].map((key) => [key, 1]);
  const rows = entries.map(([key, quantity]) => {
    const item = getCartItem(key);
    if (!item) return null;
    const { look } = item;

    const row = document.createElement("article");
    row.className = "shop-line-item";
    const image = document.createElement("img");
    setProductImage(image, look, item.color ?? getVariantSelection(look).color);
    image.loading = "lazy";
    const copy = document.createElement("div");
    copy.className = "shop-line-copy";
    const name = document.createElement("strong");
    name.textContent = look.name;
    const founder = document.createElement("span");
    founder.textContent = look.founder;
    if (item.color && item.size) {
      const variant = document.createElement("span");
      variant.textContent = `${item.color} · Size ${item.size}`;
      copy.append(name, founder, variant);
    } else {
      copy.append(name, founder);
    }
    const price = document.createElement("span");
    price.className = "shop-line-price";
    price.textContent = currency.format(look.price);
    copy.append(price);
    const actions = document.createElement("div");
    actions.className = "shop-line-actions";

    if (isCart) {
      const quantityLabel = document.createElement("span");
      quantityLabel.className = "shop-quantity";
      quantityLabel.textContent = `Qty ${quantity}`;
      actions.append(
        createShopAction("−", "decrease", key, "shop-quantity-button"),
        quantityLabel,
        createShopAction("+", "increase", key, "shop-quantity-button"),
        createShopAction("Remove", "remove-cart", key),
      );
    } else {
      actions.append(
        createShopAction("Add to bag", "wishlist-to-cart", key, "shop-primary"),
        createShopAction("Remove", "remove-wishlist", key),
      );
    }

    row.append(image, copy, actions);
    return row;
  }).filter(Boolean);

  shopDialogContent.replaceChildren(...rows);
  if (isCart && checkoutStage !== "bag") {
    renderCheckoutStage();
    return;
  }
  if (!rows.length) {
    const empty = document.createElement("p");
    empty.className = "shop-empty";
    empty.textContent = isCart
      ? "Your preview bag is empty."
      : "Save the looks you love and find them here again.";
    shopDialogContent.append(empty);
  }

  shopDialogFooter.replaceChildren();
  if (isCart) {
    const subtotal = [...shoppingCart.entries()].reduce((sum, [key, quantity]) => {
      return sum + (getCartItem(key)?.look.price ?? 0) * quantity;
    }, 0);
    const note = document.createElement("p");
    note.textContent = "Prototype checkout only. Prices are illustrative; tax, shipping, and payment are not configured. No order is placed.";
    if (subtotal > 0) appendDiscountForm(shopDialogFooter);
    appendDiscountSummary(shopDialogFooter, subtotal, "Preview total");
    shopDialogFooter.append(note);
    if (subtotal > 0) {
      const checkout = document.createElement("button");
      checkout.type = "button";
      checkout.className = "shop-primary checkout-preview-button";
      checkout.dataset.checkoutAction = "review";
      checkout.textContent = "Review checkout preview";
      checkout.disabled = bagDiscount.pending;
      shopDialogFooter.append(checkout);
    }
    const links = document.createElement("nav");
    links.className = "shopping-help-links";
    links.setAttribute("aria-label", "Shopping bag help");
    for (const [href, text] of [["shopping-info.html", "Shopping information"], ["refund-policy.html", "Returns"], ["contact.html", "Contact"]]) {
      const link = document.createElement("a"); link.href = href; link.textContent = text; links.append(link);
    }
    shopDialogFooter.append(links);
  } else {
    const note = document.createElement("p");
    note.textContent = window.VeloraPrivacy?.canSaveLooks()
      ? "Your wishlist is saved on this device with your permission."
      : "Your wishlist stays on this page until you leave or reload. Choose Cookie settings to remember it on this device.";
    shopDialogFooter.append(note);
  }
}

function renderCheckoutStage() {
  const subtotal = [...shoppingCart.entries()].reduce((sum, [key, quantity]) => {
    return sum + (getCartItem(key)?.look.price ?? 0) * quantity;
  }, 0);

  if (checkoutStage === "review") {
    const review = document.createElement("section");
    review.className = "checkout-preview-review";
    review.setAttribute("aria-labelledby", "checkout-preview-title");
    const heading = document.createElement("h3");
    heading.id = "checkout-preview-title";
    heading.textContent = "A final look, with nothing to submit.";
    const description = document.createElement("p");
    description.textContent = "This sample checkout does not collect contact or payment details and cannot place an order.";
    review.append(heading, description);
    if (checkoutError) {
      const error = document.createElement("p");
      error.className = "checkout-preview-error";
      error.setAttribute("role", "alert");
      error.textContent = checkoutError;
      review.append(error);
    }
    const list = document.createElement("div");
    list.className = "checkout-preview-items";
    for (const [key, quantity] of shoppingCart) {
      const item = getCartItem(key);
      if (!item) continue;
      const line = document.createElement("article");
      line.className = "checkout-preview-item";
      const identity = document.createElement("span");
      const name = document.createElement("strong");
      name.textContent = item.look.name;
      identity.append(name);
      const variant = [item.color, item.size ? `Size ${item.size}` : ""].filter(Boolean).join(" · ");
      if (variant) {
        const detail = document.createElement("small");
        detail.textContent = variant;
        identity.append(detail);
      }
      const price = document.createElement("span");
      price.className = "checkout-preview-item-price";
      price.textContent = `${quantity} × ${currency.format(item.look.price)} = ${currency.format(item.look.price * quantity)}`;
      line.append(identity, price);
      list.append(line);
    }
    review.append(list);
    shopDialogContent.replaceChildren(review);

    const note = document.createElement("p");
    note.textContent = "Shipping and tax are not calculated. Selecting the button below only displays a sample confirmation.";
    const back = document.createElement("button");
    back.type = "button";
    back.className = "shop-secondary";
    back.dataset.checkoutAction = "back";
    back.textContent = "Back to bag";
    const confirm = document.createElement("button");
    confirm.type = "button";
    confirm.className = "shop-primary checkout-preview-button";
    confirm.dataset.checkoutAction = "complete";
    confirm.disabled = Boolean(checkoutError) || bagDiscount.pending;
    confirm.textContent = "Show sample confirmation";
    shopDialogFooter.replaceChildren();
    appendDiscountForm(shopDialogFooter);
    appendDiscountSummary(shopDialogFooter, subtotal, "Illustrative total");
    shopDialogFooter.append(note, back, confirm);
    return;
  }

  const confirmation = document.createElement("section");
  confirmation.className = "checkout-preview-complete";
  confirmation.setAttribute("aria-labelledby", "checkout-preview-complete-title");
  const mark = document.createElement("span");
  mark.className = "checkout-preview-complete-mark";
  mark.setAttribute("aria-hidden", "true");
  mark.textContent = "✓";
  const heading = document.createElement("h3");
  heading.id = "checkout-preview-complete-title";
  heading.tabIndex = -1;
  heading.textContent = "Preview complete.";
  const message = document.createElement("p");
  message.textContent = "This was a checkout demonstration only. No order was placed, no payment was taken, and your shopping bag is unchanged.";
  confirmation.append(mark, heading, message);
  appendDiscountSummary(confirmation, subtotal, "Illustrative total");
  shopDialogContent.replaceChildren(confirmation);

  const note = document.createElement("p");
  note.textContent = "This confirmation is not an order receipt.";
  const done = document.createElement("button");
  done.type = "button";
  done.className = "shop-primary checkout-preview-button";
  done.dataset.checkoutAction = "done";
  done.textContent = "Return to the collection";
  shopDialogFooter.replaceChildren(note, done);
}

function showShopDialog(view) {
  activeShopView = view;
  checkoutStage = "bag";
  checkoutError = "";
  renderShopDialog();
  if (view === "cart" && bagDiscount.code && !bagDiscount.pending) void validateBagDiscount(bagDiscount.code, true);
  if (shopDialog instanceof HTMLDialogElement && !shopDialog.open) shopDialog.showModal();
}

document.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof Element)) return;

  const galleryButton = target.closest("button[data-gallery-action], button[data-gallery-index]");
  if (galleryButton) {
    const gallery = galleryButton.closest("[data-gallery-product-key]");
    const look = lookByKey.get(gallery?.dataset.galleryProductKey);
    if (!gallery || !look) return;
    const index = galleryButton.hasAttribute("data-gallery-index")
      ? Number(galleryButton.dataset.galleryIndex)
      : Number(gallery.dataset.currentGalleryIndex || 0) + (galleryButton.dataset.galleryAction === "next" ? 1 : -1);
    selectGalleryPhoto(gallery, look, index);
    return;
  }

  const variantOption = target.closest(".product-option");
  if (variantOption instanceof HTMLButtonElement) {
    const options = variantOption.closest(".product-options");
    const key = options?.dataset.productKey;
    const look = key ? lookByKey.get(key) : undefined;
    const optionType = variantOption.dataset.optionType;
    const optionValue = variantOption.dataset.optionValue;
    if (!look || !optionValue || (optionType !== "color" && optionType !== "size")) return;
    if (optionType === "color" && !look.colors.some((color) => color.name === optionValue)) return;
    if (optionType === "size" && !look.sizes.includes(optionValue)) return;
    const selection = { ...getVariantSelection(look), [optionType]: optionValue };
    selectedVariants.set(look.key, selection);
    if (optionType === "color") updateProductColor(look);
    document.querySelectorAll(".product-options").forEach((group) => {
      if (group.dataset.productKey !== look.key) return;
      group.querySelectorAll(`.product-option[data-option-type="${optionType}"]`).forEach((button) => {
        button.setAttribute("aria-pressed", String(button.dataset.optionValue === optionValue));
      });
    });
    return;
  }

  const quickView = target.closest(".look-quick-view, .look-photo-trigger, .product-size-help");
  if (quickView instanceof HTMLButtonElement) {
    if (
      !(productDialog instanceof HTMLDialogElement) ||
      !(productDialogImage instanceof HTMLImageElement) ||
      !(productDialogTitle instanceof HTMLElement) ||
      !(productDialogFounder instanceof HTMLElement)
    ) return;

    const look = lookByKey.get(quickView.dataset.productKey ?? "");
    if (!look || look.published === false) return;
    setProductImage(productDialogImage, look);
    attachProductGallery(productDialogImage.closest(".product-dialog-gallery"), look);
    productDialogTitle.textContent = look.name;
    if (productDialogPrice instanceof HTMLElement) productDialogPrice.textContent = currency.format(look.price);
    productDialogFounder.textContent = [
      look.founder,
      look.collection,
    ]
      .filter(Boolean)
      .join(" · ") || "From our first edit";
    if (productDialogNote instanceof HTMLElement) productDialogNote.textContent = look.description;
    if (productDialogOptions instanceof HTMLElement) {
      productDialogOptions.replaceChildren(createProductOptions(look));
    }
    if (productDialogAdd instanceof HTMLButtonElement) {
      productDialogAdd.dataset.productKey = look.key;
      configurePurchaseButton(productDialogAdd, look);
    }
    if (productDialogSave instanceof HTMLButtonElement) {
      productDialogSave.dataset.productKey = look.key;
      productDialogSave.setAttribute("aria-pressed", String(savedLooks.has(look.key)));
      productDialogSave.textContent = savedLooks.has(look.key) ? "♥ Saved" : "♡ Add to wishlist";
    }
    if (!productDialog.open) productDialog.showModal();
    renderProductInformation(look, quickView.dataset.fitFocus === "true");
    return;
  }

  const shopViewButton = target.closest("[data-shop-view]");
  if (shopViewButton instanceof HTMLButtonElement) {
    showShopDialog(shopViewButton.dataset.shopView === "wishlist" ? "wishlist" : "cart");
    return;
  }

  const shopTab = target.closest(".shop-dialog-tab");
  if (shopTab instanceof HTMLButtonElement) {
    showShopDialog(shopTab.dataset.shopView === "wishlist" ? "wishlist" : "cart");
    return;
  }

  const checkoutButton = target.closest("[data-checkout-action]");
  if (checkoutButton instanceof HTMLButtonElement) {
    const action = checkoutButton.dataset.checkoutAction;
    if (action === "review") {
      const entries = [...shoppingCart.entries()];
      const unavailable = entries.filter(([key]) => !getCartItem(key));
      if (unavailable.length) {
        unavailable.forEach(([key]) => shoppingCart.delete(key));
        persistShoppingState();
        checkoutError = "Some saved items are no longer in the collection. Review the updated bag before continuing.";
        checkoutStage = "review";
        renderShopDialog();
        return;
      }
      if (!entries.length) {
        checkoutError = "Add a piece to your preview bag before reviewing checkout.";
        checkoutStage = "bag";
        renderShopDialog();
        return;
      }
      const unavailableStock = entries.find(([key, quantity]) => {
        const item = getCartItem(key);
        const stock = variantAvailableStock(item.look, {
          color: item.color ?? getVariantSelection(item.look).color,
          size: item.size ?? getVariantSelection(item.look).size,
        });
        return stock !== null && stock !== undefined && quantity > stock;
      });
      if (unavailableStock) {
        const item = getCartItem(unavailableStock[0]);
        checkoutError = `${item.look.name} exceeds the currently listed stock. Adjust the quantity in your bag before continuing.`;
      } else {
        checkoutError = "";
      }
      checkoutStage = "review";
      if (bagDiscount.code && !bagDiscount.pending) void validateBagDiscount(bagDiscount.code, true);
      renderShopDialog();
      return;
    }
    if (action === "back") {
      checkoutStage = "bag";
      checkoutError = "";
      renderShopDialog();
      return;
    }
    if (action === "complete" && !checkoutError) {
      if (bagDiscount.pending) return;
      if (bagDiscount.code && !await validateBagDiscount(bagDiscount.code, true)) return;
      checkoutStage = "complete";
      renderShopDialog();
      shopDialogContent.querySelector("#checkout-preview-complete-title")?.focus();
      return;
    }
    if (action === "done") {
      checkoutStage = "bag";
      checkoutError = "";
      if (shopDialog instanceof HTMLDialogElement && shopDialog.open) shopDialog.close();
      return;
    }
  }

  const saveButton = target.closest(".save-look, .product-dialog-save");
  if (saveButton instanceof HTMLButtonElement) {
    const key = saveButton.dataset.productKey;
    const look = key ? lookByKey.get(key) : undefined;
    if (!key || !look) return;
    const wasSaved = savedLooks.has(key);
    if (wasSaved) savedLooks.delete(key);
    else savedLooks.add(key);
    const saved = persistShoppingState();
    updateWishlistButtons(key);
    updateShopCounts();
    if (activeShopView === "wishlist" && shopDialog instanceof HTMLDialogElement && shopDialog.open) renderShopDialog();
    shoppingSaveNotice(
      saved,
      wasSaved ? `Removed ${look.name} from your wishlist.` : `Added ${look.name} to your wishlist.`,
      wasSaved ? "neutral" : "success",
    );
    return;
  }

  const addButton = target.closest(".add-to-bag, .product-dialog-add");
  if (addButton instanceof HTMLButtonElement) {
    const key = addButton.dataset.productKey;
    const look = key ? lookByKey.get(key) : undefined;
    if (!look || look.published === false) return;
    if (!canAddToBag(look)) return;
    const cartKey = createCartKey(look);
    shoppingCart.set(cartKey, (shoppingCart.get(cartKey) ?? 0) + 1);
    const saved = persistShoppingState();
    updateShopCounts();
    if (shopDialog instanceof HTMLDialogElement && shopDialog.open && activeShopView === "cart") renderShopDialog();
    showShoppingNotice(
      saved ? `Added ${look.name} to your shopping bag.` : "Your change is active for this visit, but couldn't be saved on this device.",
      saved ? "success" : "error",
    );
    addButton.textContent = "Added to bag ✓";
    window.setTimeout(() => {
      if (addButton.isConnected) addButton.textContent = "Add to bag";
    }, 1400);
    return;
  }

  const shopAction = target.closest("[data-shop-action]");
  if (shopAction instanceof HTMLButtonElement) {
    const key = shopAction.dataset.productKey;
    const action = shopAction.dataset.shopAction;
    const item = key ? getCartItem(key) : null;
    if (!item) return;
    if (item.look.published === false && (action === "increase" || action === "wishlist-to-cart")) return;
    const selection = { color: item.color || getVariantSelection(item.look).color, size: item.size || getVariantSelection(item.look).size };
    if ((action === "increase" || action === "wishlist-to-cart") && !canAddToBag(item.look, selection)) return;
    let notice;
    if (action === "increase") shoppingCart.set(key, (shoppingCart.get(key) ?? 0) + 1);
    if (action === "increase") notice = `Added another ${item.look.name} to your shopping bag.`;
    if (action === "decrease") {
      const quantity = (shoppingCart.get(key) ?? 0) - 1;
      if (quantity > 0) shoppingCart.set(key, quantity);
      else shoppingCart.delete(key);
      notice = quantity > 0
        ? `Updated the quantity of ${item.look.name} in your shopping bag.`
        : `Removed ${item.look.name} from your shopping bag.`;
    }
    if (action === "remove-cart") {
      shoppingCart.delete(key);
      notice = `Removed ${item.look.name} from your shopping bag.`;
    }
    if (action === "remove-wishlist") {
      savedLooks.delete(key);
      notice = `Removed ${item.look.name} from your wishlist.`;
    }
    if (action === "wishlist-to-cart") {
      const cartKey = createCartKey(item.look, selection);
      shoppingCart.set(cartKey, (shoppingCart.get(cartKey) ?? 0) + 1);
      notice = `Added ${item.look.name} to your shopping bag.`;
    }
    const saved = persistShoppingState();
    updateShopCounts();
    renderShopDialog();
    if (notice) {
      showShoppingNotice(
        saved ? notice : "Your change is active for this visit, but couldn't be saved on this device.",
        saved ? (action === "remove-cart" || action === "remove-wishlist" ? "neutral" : "success") : "error",
      );
    }
  }
});

renderLooks();

productDialogClose?.addEventListener("click", () => {
  if (productDialog instanceof HTMLDialogElement) productDialog.close();
});

productDialog?.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && productDialog instanceof HTMLDialogElement) {
    event.preventDefault();
    productDialog.close();
  }
});

productDialog?.addEventListener("click", (event) => {
  if (event.target === productDialog && productDialog instanceof HTMLDialogElement) {
    productDialog.close();
  }
});

productDialogLink?.addEventListener("click", () => {
  if (productDialog instanceof HTMLDialogElement) productDialog.close();
});

shopDialog?.addEventListener("click", (event) => {
  if (event.target === shopDialog && shopDialog instanceof HTMLDialogElement) shopDialog.close();
});

shopDialog?.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && shopDialog instanceof HTMLDialogElement) {
    event.preventDefault();
    shopDialog.close();
  }
});

updateShopCounts();

document.querySelectorAll("[data-founder-link]").forEach((founderLink) => {
  founderLink.addEventListener("click", () => {
    const founder = founderLink.getAttribute("data-founder-link");
    const filter = document.querySelector(`.look-filter[data-founder="${founder}"]`);
    if (filter instanceof HTMLButtonElement) filter.click();
  });
});

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

if (window.matchMedia("(hover: hover) and (pointer: fine)").matches && !reducedMotion.matches) {
  document.querySelectorAll(".tilt-surface").forEach((surface) => {
    surface.addEventListener("pointermove", (event) => {
      const bounds = surface.getBoundingClientRect();
      const x = (event.clientX - bounds.left) / bounds.width - 0.5;
      const y = (event.clientY - bounds.top) / bounds.height - 0.5;
      surface.style.transform = `perspective(1100px) rotateY(${x * 3}deg) rotateX(${y * -3}deg)`;
    });

    surface.addEventListener("pointerleave", () => {
      surface.style.transform = "";
    });
  });
}

window.addEventListener("velora:privacy-changed", () => {
  if (!window.VeloraPrivacy?.canSaveLooks()) savedLooks.clear();
  persistShoppingState();
  updateShopCounts();
  renderLooks();
  renderRecommendations();
  if (shopDialog?.open) renderShopDialog();
});
window.addEventListener("velora:device-data-cleared", () => {
  savedLooks.clear();
  shoppingCart.clear();
  updateShopCounts();
  renderLooks();
  renderRecommendations();
  if (shopDialog?.open) renderShopDialog();
});
window.addEventListener("pageshow", (event) => {
  if (!event.persisted) return;
  const { wishlist, cart } = readShoppingState();
  savedLooks.clear();
  wishlist.forEach((key) => savedLooks.add(key));
  shoppingCart.clear();
  cart.forEach((quantity, key) => shoppingCart.set(key, quantity));
  updateShopCounts();
  renderLooks();
  renderRecommendations();
  if (shopDialog?.open) renderShopDialog();
});

const year = document.querySelector("#year");
if (year) year.textContent = String(new Date().getFullYear());

// The static collection remains available for previews; the account server supplies
// the saved prices, descriptions, and publication state when it is running.
let catalogLoading = null;
let catalogSignature = "";
let catalogLoadedAt = 0;

function reconcileManagedProducts(products) {
  const known = [...new Set(lookByKey.values())];
  const byId = new Map(known.filter((look) => look.id).map((look) => [look.id, look]));
  const legacy = new Map(known.filter((look) => !look.managed).map((look) => [look.key, look]));
  known.forEach((look) => { look.published = false; });
  const items = products.map((product) => {
    const original = product.legacy_key ? legacy.get(product.legacy_key) : null;
    const look = byId.get(product.id) || original || {};
    if (original) legacy.delete(product.legacy_key);
    const previousKey = look.key;
    const key = `product:${product.id}`;
    if (previousKey && previousKey !== key) {
      productKeyAliases.set(previousKey, key);
      if (selectedVariants.has(previousKey)) selectedVariants.set(key, selectedVariants.get(previousKey));
    }
    const previousNumber = look.number;
    Object.assign(look, product, {
      key, managed: true, published: true,
      number: previousNumber || product.sku || product.id,
      sizes: product.sizes?.length ? product.sizes : ["XS", "S", "M", "L"],
      images: product.images?.length ? [...product.images] : [product.image],
    });
    look.colors = getProductColors(look);
    lookByKey.set(key, look);
    return look;
  });
  // Move the old static product keys to immutable server IDs. Saved variants keep
  // their color/size suffix when a title or cover photo changes in the portal.
  let migrated = false;
  const canonical = (key) => {
    const separator = key.indexOf("::");
    const base = separator < 0 ? key : key.slice(0, separator);
    const suffix = separator < 0 ? "" : key.slice(separator);
    const replacement = productKeyAliases.get(base);
    if (replacement) { migrated = true; return replacement + suffix; }
    return key;
  };
  const saved = [...savedLooks].map(canonical);
  const cart = new Map();
  shoppingCart.forEach((quantity, key) => {
    const mapped = canonical(key);
    cart.set(mapped, (cart.get(mapped) || 0) + quantity);
  });
  savedLooks.clear();
  saved.forEach((key) => savedLooks.add(key));
  shoppingCart.clear();
  cart.forEach((quantity, key) => shoppingCart.set(key, quantity));
  items.sort((left, right) => (Date.parse(right.created_at) || 0) - (Date.parse(left.created_at) || 0));
  individualLooks.splice(0, individualLooks.length, ...items);
  if (migrated) persistShoppingState();
}

function renderCatalogFilters() {
  renderFacetOptions();
  const categories = [...new Set(individualLooks.map((look) => look.collection))];
  const founders = [...new Set(individualLooks.map((look) => look.founder))];
  if (!categories.includes(activeCategory)) activeCategory = "all";
  if (!founders.includes(activeFounder)) activeFounder = "all";
  const categoryNames = {
    "THE EVERYDAY EDIT": "Everyday", "THE SOFT EDIT": "Soft essentials",
    "THE AFTER-HOURS EDIT": "After hours", "THE EVENING EDIT": "Evening",
    "THE MODEST EDIT": "Modest dressing", "THE POLISHED EDIT": "Polished",
    "THE TAILORED EDIT": "Tailoring", "THE OCCASION EDIT": "Occasion", "THE LAYERING EDIT": "Layering",
  };
  function button(value, text, type, selected) {
    const node = document.createElement("button");
    node.type = "button";
    node.className = `look-filter${value === selected ? " is-active" : ""}`;
    node.dataset[type] = value;
    node.textContent = text;
    node.setAttribute("aria-pressed", String(value === selected));
    return node;
  }
  const categoryGroup = document.querySelector('[data-filter-group="category"]');
  categoryGroup?.replaceChildren(button("all", "Shop all", "category", activeCategory), ...categories.map((value) => button(value, categoryNames[value] || value, "category", activeCategory)));
  const founderGroup = document.querySelector('[data-filter-group="founder"]');
  if (founderGroup) {
    const label = document.createElement("span");
    label.className = "look-filter-label";
    label.textContent = "THE DESIGNERS";
    founderGroup.replaceChildren(label, button("all", "All the looks", "founder", activeFounder), ...founders.map((value) => button(value, value.split(" ")[0], "founder", activeFounder)));
  }
}

async function loadManagedCatalog() {
  if (!/^https?:$/.test(location.protocol)) return false;
  if (catalogLoading) return catalogLoading;
  catalogLoadedAt = Date.now();
  catalogLoading = (async () => {
    try {
      const response = await fetch("/api/catalog", { cache: "no-store", signal: AbortSignal.timeout(10000) });
      if (!response.ok) return false;
      const { products } = await response.json();
      if (!Array.isArray(products)) return false;
      const signature = JSON.stringify(products);
      if (signature === catalogSignature) return true;
      reconcileManagedProducts(products);
      catalogSignature = signature;
      renderCatalogFilters();
      renderLooks();
      renderRecommendations();
      updateShopCounts();
      if (productDialog?.open) productDialog.close();
      if (shopDialog?.open) renderShopDialog();
      document.documentElement.dataset.catalogState = "managed";
      return true;
    } catch {
      return false;
    } finally {
      catalogLoading = null;
    }
  })();
  return catalogLoading;
}
window.veloraCatalogReady = loadManagedCatalog();
const requestedShopView = new URLSearchParams(location.search);
if (requestedShopView.get("view") === "bag") {
  window.veloraCatalogReady.finally(() => {
    activeShopView = "cart";
    checkoutStage = "bag";
    renderShopDialog();
    if (shopDialog instanceof HTMLDialogElement && !shopDialog.open) shopDialog.showModal();
    requestedShopView.delete("view");
    const search = requestedShopView.toString();
    history.replaceState(null, "", `${location.pathname}${search ? `?${search}` : ""}${location.hash}`);
  });
}
window.addEventListener("focus", () => {
  if (Date.now() - catalogLoadedAt > 2000) window.veloraCatalogReady = loadManagedCatalog();
});
