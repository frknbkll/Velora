"""Public page metadata and discovery files, independent of request Host input."""
from __future__ import annotations

from functools import lru_cache
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, quote, urlencode, urlsplit
from xml.etree import ElementTree as ET
from project_paths import source_file

BRAND_IMAGE = "assets/brand/og-velora.png"
BRAND_IMAGE_ALT = "Velora wordmark and v. monogram in cream and dark olive, with the words Considered style. Your own point of view."
PRIVATE_PAGES = {"account.html", "admin.html", "intranet.html"}
UTILITY_PAGES = PRIVATE_PAGES | {"login.html", "register.html", "unsubscribe.html", "404.html"}
PAGES = {
    "index.html": ("Velora | The Opening Fashion Collection", "Explore Velora's fashion concept collection, shaped by four friends. Discover considered looks, color previews, our story and the free design studio."),
    "our-story.html": ("Our Story | Four Friends, One Fashion House | Velora", "Discover the story behind Velora: four friends, four points of view, and a shared approach to personal style."),
    "founders.html": ("Meet the Four Founders | Velora", "Meet Beyza, Derya, Luna and Victoria, the four creative points of view behind the Velora fashion concept."),
    "team.html": ("Meet the Team | The People Behind Velora", "Explore Velora's illustrative team, from creative direction and fashion design to digital experience and people leadership."),
    "careers.html": ("Careers & Illustrative Role Profiles | Velora", "Explore the kinds of creative, retail and digital roles imagined for Velora. These are illustrative profiles; recruitment is not currently open."),
    "contact.html": ("Contact & Support | Velora", "Find published Velora contact details and open support chat for help with the website, your account or the concept collection."),
    "shopping-info.html": ("Shopping Information, Sizing & Preview Prices | Velora", "Read how Velora's concept collection, illustrative euro prices, sizing information and preview shopping bag work. No orders or payments are processed."),
    "faq.html": ("Frequently Asked Questions | Velora", "Find answers about Velora's fashion showcase, product previews, account features, sizing information and support."),
    "reviews.html": ("Community Reviews & Experiences | Velora", "Read experiences shared by Velora account holders or leave your own review. Purchases are not verified and reviews are not verified-buyer endorsements."),
    "velora-school.html": ("Velora School | Free Fashion Design Studio & Workshop", "Try the free Velora 3D design studio and introductory fashion workshop. Explore planned courses and earn a non-accredited workshop completion certificate."),
    "business-details.html": ("Business & Customer-Service Details | Velora", "Read the business identity and customer-service information currently published for the Velora website."),
    "privacy.html": ("Privacy Policy | Velora", "Read how Velora handles account, support and review information, active shopping bags and optional saved looks."),
    "terms.html": ("Terms of Service | Velora", "Read the terms for using Velora's fashion showcase, website accounts, community features and design previews."),
    "refund-policy.html": ("Refund & Returns Information | Velora", "Read the current status of returns and refunds for the Velora concept showcase. The website does not process purchases or payments."),
    "cookie-policy.html": ("Cookie & Browser Storage Policy | Velora", "Understand Velora's essential sign-in, active-bag and support storage, optional saved looks and privacy preference controls."),
    "product.html": ("Explore a Collection Piece | Velora", "Explore a piece from Velora's fashion concept collection, including photos, color previews, sizes and illustrative euro prices."),
    "vacancy.html": ("Illustrative Role Profile | Velora Careers", "Explore an illustrative role profile from the Velora concept team. Recruitment and applications are not currently open."),
    "account.html": ("Your Account | Velora", "Manage your Velora account, security preferences and website data."),
    "admin.html": ("Admin Studio | Velora", "Manage the Velora collection, operations and colleague access."),
    "intranet.html": ("Team Workspace | Velora", "The private Velora colleague workspace and department folders."),
    "login.html": ("Sign In | Velora", "Sign in to your Velora account using your email address and password."),
    "register.html": ("Create an Account | Velora", "Create a customer account to use Velora's account and community features."),
    "unsubscribe.html": ("Email Preferences | Velora", "Read the current status of Velora email updates and unsubscribe information."),
    "404.html": ("Page Not Found | Velora", "This Velora page could not be found. Return to the collection or explore the website navigation."),
}

META_START = "<!-- velora:page-metadata -->"
META_END = "<!-- /velora:page-metadata -->"
ASSET_START = "<!-- velora:brand-assets -->"
ASSET_END = "<!-- /velora:brand-assets -->"


