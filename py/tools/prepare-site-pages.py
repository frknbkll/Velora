"""Wire public metadata, brand icons and optimized static image sources.

This edits html/ templates only; live product metadata and sitemaps are
rendered from the current published catalog by the server.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys

import seo


def image_manifest():
    source = (ROOT / "js/product-responsive-images.js").read_text(encoding="utf-8")
    return json.JSONDecoder().raw_decode(source.split("window.VeloraResponsiveImages =", 1)[1].lstrip())[0]


def image_sizes(source, attrs):
    if attrs.get("sizes"):
        return attrs["sizes"]
    if source.startswith("assets/team/"):
        return "(max-width: 650px) 90vw, (max-width: 1000px) 42vw, 28vw"
    return "(max-width: 760px) 100vw, 50vw"


class Images(HTMLParser):
    def __init__(self, manifest):
        super().__init__(convert_charrefs=True)
        self.manifest = manifest
        self.edits = []
        self.count = 0
        self.hero_picture = False

    def handle_starttag(self, tag, pairs):
        if tag == "picture":
            self.hero_picture = "hero-visual" in dict(pairs).get("class", "").split()
            return
        if tag not in {"img", "source"}:
            return
        attrs = dict(pairs)
        if tag == "source" and (self.hero_picture or "assets/hero-founders" in attrs.get("srcset", "") or attrs.get("data-original-src") == "assets/hero-founders-8k.jpg"):
            source = "assets/hero-founders-8k.jpg"
            responsive = self.manifest.get(source)
            if not responsive:
                return
            attrs.update({"srcset": responsive["srcset"], "type": "image/webp", "data-original-src": source})
        elif tag == "img":
            source = attrs.get("data-original-src") or attrs.get("src", "")
            if "hero-image" in attrs.get("class", "").split() and source.startswith("assets/hero-founders"):
                source = "assets/hero-founders-8k.jpg"
            responsive = self.manifest.get(source)
            if not responsive:
                return
            attrs.update({"data-original-src": source, "src": responsive["src"], "srcset": responsive["srcset"],
                          "sizes": image_sizes(source, attrs), "width": str(responsive["width"]), "height": str(responsive["height"])})
            attrs.setdefault("decoding", "async")
        else:
            return
        encoded = " ".join(key if value is None else f'{key}="{escape(value, quote=True)}"' for key, value in attrs.items())
        self.edits.append((self.get_starttag_text(), f"<{tag} {encoded} />"))
        self.count += 1

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        if tag == "picture":
            self.hero_picture = False


def prepare(path, public_url, manifest):
    original = path.read_text(encoding="utf-8")
    html = seo.replace_metadata(original, seo.page_metadata(path.name, public_url))
    if seo.ASSET_START not in html:
        html = html.replace("</head>", "    " + seo.favicon_markup() + "\n  </head>", 1)
    else:
        start = html.index(seo.ASSET_START)
        end = html.index(seo.ASSET_END, start) + len(seo.ASSET_END)
        html = html[:start] + seo.favicon_markup() + html[end:]
    parser = Images(manifest)
    parser.feed(html)
    for before, after in parser.edits:
        html = html.replace(before, after, 1)
    needs_images = bool(parser.count or path.name in {"index.html", "product.html", "careers.html", "vacancy.html", "admin.html"})
    html = re.sub(r'\s*<script src="(?:/?js/)?(?:product-responsive-images|site-images)\.js(?:\?v=\d+)?" defer></script>', "", html)
    if needs_images:
        # Both helpers run before page-specific scripts, while defer still waits
        # for the complete document. Already optimized static srcsets need no JS.
        helpers = '    <script src="/js/product-responsive-images.js?v=4" defer></script>\n    <script src="/js/site-images.js?v=1" defer></script>\n'
        first_script = re.search(r"(?m)^\s*<script\b", html)
        if first_script:
            html = html[:first_script.start()] + "\n" + helpers + html[first_script.start():]
        else:
            html = html.replace("</head>", helpers + "  </head>", 1)
    if html != original:
        path.write_text(html, encoding="utf-8", newline="")
    return parser.count


def main():
    manifest = image_manifest()
    public_url = seo.load_public_url(ROOT)
    pages = sorted((ROOT / "html").glob("*.html"))
    count = sum(prepare(page, public_url, manifest) for page in pages)
    print(f"Prepared metadata and icons for {len(pages)} pages; optimized {count} static image sources. Public origin: {public_url}")


if __name__ == "__main__":
    main()
