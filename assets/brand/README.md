# Velora launch artwork

These assets are deterministic brand graphics. They use Velora's existing cream,
dark olive and terracotta palette and its bundled Playfair Display and DM Sans
fonts. They do not introduce new product photography or product claims.

Rebuild from the project root with:

```powershell
py -3.14 tools/prepare-brand-assets.py
```

The generator needs Pillow. Python 3.14 in this workspace already has it installed;
any Python runtime with Pillow can run the same script. No network, account data
or API key is used.

| Asset | Size / purpose |
| --- | --- |
| `favicon.svg` | Self-contained 512 × 512 vector monogram; font outlines included |
| `favicon.ico` | 16 × 16, 32 × 32 and 48 × 48 browser icons in one file |
| `favicon-16x16.png` | 16 × 16 fallback |
| `favicon-32x32.png` | 32 × 32 fallback |
| `apple-touch-icon.png` | 180 × 180, full square background for device rounding |
| `icon-192.png` | 192 × 192 manifest icon |
| `icon-512.png` | 512 × 512 manifest icon |
| `icon-maskable-512.png` | 512 × 512 full-bleed icon with a smaller central mark |
| `og-velora.png` | 1200 × 630 sharing card |

Suggested sharing-image alt text: **Velora wordmark and v. monogram in cream and
dark olive, with the words “Considered style. Your own point of view.”**

Font licenses and attribution are retained at `assets/fonts/Playfair-Display-OFL.txt`
and `assets/fonts/DM-Sans-OFL.txt`. The SVG contains paths rather than font links,
and the raster artwork needs no external fonts when served.