def validate_public_url(value):
    if not value:
        return ""
    if not isinstance(value, str) or len(value) > 300:
        raise ValueError("Set publicUrl to the HTTPS origin of the public website.")
    parsed = urlsplit(value.strip())
    try:
        valid_port = parsed.port in (None, 443)
    except ValueError:
        valid_port = False
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or
            parsed.path not in ("", "/") or parsed.query or parsed.fragment or not valid_port or
            not re.fullmatch(r"[A-Za-z0-9.-]+", parsed.hostname) or "." not in parsed.hostname or
            any(character.isspace() for character in value)):
        raise ValueError("Set publicUrl to an HTTPS origin without a path, credentials, query or fragment.")
    return f"https://{parsed.hostname.lower()}"


def load_public_url(root, override=None):
    if override is not None:
        return validate_public_url(override)
    config = source_file(root, "json/config", "site-config.json")
    if not config.is_file():
        return ""
    settings = json.loads(config.read_text(encoding="utf-8"))
    if not isinstance(settings, dict):
        raise ValueError("site-config.json must contain the public website settings.")
    return validate_public_url(settings.get("publicUrl", ""))


def live_origin(public_url, host, secure):
    return bool(public_url and secure and host.lower() in {urlsplit(public_url).netloc, urlsplit(public_url).netloc + ":443"})


@lru_cache(maxsize=8)
def _vacancies(path, modified):
    source = Path(path).read_text(encoding="utf-8")
    string = r'("(?:[^"\\]|\\.)*")'
    pattern = r"slug:\s*" + string + r".*?title:\s*" + string + r".*?introduction:\s*" + string
    result = {}
    for slug, title, description in re.findall(pattern, source, re.S):
        slug, title, description = (json.loads(value) for value in (slug, title, description))
        if re.fullmatch(r"[a-z0-9-]{1,100}", slug):
            result[slug] = {"title": title, "description": description, "image": f"assets/careers/{slug}.jpg"}
    return result


def vacancies(root):
    path = source_file(root, "js", "careers.js")
    return _vacancies(str(path), path.stat().st_mtime_ns) if path.is_file() else {}


def page_metadata(page, public_url, *, product=None, vacancy=None, indexable=True):
    title, description = PAGES.get(page, ("Velora", "Explore the world of Velora."))
    path = "/" if page == "index.html" else "/" + page
    image, image_alt = BRAND_IMAGE, BRAND_IMAGE_ALT
    if page == "product.html":
        indexable = bool(product and product.get("published") and indexable)
        if product:
            title = f"{product['name']} | Velora"
            description = product.get("description") or f"Explore {product['name']} from the Velora concept collection."
            path += "?" + urlencode({"id": product["id"]})
            image, image_alt = product["image"], product["name"]
    elif page == "vacancy.html":
        indexable = bool(vacancy and indexable)
        if vacancy:
            title = f"{vacancy['title']} | Illustrative Role | Velora"
            description = f"{vacancy['description']} Illustrative role profile; recruitment is not open."
            path += "?" + urlencode({"role": vacancy["slug"]})
            image, image_alt = vacancy["image"], f"Illustrative {vacancy['title']} role at Velora"
    indexable = bool(indexable and public_url and page not in UTILITY_PAGES and page in PAGES)
    canonical = public_url + path if public_url and page not in UTILITY_PAGES and (page not in {"product.html", "vacancy.html"} or product or vacancy) else ""
    image_path = "/" + quote(image.lstrip("/"), safe="/-._~")
    return {"title": title, "description": description[:320], "canonical": canonical,
            "image": public_url + image_path if public_url else image_path,
            "imageAlt": image_alt, "brandImage": image == BRAND_IMAGE,
            "robots": "index, follow, max-image-preview:large" if indexable else "noindex, nofollow"}


def metadata_markup(metadata):
    attr = lambda value: escape(str(value), quote=True)
    lines = [META_START, f"<title>{escape(metadata['title'])}</title>",
             f'<meta name="description" content="{attr(metadata["description"])}" />',
             f'<meta name="robots" content="{attr(metadata["robots"])}" />']
    if metadata["canonical"]:
        lines.append(f'<link rel="canonical" href="{attr(metadata["canonical"])}" />')
    properties = {"og:site_name": "Velora", "og:type": "website", "og:title": metadata["title"],
                  "og:description": metadata["description"], "og:image": metadata["image"],
                  "og:image:alt": metadata["imageAlt"]}
    if metadata["canonical"]:
        properties["og:url"] = metadata["canonical"]
    if metadata["brandImage"]:
        properties.update({"og:image:width": "1200", "og:image:height": "630", "og:image:type": "image/png"})
    lines.extend(f'<meta property="{name}" content="{attr(value)}" />' for name, value in properties.items())
    for name, value in {"twitter:card": "summary_large_image", "twitter:title": metadata["title"],
                        "twitter:description": metadata["description"], "twitter:image": metadata["image"],
                        "twitter:image:alt": metadata["imageAlt"]}.items():
        lines.append(f'<meta name="{name}" content="{attr(value)}" />')
    lines.append(META_END)
    return "\n    ".join(lines)


