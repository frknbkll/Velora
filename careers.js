(() => {
  "use strict";

  const vacancies = [
    {
      slug: "sales-client-experience-associate",
      title: "Sales & Client Experience Associate",
      team: "Client experience",
      artwork: "client-experience",
      poster: "assets/careers/sales-client-experience-associate.svg",
      introduction: "Make every conversation feel considered, warm, and distinctly Velora.",
      overview: "The Sales & Client Experience Associate helps make discovering Velora feel personal. This role brings thoughtful styling guidance together with attentive service, creating a welcoming experience from the first question to the final details.",
      responsibilities: [
        "Welcome customers and offer thoughtful, individual styling guidance.",
        "Help customers explore pieces, fit, and outfit pairings.",
        "Support the sales floor and make each brand interaction feel seamless.",
        "Share recurring customer questions and feedback with the wider team."
      ],
      qualities: [
        "Warm, clear communication and a customer-first point of view.",
        "A genuine interest in fashion, personal styling, and considered service.",
        "Care with details and confidence working collaboratively."
      ]
    },
    {
      slug: "marketing-social-media-coordinator",
      title: "Marketing & Social Media Coordinator",
      team: "Brand & community",
      artwork: "social-storytelling",
      introduction: "Bring the Velora point of view to life across stories, campaigns, and community.",
      overview: "This role helps translate the Velora brand into thoughtful, consistent communication. You will connect creative ideas with a clear content plan and help make every interaction feel recognizably human.",
      responsibilities: [
        "Plan and create engaging social content that reflects the brand voice.",
        "Coordinate campaign calendars, launches, and creative collaborations.",
        "Listen to the community and turn insights into meaningful brand moments.",
        "Review content performance and share practical learnings with the team."
      ],
      qualities: [
        "A clear storyteller with a strong visual eye and thoughtful ideas.",
        "An understanding of social platforms, fashion culture, and online communities.",
        "Good organization and a collaborative approach to creative work."
      ]
    },
    {
      slug: "fashion-design-assistant",
      title: "Fashion & Design Assistant",
      team: "Creative studio",
      artwork: "fashion-design",
      introduction: "Help shape the pieces, details, and visual language of each collection.",
      overview: "The Fashion & Design Assistant supports the early ideas and practical details behind a collection. It is a hands-on creative role for someone curious about how research, fabric, fit, and styling come together.",
      responsibilities: [
        "Support research, mood boards, and early collection concepts.",
        "Assist with styling, fittings, and preparation for campaign shoots.",
        "Organize design references, fabric notes, and collection materials.",
        "Help keep creative samples and project information easy to follow."
      ],
      qualities: [
        "A curious, detail-minded creative with an interest in fashion design.",
        "An eye for textiles, styling, proportion, and considered craftsmanship.",
        "A willingness to learn and contribute across a small creative team."
      ]
    },
    {
      slug: "ecommerce-merchandising-coordinator",
      title: "E-commerce & Merchandising Coordinator",
      team: "Digital storefront",
      artwork: "ecommerce",
      introduction: "Make the online collection easy to explore, understand, and love.",
      overview: "This coordinator keeps the digital collection considered and clear. The role connects product information, visual presentation, and customer journeys so each piece is represented consistently online.",
      responsibilities: [
        "Organize product details, imagery, and collection updates for the online store.",
        "Check product pages for clear descriptions, accurate options, and consistent presentation.",
        "Coordinate with creative and customer experience teammates on launches.",
        "Notice friction in the shopping journey and suggest practical improvements."
      ],
      qualities: [
        "Strong attention to detail and comfort organizing information.",
        "An interest in fashion e-commerce, product presentation, and customer journeys.",
        "Clear communication and confidence managing several small tasks."
      ]
    },
    {
      slug: "customer-care-specialist",
      title: "Customer Care Specialist",
      team: "Client experience",
      artwork: "customer-care",
      introduction: "Turn customer questions into moments of clarity and care.",
      overview: "The Customer Care Specialist supports customers with thoughtful, useful answers. This role helps people feel heard while sharing common themes with the team so the experience can keep improving.",
      responsibilities: [
        "Respond to product, sizing, and general service questions with care.",
        "Explain available shopping information in a clear, consistent way.",
        "Keep track of recurring enquiries and help identify where guidance could improve.",
        "Work with the team to make customer communication feel personal and helpful."
      ],
      qualities: [
        "Empathy, patience, and excellent written communication.",
        "A practical, calm approach to solving customer questions.",
        "Interest in fashion and a commitment to clear, honest service."
      ]
    },
    {
      slug: "production-sourcing-assistant",
      title: "Production & Sourcing Assistant",
      team: "Product & production",
      artwork: "production",
      introduction: "Help bring thoughtful materials and well-made ideas together.",
      overview: "This assistant supports the research and coordination behind product development. The focus is on keeping information organized and helping the team ask considered questions about materials, samples, and production.",
      responsibilities: [
        "Organize material references, supplier information, and sample notes.",
        "Help track product development milestones and follow-up questions.",
        "Support research into fabrics, trims, and construction details.",
        "Keep communication between product and creative work clear and timely."
      ],
      qualities: [
        "A structured and reliable approach to details and documentation.",
        "Curiosity about textiles, garment construction, and responsible sourcing.",
        "Thoughtful communication and a collaborative working style."
      ]
    },
    {
      slug: "visual-content-producer",
      title: "Visual Content Producer",
      team: "Creative studio",
      artwork: "visual-content",
      introduction: "Create imagery that makes the feeling behind each piece visible.",
      overview: "The Visual Content Producer helps plan and deliver the imagery that introduces Velora collections. This role brings a strong visual point of view together with careful shoot preparation and asset organization.",
      responsibilities: [
        "Help plan photo and video concepts for products, stories, and campaigns.",
        "Coordinate shoot references, shot lists, styling needs, and schedules.",
        "Organize and prepare visual assets for use across the website and social channels.",
        "Work with the team to keep imagery cohesive and accessible."
      ],
      qualities: [
        "A strong visual eye and interest in fashion photography or content production.",
        "Good planning skills and care with creative details.",
        "A flexible, collaborative approach on shoot days and during preparation."
      ]
    },
    {
      slug: "retail-operations-coordinator",
      title: "Retail Operations Coordinator",
      team: "Retail & operations",
      artwork: "retail-operations",
      introduction: "Make the thoughtful details of the Velora experience work smoothly.",
      overview: "This role helps coordinate the practical work that supports a considered retail experience. It connects people, product information, and day-to-day processes so the team can focus on customers.",
      responsibilities: [
        "Help organize store routines, schedules, and operational checklists.",
        "Keep product and display information accurate and easy for the team to use.",
        "Support stock awareness and communicate operational needs clearly.",
        "Identify small process improvements that make daily work easier."
      ],
      qualities: [
        "A dependable, organized approach and comfort following through.",
        "An interest in customer experience and retail operations.",
        "Clear communication and a practical, helpful mindset."
      ]
    },
    {
      slug: "product-copywriter",
      title: "Product Copywriter",
      team: "Brand & storytelling",
      artwork: "copywriting",
      introduction: "Give every piece a description that is useful, warm, and true to its details.",
      overview: "The Product Copywriter turns product knowledge into clear, inviting language. This role balances the personality of the Velora voice with practical details customers need to make informed choices.",
      responsibilities: [
        "Write and refine product descriptions, collection notes, and helpful guidance.",
        "Work with the product team to confirm names, details, and material information.",
        "Keep language consistent across the website and supporting content.",
        "Edit copy for clarity, accessibility, and a thoughtful brand voice."
      ],
      qualities: [
        "Excellent writing and editing skills with a careful eye for accuracy.",
        "An ability to explain product details in a clear, natural way.",
        "Interest in fashion, brand storytelling, and inclusive communication."
      ]
    },
    {
      slug: "people-culture-assistant",
      title: "People & Culture Assistant",
      team: "People & culture",
      artwork: "people-culture",
      introduction: "Help create a welcoming, thoughtful experience for the people behind Velora.",
      overview: "This assistant supports the everyday details that help a small team work well together. The role is grounded in discretion, organization, and care for clear, welcoming communication.",
      responsibilities: [
        "Help organize onboarding information and team resources.",
        "Coordinate schedules and practical details for team activities.",
        "Keep people-related records and shared information carefully organized.",
        "Support a welcoming and respectful team culture in everyday interactions."
      ],
      qualities: [
        "Discretion, empathy, and a respectful approach to sensitive information.",
        "Good organization and attention to detail.",
        "A genuine interest in people support and thoughtful team experiences."
      ]
    },
    {
      slug: "sustainability-materials-coordinator",
      title: "Sustainability & Materials Coordinator",
      team: "Product & impact",
      artwork: "materials",
      introduction: "Bring care and curiosity to the materials and choices behind each collection.",
      overview: "The Sustainability & Materials Coordinator helps the team understand product materials and document what is known. The role favors careful research and transparent communication over unsupported claims.",
      responsibilities: [
        "Gather and organize available information about materials and product care.",
        "Research lower-impact material options and relevant industry practices.",
        "Help document questions and evidence for product and sourcing decisions.",
        "Review public-facing sustainability language for clarity and substantiation."
      ],
      qualities: [
        "Curiosity about textiles, material choices, and responsible design.",
        "Careful research habits and a commitment to evidence-based communication.",
        "Clear writing, organization, and a collaborative approach."
      ]
    }
  ];

  const illustrations = {
    "client-experience": {
      colors: ["#e8cdb5", "#b87357", "#49362e"],
      drawing: `<path d="M253 153 300 191l47-38" fill="none" stroke="#49362e" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/><path d="M300 190v37" stroke="#49362e" stroke-width="8" stroke-linecap="round"/><path d="M245 224q55-31 110 0l-14 145q-41 37-82 0z" fill="#b87357"/><path d="M274 229v105m52-105v105" fill="none" stroke="#f4e7d8" stroke-width="4" stroke-dasharray="5 8"/><path d="M230 374h140M246 374v35m108-35v35M300 374v35" fill="none" stroke="#49362e" stroke-width="6" stroke-linecap="round"/>`
    },
    "social-storytelling": {
      colors: ["#ead5c5", "#bd795e", "#463b38"],
      drawing: `<rect x="239" y="146" width="122" height="230" rx="22" fill="#463b38"/><rect x="249" y="161" width="102" height="198" rx="13" fill="#f3e8de"/><rect x="260" y="174" width="80" height="84" rx="8" fill="#d9a58c"/><circle cx="300" cy="215" r="20" fill="#f3e8de"/><path d="m260 249 25-26 20 17 13-13 22 31h-80z" fill="#b76e58"/><circle cx="267" cy="278" r="6" fill="#b76e58"/><path d="M281 278h54m-68 20h68m-68 13h44" stroke="#8c7064" stroke-width="5" stroke-linecap="round"/><circle cx="278" cy="341" r="5" fill="#d6b38d"/><circle cx="300" cy="341" r="5" fill="#b76e58"/><circle cx="322" cy="341" r="5" fill="#d6b38d"/><path d="M382 185h52v43h-30l-14 13v-13h-8z" fill="#b76e58"/><path d="M395 201h26m-26 11h18" stroke="#fff4e8" stroke-width="4" stroke-linecap="round"/><circle cx="213" cy="300" r="24" fill="#d9a58c"/><path d="m213 286 5 10 11 2-8 8 2 11-10-5-10 5 2-11-8-8 11-2z" fill="#fff1df"/>`
    },
    "fashion-design": {
      colors: ["#e9d8c6", "#b77c65", "#453832"],
      drawing: `<path d="M300 142v34m-39-29h78m-58 5q0 17 19 24 19-7 19-24" fill="none" stroke="#453832" stroke-width="7" stroke-linecap="round"/><path d="M284 176h32l14 36 42 21-18 25-21-10 15 119q-48 38-96 0l15-119-21 10-18-25 42-21z" fill="#b77c65"/><path d="M284 184q16 13 32 0m-16 21v133m-35-100 35 17 35-17" fill="none" stroke="#f4e9dc" stroke-width="4" stroke-dasharray="5 7"/><path d="M384 323h56v57h-56z" fill="#d4ae8e"/><path d="M399 323v57m14-57v57" stroke="#f4e9dc" stroke-width="4"/><circle cx="413" cy="414" r="24" fill="#b77c65"/><path d="m400 414 9 9 18-21" fill="none" stroke="#fff5e9" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>`
    },
    ecommerce: {
      colors: ["#e7d8cb", "#9d806c", "#403934"],
      drawing: `<rect x="186" y="171" width="228" height="157" rx="11" fill="#403934"/><rect x="198" y="183" width="204" height="132" rx="5" fill="#f4ede5"/><rect x="211" y="196" width="78" height="106" rx="4" fill="#d8bba4"/><path d="M235 213h30m-25 8h20m-35 62 25-34 20 20 15-13 22 34h-82z" fill="#9d806c"/><rect x="299" y="201" width="88" height="9" rx="4" fill="#b39a88"/><rect x="299" y="222" width="68" height="7" rx="3" fill="#d1beb0"/><rect x="299" y="239" width="78" height="7" rx="3" fill="#d1beb0"/><rect x="299" y="266" width="62" height="22" rx="11" fill="#9d806c"/><path d="m170 342 27-16h176l27 16q-1 13-13 13H183q-12 0-13-13z" fill="#403934"/><path d="M269 344h32" stroke="#f4ede5" stroke-width="4" stroke-linecap="round"/>`
    },
    "customer-care": {
      colors: ["#e7d5c6", "#bd8164", "#433b37"],
      drawing: `<circle cx="300" cy="247" r="63" fill="#d8ad92"/><path d="M238 247a62 62 0 0 1 124 0" fill="none" stroke="#433b37" stroke-width="13" stroke-linecap="round"/><rect x="230" y="242" width="23" height="55" rx="11" fill="#bd8164"/><rect x="347" y="242" width="23" height="55" rx="11" fill="#bd8164"/><path d="M359 291q0 44-48 44" fill="none" stroke="#433b37" stroke-width="7" stroke-linecap="round"/><circle cx="303" cy="335" r="8" fill="#433b37"/><path d="M193 174h82v57h-48l-20 18v-18h-14z" fill="#fff4e8"/><circle cx="218" cy="202" r="4" fill="#bd8164"/><circle cx="233" cy="202" r="4" fill="#bd8164"/><circle cx="248" cy="202" r="4" fill="#bd8164"/><path d="M353 160h65v47h-36l-16 14v-14h-13z" fill="#bd8164"/><path d="M369 178h33m-33 10h22" stroke="#fff4e8" stroke-width="4" stroke-linecap="round"/>`
    },
    production: {
      colors: ["#e8d8c4", "#a8795c", "#483c33"],
      drawing: `<path d="m240 173 60-27 60 27-60 28z" fill="#c99d7b"/><path d="m240 173 60 28v152l-60-30z" fill="#a8795c"/><path d="m360 173-60 28v152l60-30z" fill="#88634f"/><path d="m240 204 60 28 60-28m-120 36 60 28 60-28m-120 36 60 28 60-28m-120 36 60 28 60-28" fill="none" stroke="#e8d8c4" stroke-width="4"/><path d="M214 362q38-21 76 0 38 21 76 0v34q-38 21-76 0-38-21-76 0z" fill="#d8b89b"/><path d="M214 378q38-21 76 0 38 21 76 0" fill="none" stroke="#f5eadd" stroke-width="4"/><circle cx="381" cy="143" r="23" fill="#f4e8d7"/><path d="M380 127q-20 24 2 33 19-16-2-33m2 32 12-17" fill="none" stroke="#71806b" stroke-width="4" stroke-linecap="round"/>`
    },
    "visual-content": {
      colors: ["#e6d6c8", "#b1765e", "#403733"],
      drawing: `<path d="M185 218h42l20-28h103l21 28h44q14 0 14 14v115q0 14-14 14H185q-14 0-14-14V232q0-14 14-14z" fill="#403733"/><circle cx="300" cy="275" r="64" fill="#d9c2ad"/><circle cx="300" cy="275" r="47" fill="#b1765e"/><circle cx="300" cy="275" r="32" fill="#403733"/><circle cx="300" cy="275" r="16" fill="#d9c2ad"/><circle cx="224" cy="240" r="8" fill="#e6d6c8"/><rect x="356" y="230" width="28" height="15" rx="5" fill="#d9c2ad"/><path d="M201 384h198m-164 17h130" stroke="#b1765e" stroke-width="5" stroke-linecap="round"/><path d="m437 179 9 22 23 9-23 9-9 22-9-22-23-9 23-9z" fill="#c99573"/>`
    },
    "retail-operations": {
      colors: ["#e8d8ca", "#a98168", "#493b35"],
      drawing: `<path d="M205 192h190m-166 0v185m143-185v185M217 377h152" fill="none" stroke="#493b35" stroke-width="7" stroke-linecap="round"/><path d="m247 217 26 19 26-19m-52 0h52l-7 96q-19 18-38 0z" fill="#bd8f73"/><path d="m307 217 26 19 26-19m-52 0h52l-7 96q-19 18-38 0z" fill="#e6cbb4"/><path d="M254 267h38m-38 14h33m-33 14h26" stroke="#f7ede3" stroke-width="4" stroke-linecap="round"/><path d="M364 292h78l-8 87h-62z" fill="#a98168"/><path d="M382 292v-16q0-20 21-20t21 20v16" fill="none" stroke="#493b35" stroke-width="6"/><path d="M384 327h39" stroke="#e8d8ca" stroke-width="4"/>`
    },
    copywriting: {
      colors: ["#ead9c7", "#ab765b", "#443a35"],
      drawing: `<path d="M218 143h131l42 42v207H218z" fill="#fff5e9"/><path d="M349 143v44h42" fill="#e4cbb6"/><path d="M243 225h117m-117 21h97m-97 21h108m-108 21h79" stroke="#bd9b83" stroke-width="5" stroke-linecap="round"/><rect x="242" y="313" width="92" height="48" rx="4" fill="#ead9c7"/><path d="M254 344q18-25 38 0 18-25 31 0" fill="none" stroke="#ab765b" stroke-width="4"/><path d="m365 239 34 15-71 140-29 12 3-32z" fill="#ab765b"/><path d="m365 239 17-28q8-11 19-5t5 17l-15 31" fill="#443a35"/><path d="m327 394 19-10-17-9z" fill="#443a35"/>`
    },
    "people-culture": {
      colors: ["#e9d7c6", "#ae7962", "#473b36"],
      drawing: `<circle cx="230" cy="195" r="34" fill="#bd9278"/><circle cx="300" cy="170" r="39" fill="#d9ad91"/><circle cx="372" cy="195" r="34" fill="#a97861"/><path d="M172 294q5-56 58-56t58 56v42H172zm70-20q6-66 58-66t58 66v62H242zm70 20q5-56 58-56t58 56v42h-116z" fill="#473b36"/><path d="M253 296q22-30 47-5l20 18 21-18q22-20 37-1l-44 53h-42z" fill="#d9ad91"/><path d="m280 311 21 19 21-19" fill="none" stroke="#fff2e4" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/><path d="M207 365h186" stroke="#ae7962" stroke-width="4" stroke-linecap="round"/>`
    },
    materials: {
      colors: ["#e3ddca", "#7d8b6c", "#454538"],
      drawing: `<circle cx="300" cy="247" r="103" fill="#d2d6bd"/><path d="M302 348q-4-90 51-154" fill="none" stroke="#596c50" stroke-width="8" stroke-linecap="round"/><path d="M312 258q-6-52-54-68 2 47 54 68m31-38q36-44 80-31-21 44-80 31m-47 78q-40-35-79-20 24 40 79 20" fill="#7d8b6c"/><path d="M220 359h160v39H220z" fill="#bdad91"/><path d="M220 369h160m-142 0v20m30-20v20m30-20v20m30-20v20m30-20v20" stroke="#f4eddd" stroke-width="3"/><circle cx="395" cy="328" r="31" fill="#f4eddd"/><path d="M395 306v44m-22-22h44m-37-15 30 30m0-30-30 30" stroke="#7d8b6c" stroke-width="4" stroke-linecap="round"/>`
    }
  };

  const escapeXml = (text) => text.replace(/[<>&'"]/g, (character) => ({
    "<": "&lt;",
    ">": "&gt;",
    "&": "&amp;",
    "'": "&apos;",
    "\"": "&quot;"
  })[character]);

  const titleLines = (title) => {
    const words = title.split(" ");
    const lines = [];
    let line = "";
    words.forEach((word) => {
      const next = line ? `${line} ${word}` : word;
      if (next.length > 23 && line) {
        lines.push(line);
        line = word;
      } else {
        line = next;
      }
    });
    if (line) lines.push(line);
    return lines;
  };

  const makeVacancyImage = (vacancy) => {
    const illustration = illustrations[vacancy.artwork];
    const [paper, accent, ink] = illustration.colors;
    const title = titleLines(vacancy.title)
      .map((line, index) => `<tspan x="56" dy="${index === 0 ? 0 : 43}">${escapeXml(line)}</tspan>`)
      .join("");
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="750" viewBox="0 0 600 750">
      <defs>
        <linearGradient id="paper" x2="1" y2="1"><stop stop-color="${paper}"/><stop offset="1" stop-color="#f6eee5"/></linearGradient>
        <linearGradient id="foot" x2="0" y2="1"><stop stop-color="${ink}" stop-opacity="0"/><stop offset=".23" stop-color="${ink}" stop-opacity=".83"/><stop offset="1" stop-color="${ink}"/></linearGradient>
        <pattern id="grain" width="34" height="34" patternUnits="userSpaceOnUse"><path d="M0 17h34M17 0v34" stroke="${ink}" stroke-opacity=".035"/></pattern>
      </defs>
      <rect width="600" height="750" fill="url(#paper)"/>
      <rect width="600" height="750" fill="url(#grain)"/>
      <path d="M77 443V251c0-133 100-197 223-197s223 64 223 197v192" fill="${accent}" opacity=".13"/>
      <path d="M95 444V252c0-120 87-177 205-177s205 57 205 177v192" fill="none" stroke="${ink}" stroke-opacity=".12" stroke-width="2"/>
      <circle cx="478" cy="112" r="35" fill="#fff9f1" opacity=".58"/>
      <path d="M65 47h470" stroke="${ink}" stroke-opacity=".22"/>
      <text x="66" y="72" fill="${ink}" font-family="Arial,sans-serif" font-size="12" font-weight="600" letter-spacing="3">VELORA  /  CAREERS</text>
      <g>${illustration.drawing}</g>
      <rect y="468" width="600" height="282" fill="url(#foot)"/>
      <path d="M56 529h46" stroke="${accent}" stroke-width="3"/>
      <text x="56" y="510" fill="${paper}" opacity=".92" font-family="Arial,sans-serif" font-size="13" font-weight="600" letter-spacing="2.4">${escapeXml(vacancy.team.toUpperCase())}</text>
      <text x="56" y="571" fill="#fffaf4" font-family="Georgia,serif" font-size="39" letter-spacing="-1.2">${title}</text>
      <text x="56" y="714" fill="${paper}" opacity=".78" font-family="Arial,sans-serif" font-size="11" font-weight="600" letter-spacing="2.5">MAKE SOMETHING MEANINGFUL</text>
      <path d="M56 685h488" stroke="#fffaf4" stroke-opacity=".26"/>
      <rect x="17" y="17" width="566" height="716" rx="2" fill="none" stroke="#fffaf4" stroke-opacity=".55"/>
    </svg>`;
    return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
  };

  const grid = document.querySelector("[data-vacancy-grid]");
  if (grid) {
    vacancies.forEach((vacancy) => {
      const card = document.createElement("a");
      card.className = "vacancy-tile";
      card.href = `vacancy.html?role=${encodeURIComponent(vacancy.slug)}`;
      card.setAttribute("aria-label", `${vacancy.title} — view role details`);
      card.setAttribute("role", "listitem");

      const image = document.createElement("img");
      image.className = "vacancy-artwork";
      image.src = vacancy.poster || makeVacancyImage(vacancy);
      image.alt = `Illustrated vacancy poster for ${vacancy.title}, ${vacancy.team}`;
      image.width = 600;
      image.height = 750;
      image.decoding = "async";
      card.append(image);
      grid.append(card);
    });
  }

  const detail = document.querySelector("[data-vacancy-detail]");
  if (!detail) return;

  const vacancy = vacancies.find((item) => item.slug === new URLSearchParams(location.search).get("role"));
  const element = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  };
  const listSection = (heading, items) => {
    const section = element("section", "vacancy-detail-section");
    section.append(element("h2", "", heading));
    const list = element("ul", "vacancy-detail-list");
    items.forEach((item) => list.append(element("li", "", item)));
    section.append(list);
    return section;
  };

  detail.replaceChildren();
  if (!vacancy) {
    detail.append(
      element("p", "eyebrow", "A place to grow"),
      element("h1", "", "Role not found."),
      element("p", "vacancy-detail-lead", "That vacancy may have moved. Explore all of the roles on our vacancies page."),
      Object.assign(element("a", "text-link", "Back to all vacancies ↗"), { href: "careers.html" })
    );
    return;
  }

  document.title = `${vacancy.title} — Vacancies — Velora`;
  const description = document.querySelector('meta[name="description"]');
  if (description) description.content = vacancy.introduction;

  const backLink = element("a", "vacancy-back-link", "← All vacancies");
  backLink.href = "careers.html";
  detail.append(
    backLink,
    element("p", "eyebrow", vacancy.team),
    element("h1", "", vacancy.title),
    element("p", "vacancy-detail-lead", vacancy.introduction)
  );

  const overview = element("section", "vacancy-detail-section");
  overview.append(element("h2", "", "About the role"), element("p", "", vacancy.overview));
  detail.append(overview, listSection("What you’ll do", vacancy.responsibilities), listSection("What you’ll bring", vacancy.qualities));

  const note = element("aside", "vacancy-detail-note");
  note.append(
    element("h2", "", "A note about recruitment"),
    element("p", "", "This is an illustrative role profile. Recruitment is not currently open, and this website does not accept applications, CVs, or identity documents.")
  );
  detail.append(note);
})();
