"""Build Velora's code-native favicon and sharing artwork from bundled fonts.

Run with ``py -3.14 tools/prepare-brand-assets.py`` on this checkout, or any
Python with Pillow installed. No network, live database or credentials are used.
The favicon SVG contains outlines from the bundled OFL Playfair Display font,
so it needs no external font request. Originals and other assets are untouched.
"""
from __future__ import annotations

import json
from pathlib import Path
import struct

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
DESTINATION = ROOT / "assets" / "brand"
FONT = ROOT / "assets" / "fonts" / "playfair-display-variable.ttf"
ITALIC = ROOT / "assets" / "fonts" / "playfair-display-italic-variable.ttf"
SANS = ROOT / "assets" / "fonts" / "dm-sans-variable.ttf"
PAPER, INK, OLIVE, ACCENT, MUTED, LINE = "#f6f2ec", "#292621", "#303128", "#a64e37", "#81796f", "#ded7ce"


class FontOutlines:
    """Read the simple TrueType glyphs used in the v. monogram, without an SDK."""

    def __init__(self, path):
        self.data = path.read_bytes()
        self.tables = {}
        for i in range(self.u16(4)):
            tag, _, offset, _ = struct.unpack_from(">4sIII", self.data, 12 + i * 16)
            self.tables[tag.decode("ascii")] = offset
        self.long_locations = self.i16(self.tables["head"] + 50) == 1
        self.metrics_count = self.u16(self.tables["hhea"] + 34)

    def u16(self, offset):
        return struct.unpack_from(">H", self.data, offset)[0]

    def i16(self, offset):
        return struct.unpack_from(">h", self.data, offset)[0]

    def u32(self, offset):
        return struct.unpack_from(">I", self.data, offset)[0]

    def glyph_id(self, character):
        cmap = self.tables["cmap"]
        codepoint = ord(character)
        for index in range(self.u16(cmap + 2)):
            subtable = cmap + self.u32(cmap + 4 + index * 8 + 4)
            if self.u16(subtable) == 12:
                for group in range(self.u32(subtable + 12)):
                    start, end, glyph = struct.unpack_from(">III", self.data, subtable + 16 + group * 12)
                    if start <= codepoint <= end:
                        return glyph + codepoint - start
            elif self.u16(subtable) == 4:
                segments = self.u16(subtable + 6) // 2
                end_base = subtable + 14
                start_base = end_base + segments * 2 + 2
                delta_base = start_base + segments * 2
                range_base = delta_base + segments * 2
                for segment in range(segments):
                    start = self.u16(start_base + segment * 2)
                    end = self.u16(end_base + segment * 2)
                    if start <= codepoint <= end:
                        delta = self.i16(delta_base + segment * 2)
                        range_slot = range_base + segment * 2
                        offset = self.u16(range_slot)
                        if not offset:
                            return (codepoint + delta) & 0xffff
                        glyph = self.u16(range_slot + offset + (codepoint - start) * 2)
                        return (glyph + delta) & 0xffff if glyph else 0
        raise ValueError("The bundled font needs a supported Unicode cmap")

    def glyph(self, character):
        glyph_id = self.glyph_id(character)
        loca = self.tables["loca"]
        offset = self.u32(loca + glyph_id * 4) if self.long_locations else self.u16(loca + glyph_id * 2) * 2
        start = self.tables["glyf"] + offset
        contour_count = self.i16(start)
        if contour_count <= 0:
            raise ValueError("The monogram expects simple, non-empty glyphs")
        bbox = struct.unpack_from(">hhhh", self.data, start + 2)
        end_points = [self.u16(start + 10 + index * 2) for index in range(contour_count)]
        count = end_points[-1] + 1
        cursor = start + 10 + contour_count * 2
        cursor += 2 + self.u16(cursor)
        flags = []
        while len(flags) < count:
            flag = self.data[cursor]
            cursor += 1
            repeat = 1
            if flag & 8:
                repeat += self.data[cursor]
                cursor += 1
            flags.extend([flag] * repeat)
        axes = []
        for short_bit, same_bit in ((2, 16), (4, 32)):
            position, coordinates = 0, []
            for flag in flags:
                if flag & short_bit:
                    delta = self.data[cursor] * (1 if flag & same_bit else -1)
                    cursor += 1
                elif flag & same_bit:
                    delta = 0
                else:
                    delta = self.i16(cursor)
                    cursor += 2
                position += delta
                coordinates.append(position)
            axes.append(coordinates)
        paths, previous = [], 0
        for end in end_points:
            points = [(axes[0][i], axes[1][i], bool(flags[i] & 1)) for i in range(previous, end + 1)]
            expanded = []
            for index, point in enumerate(points):
                expanded.append(point)
                following = points[(index + 1) % len(points)]
                if not point[2] and not following[2]:
                    expanded.append(((point[0] + following[0]) / 2, (point[1] + following[1]) / 2, True))
            first = next(i for i, point in enumerate(expanded) if point[2])
            ordered = expanded[first:] + expanded[:first]
            ordered.append(ordered[0])
            path = [f"M{ordered[0][0]:g},{ordered[0][1]:g}"]
            index = 1
            while index < len(ordered):
                point = ordered[index]
                if point[2]:
                    path.append(f"L{point[0]:g},{point[1]:g}")
                    index += 1
                else:
                    following = ordered[index + 1]
                    path.append(f"Q{point[0]:g},{point[1]:g} {following[0]:g},{following[1]:g}")
                    index += 2
            paths.append(" ".join(path) + " Z")
            previous = end + 1
        advance = self.u16(self.tables["hmtx"] + min(glyph_id, self.metrics_count - 1) * 4)
        return paths, bbox, advance