def replace_metadata(html, metadata):
    if "</head>" not in html.lower():
        return html
    head_end = html.lower().index("</head>")
    head, body = html[:head_end], html[head_end:]
    block = metadata_markup(metadata)
    if META_START in head and META_END in head:
        start = head.index(META_START)
        end = head.index(META_END, start) + len(META_END)
        return head[:start] + block + head[end:] + body
    head = re.sub(r"<title\b[^>]*>.*?</title\s*>\s*", "", head, flags=re.I | re.S)
    head = re.sub(r'<meta\b(?=[^>]*(?:name|property)\s*=\s*[\"\'](?:description|robots|og:[^\"\']+|twitter:[^\"\']+)[\"\'])[^>]*>\s*', "", head, flags=re.I | re.S)
    head = re.sub(r'<link\b(?=[^>]*rel\s*=\s*[\"\']canonical[\"\'])[^>]*>\s*', "", head, flags=re.I | re.S)
    return head.rstrip() + "\n    " + block + "\n  " + body


def favicon_markup():
    return "\n    ".join([ASSET_START,
        '<link rel="icon" href="/assets/brand/favicon.ico" sizes="16x16 32x32 48x48" />',
        '<link rel="icon" href="/assets/brand/favicon.svg" type="image/svg+xml" sizes="any" />',
        '<link rel="apple-touch-icon" href="/assets/brand/apple-touch-icon.png" sizes="180x180" />',
        '<link rel="manifest" href="/site.webmanifest" />', ASSET_END])


def html_metadata(server, page, query, host):
    """Only a currently published record may supply product sharing metadata."""
    from server import public_product
    params = parse_qs(query, keep_blank_values=True)
    product = vacancy = None
    status = 200
    if page == "product.html" and "id" in params:
        ids = params["id"]
        if len(ids) == 1 and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", ids[0]):
            with server.connect() as connection:
                row = connection.execute("SELECT * FROM products WHERE id=? AND published=1 AND deleted_at IS NULL", (ids[0],)).fetchone()
            if row:
                product = public_product(row)
        if not product:
            status = 404
    elif page == "vacancy.html" and "role" in params:
        roles = params["role"]
        role = vacancies(server.root).get(roles[0]) if len(roles) == 1 else None
        if role:
            vacancy = {**role, "slug": roles[0]}
        else:
            status = 404
    result = page_metadata(page, server.public_url, product=product, vacancy=vacancy,
                           indexable=live_origin(server.public_url, host, server.secure_cookies))
    return result, status


def sitemap(server):
    namespace = "http://www.sitemaps.org/schemas/sitemap/0.9"
    ET.register_namespace("", namespace)
    root = ET.Element(f"{{{namespace}}}urlset")
    if server.public_url:
        paths = ["/" if page == "index.html" else "/" + page for page in PAGES
                 if page not in UTILITY_PAGES | {"product.html", "vacancy.html"} and source_file(server.root, "html", page).is_file()]
        paths += ["/vacancy.html?" + urlencode({"role": slug}) for slug in vacancies(server.root)
                  if source_file(server.root, "html", "vacancy.html").is_file()]
        with server.connect() as connection:
            rows = connection.execute("SELECT id FROM products WHERE published=1 AND deleted_at IS NULL ORDER BY id").fetchall()
        if source_file(server.root, "html", "product.html").is_file():
            paths += ["/product.html?" + urlencode({"id": row["id"]}) for row in rows]
        for path in paths:
            item = ET.SubElement(root, f"{{{namespace}}}url")
            ET.SubElement(item, f"{{{namespace}}}loc").text = server.public_url + path
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def robots(server, host):
    if not live_origin(server.public_url, host, server.secure_cookies):
        return b"User-agent: *\nDisallow: /\n"
    return ("User-agent: *\nAllow: /\nDisallow: /api/\nAllow: /api/catalog\nAllow: /api/business-details\nAllow: /api/reviews\n" +
            f"Sitemap: {server.public_url}/sitemap.xml\n").encode("utf-8")
