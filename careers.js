(() => {
  "use strict";

  const vacancies = [
    {
      slug: "sales-client-experience-associate",
      photoAlt: "A sales and client experience associate seated at a desk providing client support, working on a laptop with a notebook and clothing samples nearby.",
      title: "Sales & Client Experience Associate",
      team: "Client experience",
      introduction: "Make every conversation feel considered, warm, and distinctly Velora.",
      overview: "The Sales & Client Experience Associate helps make discovering Velora feel personal. This role brings thoughtful styling guidance together with attentive service, creating a welcoming experience from the first question to the final details.",
      experience: "This is an illustrative early-career profile. Customer-facing work, retail, hospitality, styling, or volunteering can all provide useful experience; transferable skills and a thoughtful approach matter more than a specific number of years.",
      certifications: "No certificate is required for this illustrative role. Optional study in customer service, personal styling, retail sales, or visual merchandising can help build confidence; relevant learning already in progress is welcome.",
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
      photoAlt: "A marketing and social media coordinator in a team meeting, three colleagues around an oak office table discussing campaign ideas with a laptop and moodboard.",
      title: "Marketing & Social Media Coordinator",
      team: "Brand & community",
      introduction: "Bring the Velora point of view to life across stories, campaigns, and community.",
      overview: "This role helps translate the Velora brand into thoughtful, consistent communication. You will connect creative ideas with a clear content plan and help make every interaction feel recognizably human.",
      experience: "This illustrative role suits an early-career marketer with a small portfolio, relevant coursework, personal projects, or internship experience. Practical examples of planning content and learning from audience response are valuable.",
      certifications: "No certificate is required. Optional learning could include Meta Blueprint, Google Analytics, or a short course in social content strategy; candidates planning to pursue one of these may mention it.",
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
      photoAlt: "A fashion design assistant actively designing clothing at a studio worktable, drawing a garment sketch with pencil beside fabric swatches and a dress form.",
      title: "Fashion & Design Assistant",
      team: "Creative studio",
      introduction: "Help shape the pieces, details, and visual language of each collection.",
      overview: "The Fashion & Design Assistant supports the early ideas and practical details behind a collection. It is a hands-on creative role for someone curious about how research, fabric, fit, and styling come together.",
      experience: "This illustrative assistant role is suitable for a recent graduate, student, career changer, or emerging designer. Coursework, a personal portfolio, sewing projects, studio assistance, or other hands-on creative work can demonstrate relevant experience.",
      certifications: "A formal certificate is not required. Optional study in fashion design, garment construction, pattern cutting, textiles, or CAD tools such as CLO 3D is useful; planned training is welcome.",
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
      photoAlt: "An ecommerce and merchandising coordinator standing in the office talking naturally to a colleague beside a clothing rail and desk.",
      title: "E-commerce & Merchandising Coordinator",
      team: "Digital storefront",
      introduction: "Make the online collection easy to explore, understand, and love.",
      overview: "This coordinator keeps the digital collection considered and clear. The role connects product information, visual presentation, and customer journeys so each piece is represented consistently online.",
      experience: "This illustrative early-career role welcomes experience from retail, product administration, digital content, or personal e-commerce projects. Accuracy, organization, and examples of improving how information is presented are especially useful.",
      certifications: "No certificate is required. Optional learning in e-commerce operations, Shopify, product merchandising, or Google Analytics can support the role; candidates may also describe courses they plan to take.",
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
      photoAlt: "A customer care specialist seated at a desk speaking to a customer through a phone held to her ear, laptop open beside her.",
      title: "Customer Care Specialist",
      team: "Client experience",
      introduction: "Turn customer questions into moments of clarity and care.",
      overview: "The Customer Care Specialist supports customers with thoughtful, useful answers. This role helps people feel heard while sharing common themes with the team so the experience can keep improving.",
      experience: "This illustrative role suits someone with experience in customer support, hospitality, retail, or community service, including transferable or volunteer experience. Clear writing, patience, and calm problem-solving are key.",
      certifications: "No formal certificate is required. Optional training in customer experience, conflict resolution, accessibility, or common CRM tools can be helpful; in-progress learning is welcome.",
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
      photoAlt: "A production and sourcing assistant talking on a phone held to her ear and taking handwritten notes in a notebook at an office desk.",
      title: "Production & Sourcing Assistant",
      team: "Product & production",
      introduction: "Help bring thoughtful materials and well-made ideas together.",
      overview: "This assistant supports the research and coordination behind product development. The focus is on keeping information organized and helping the team ask considered questions about materials, samples, and production.",
      experience: "This illustrative assistant role welcomes relevant study, internships, practical administration, or transferable coordination experience. Familiarity with textiles, supplier communication, product samples, or careful record-keeping is useful but not essential.",
      certifications: "No certificate is required. Optional courses in textiles, garment production, responsible sourcing, or supply-chain basics may help; candidates planning relevant study are encouraged to say so.",
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
      photoAlt: "A visual content producer busy creating visual layouts on a desktop PC, seated at a workstation, side three-quarter view showing her face and the monitor with abstract photo-editing panels.",
      title: "Visual Content Producer",
      team: "Creative studio",
      introduction: "Create imagery that makes the feeling behind each piece visible.",
      overview: "The Visual Content Producer helps plan and deliver the imagery that introduces Velora collections. This role brings a strong visual point of view together with careful shoot preparation and asset organization.",
      experience: "This illustrative role is suited to an emerging photographer, videographer, stylist, or content creator. A portfolio, personal projects, assisting on shoots, or experience organizing digital assets can demonstrate relevant skills.",
      certifications: "A certificate is not required when practical work can be shown. Optional training in photography, lighting, video editing, accessibility, or Adobe tools may help; planned learning is welcome.",
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
      photoAlt: "A female retail operations coordinator showing something on an open laptop to her colleague, both looking at the screen together at a boutique office desk.",
      title: "Retail Operations Coordinator",
      team: "Retail & operations",
      introduction: "Make the thoughtful details of the Velora experience work smoothly.",
      overview: "This role helps coordinate the practical work that supports a considered retail experience. It connects people, product information, and day-to-day processes so the team can focus on customers.",
      experience: "This illustrative coordinator role welcomes experience in retail, hospitality, scheduling, stock support, or team administration. Examples of dependable follow-through and improving a routine are more important than a particular career path.",
      certifications: "No certificate is required. Optional learning in retail operations, inventory management, workplace health and safety, or first aid can be useful; candidates may include certifications they are working toward.",
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
      photoAlt: "A product copywriter working at a laptop at an oak office desk, with a cream blouse and handwritten product notes beside the laptop.",
      title: "Product Copywriter",
      team: "Brand & storytelling",
      introduction: "Give every piece a description that is useful, warm, and true to its details.",
      overview: "The Product Copywriter turns product knowledge into clear, inviting language. This role balances the personality of the Velora voice with practical details customers need to make informed choices.",
      experience: "This illustrative role welcomes writing samples from work, study, a personal blog, volunteer projects, or other portfolios. Experience editing product information, web copy, newsletters, or accessible content is useful.",
      certifications: "No writing certificate is required. Optional short courses in copywriting, editing, SEO, or accessible content can support development; planned study is welcome alongside strong writing samples.",
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
      photoAlt: "A people and culture assistant welcoming a new teammate as they walk through a sunlit fashion office corridor, chatting naturally while carrying a notebook.",
      title: "People & Culture Assistant",
      team: "People & culture",
      introduction: "Help create a welcoming, thoughtful experience for the people behind Velora.",
      overview: "This assistant supports the everyday details that help a small team work well together. The role is grounded in discretion, organization, and care for clear, welcoming communication.",
      experience: "This illustrative assistant role welcomes transferable experience in administration, education, customer support, volunteering, or people coordination. Careful organization, discretion, and respectful communication are essential.",
      certifications: "No HR certificate is required. Optional study could include an introductory people-practice or employment-law course; candidates considering a recognized HR qualification may mention their plans.",
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
      photoAlt: "A sustainability and materials coordinator examining woven natural textile swatches at a studio table with an open materials sample book.",
      title: "Sustainability & Materials Coordinator",
      team: "Product & impact",
      introduction: "Bring care and curiosity to the materials and choices behind each collection.",
      overview: "The Sustainability & Materials Coordinator helps the team understand product materials and document what is known. The role favors careful research and transparent communication over unsupported claims.",
      experience: "This illustrative coordinator role welcomes research, study, sourcing, product, or data-organization experience. Examples of careful evidence review and clear communication are useful, including academic or personal projects.",
      certifications: "No sustainability certificate is required. Optional learning in textile materials, life-cycle assessment, responsible sourcing, or sustainability reporting can be relevant; candidates may describe a course they plan to pursue.",
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
      if (window.VeloraImageSources) window.VeloraImageSources.apply(image, `assets/careers/${vacancy.slug}.jpg`, "(max-width: 650px) 90vw, 33vw");
      else image.src = `assets/careers/${vacancy.slug}.jpg`;
      image.alt = vacancy.photoAlt;
      image.width = 600;
      image.height = 750;
      image.decoding = "async";
      image.loading = "lazy";
      card.append(image);
      const caption = document.createElement("span");
      caption.className = "vacancy-caption";
      const team = document.createElement("span");
      team.className = "vacancy-caption-team";
      team.textContent = vacancy.team;
      const title = document.createElement("span");
      title.className = "vacancy-caption-title";
      title.textContent = vacancy.title;
      caption.append(team, title);
      card.append(caption);
      grid.append(card);
    });
  }

  const detail = document.querySelector("[data-vacancy-detail]");
  if (!detail) return;

  const hrContact = {
    name: "Leila Demir",
    role: "HR Specialist",
    email: "leila.demir@lenora.com",
    phone: "+31 6 45 98 46 70",
    photo: "assets/team/leila-demir.jpg",
  };
  const vacancy = vacancies.find((item) => item.slug === new URLSearchParams(location.search).get("role"));
  const element = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  };
  const listSection = (heading, items, className) => {
    const section = element("section", `vacancy-detail-section ${className}`);
    section.append(element("h2", "", heading));
    const list = element("ul", "vacancy-detail-list");
    items.forEach((item) => list.append(element("li", "", item)));
    section.append(list);
    return section;
  };
  const textSection = (heading, text, className) => {
    const section = element("section", `vacancy-detail-section ${className}`);
    section.append(element("h2", "", heading), element("p", "", text));
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
  const hero = element("section", "vacancy-detail-hero");
  const heroCopy = element("div", "vacancy-detail-hero-copy");
  heroCopy.append(
    element("p", "eyebrow", vacancy.team),
    element("h1", "", vacancy.title),
    element("p", "vacancy-detail-lead", vacancy.introduction)
  );
  const heroImage = element("img", "vacancy-detail-image");
  if (window.VeloraImageSources) window.VeloraImageSources.apply(heroImage, `assets/careers/${vacancy.slug}.jpg`, "(max-width: 760px) 100vw, 50vw");
  else heroImage.src = `assets/careers/${vacancy.slug}.jpg`;
  heroImage.alt = vacancy.photoAlt;
  heroImage.width = 600;
  heroImage.height = 750;
  heroImage.decoding = "async";
  hero.append(heroCopy, heroImage);

  const overview = element("section", "vacancy-detail-section");
  overview.append(element("h2", "", "About the role"), element("p", "", vacancy.overview));
  overview.classList.add("vacancy-detail-section--overview");
  const content = element("div", "vacancy-detail-grid");
  content.append(
    overview,
    listSection("What you’ll do", vacancy.responsibilities, "vacancy-detail-section--responsibilities"),
    listSection("What you’ll bring", vacancy.qualities, "vacancy-detail-section--qualities"),
    textSection("Relevant experience", vacancy.experience, "vacancy-detail-section--experience"),
    textSection("Certificates & continued learning", vacancy.certifications, "vacancy-detail-section--certifications")
  );

  const contact = element("section", "vacancy-contact vacancy-hr-contact");
  contact.setAttribute("aria-labelledby", "vacancy-hr-heading");
  const contactImage = element("img", "vacancy-hr-contact-photo");
  if (window.VeloraImageSources) window.VeloraImageSources.apply(contactImage, hrContact.photo, "(max-width: 650px) 40vw, 250px");
  else contactImage.src = hrContact.photo;
  contactImage.alt = `Illustrative portrait of ${hrContact.name}`;
  contactImage.width = 768;
  contactImage.height = 960;
  contactImage.loading = "lazy";
  contactImage.decoding = "async";
  const contactCopy = element("div", "vacancy-hr-contact-copy");
  contactCopy.append(
    element("p", "vacancy-contact-role", "YOUR PEOPLE & CULTURE CONTACT"),
    element("h2", "", "Questions about the role?")
  );
  contactCopy.lastElementChild.id = "vacancy-hr-heading";
  const contactDescription = element("p", "", "Leila can help with questions about the role and the experience or learning that may be relevant.");
  const contactDetails = element("dl", "vacancy-hr-contact-details");
  [
    ["Name", hrContact.name],
    ["Role", hrContact.role],
    ["Email", hrContact.email],
    ["Phone", hrContact.phone],
  ].forEach(([label, value]) => {
    const row = element("div", "");
    row.append(element("dt", "", label));
    const detailValue = element("dd", "");
    if (label === "Email") {
      const link = element("a", "", value);
      link.href = `mailto:${value}`;
      detailValue.append(link);
    } else if (label === "Phone") {
      const link = element("a", "", value);
      link.href = `tel:${value.replace(/[^\d+]/g, "")}`;
      detailValue.append(link);
    } else {
      detailValue.textContent = value;
    }
    row.append(detailValue);
    contactDetails.append(row);
  });
  contactCopy.append(contactDescription, contactDetails);
  contact.append(contactImage, contactCopy);

  const note = element("aside", "vacancy-detail-note");
  note.append(
    element("h2", "", "A note about recruitment"),
    element("p", "", "This is an illustrative role profile. Recruitment is not currently open, and this website does not accept applications, CVs, or identity documents.")
  );
  content.append(contact, note);
  detail.append(backLink, hero, content);
})();