def monogram_svg():
    font = FontOutlines(FONT)
    v_paths, v_box, advance = font.glyph("v")
    dot_paths, dot_box, _ = font.glyph(".")
    # Bring the dot closer to the v, keeping the combined outlines centered.
    dot_x = advance - 20
    left, right = min(v_box[0], dot_x + dot_box[0]), max(v_box[2], dot_x + dot_box[2])
    bottom, top = min(v_box[1], dot_box[1]), max(v_box[3], dot_box[3])
    scale = min(340 / (right - left), 300 / (top - bottom))
    x = (512 - (right - left) * scale) / 2 - left * scale
    y = (512 - (top - bottom) * scale) / 2 + top * scale
    body = f'<path d="{" ".join(v_paths)}"/><path transform="translate({dot_x} 0)" d="{" ".join(dot_paths)}"/>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">\n'
            f'  <title>Velora</title>\n  <metadata>Playfair Display outlines; source font under SIL OFL, assets/fonts/Playfair-Display-OFL.txt</metadata>\n'
            f'  <rect width="512" height="512" rx="104" fill="{OLIVE}"/>\n'
            f'  <g fill="{PAPER}" transform="translate({x:g} {y:g}) scale({scale:g} {-scale:g})">{body}</g>\n</svg>\n')


def font(path, size):
    return ImageFont.truetype(str(path), size)


def draw_monogram(size, *, maskable=False, rounded=False):
    factor = 4
    canvas = Image.new("RGBA", (size * factor, size * factor), (0, 0, 0, 0) if rounded else OLIVE)
    draw = ImageDraw.Draw(canvas)
    if rounded:
        draw.rounded_rectangle((0, 0, size * factor - 1, size * factor - 1), radius=round(size * factor * .203), fill=OLIVE)
    face = font(FONT, round(size * factor * (.74 if maskable else .91)))
    bounds = draw.textbbox((0, 0), "v.", font=face)
    x = (size * factor - (bounds[2] - bounds[0])) / 2 - bounds[0]
    y = (size * factor - (bounds[3] - bounds[1])) / 2 - bounds[1]
    draw.text((round(x), round(y)), "v.", font=face, fill=PAPER)
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def letterspaced(draw, position, value, face, color, spacing):
    x, y = position
    for character in value:
        draw.text((round(x), y), character, font=face, fill=color)
        x += draw.textlength(character, font=face) + spacing


def sharing_image():
    scale = 2
    canvas = Image.new("RGB", (1200 * scale, 630 * scale), PAPER)
    draw = ImageDraw.Draw(canvas)
    def text(position, value, size, color=INK, face=FONT):
        draw.text(tuple(int(v * scale) for v in position), value, font=font(face, size * scale), fill=color)
    letterspaced(draw, (86 * scale, 62 * scale), "THE OPENING COLLECTION", font(SANS, 14 * scale), MUTED, 3 * scale)
    text((78, 125), "velora", 174)
    word_width = draw.textlength("velora", font=font(FONT, 174 * scale)) / scale
    text((83 + word_width, 151), "®", 24, MUTED, SANS)
    draw.line((86 * scale, 346 * scale, 143 * scale, 346 * scale), fill=ACCENT, width=2 * scale)
    text((83, 376), "Considered style.", 49)
    text((84, 438), "Your own point of view.", 38, ACCENT, ITALIC)
    text((86, 554), "FASHION, THOUGHTFULLY COMPOSED.", 14, MUTED, SANS)
    draw.rounded_rectangle((832 * scale, 62 * scale, 1114 * scale, 568 * scale), radius=8 * scale, fill=OLIVE)
    mark = draw_monogram(250 * scale)
    canvas.paste(mark, (848 * scale, 186 * scale), mark)
    draw.line((878 * scale, 510 * scale, 1068 * scale, 510 * scale), fill="#77786a", width=scale)
    return canvas.resize((1200, 630), Image.Resampling.LANCZOS)


def main():
    if not DESTINATION.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Brand assets must stay in the workspace")
    DESTINATION.mkdir(parents=True, exist_ok=True)
    (DESTINATION / "favicon.svg").write_text(monogram_svg(), encoding="utf-8")
    for size in (16, 32):
        draw_monogram(size, rounded=True).save(DESTINATION / f"favicon-{size}x{size}.png", optimize=True)
    draw_monogram(256, rounded=True).save(DESTINATION / "favicon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    for size, filename in ((180, "apple-touch-icon.png"), (192, "icon-192.png"), (512, "icon-512.png")):
        draw_monogram(size).convert("RGB").save(DESTINATION / filename, optimize=True)
    draw_monogram(512, maskable=True).convert("RGB").save(DESTINATION / "icon-maskable-512.png", optimize=True)
    sharing_image().save(DESTINATION / "og-velora.png", optimize=True)
    report = []
    for asset in sorted(DESTINATION.iterdir()):
        if asset.suffix not in {".svg", ".png", ".ico"}:
            continue
        if asset.suffix == ".svg":
            dimensions = [512, 512]
        else:
            with Image.open(asset) as image:
                dimensions = list(image.size)
                if asset.suffix == ".ico":
                    assert image.ico.sizes() == {(16, 16), (32, 32), (48, 48)}
        report.append({"path": asset.relative_to(ROOT).as_posix(), "dimensions": dimensions, "bytes": asset.stat().st_size})
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
