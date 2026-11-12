"""Install reviewed generated photos for the thirteen new arrivals.

Reads the saved generation manifest; does not call any external service.
Keeps original cover photos and updates only galleries and alternate colors.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

import json
from pathlib import Path
import re
import sqlite3

from PIL import Image


def main():
    records = json.loads((ROOT / 'json/reports/imagegen/new-arrival-variations.json').read_text(encoding='utf-8'))
    draft_path = ROOT / 'json/reports/new-product-drafts.json'
    drafts = json.loads(draft_path.read_text(encoding='utf-8'))
    catalog_path = ROOT / 'json/catalog/product-catalog.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    mapping_path = ROOT / 'js/product-color-images.js'
    mapping_text = mapping_path.read_text(encoding='utf-8')
    mapping = json.loads(mapping_text.split('=', 1)[1].strip().rstrip(';'))
    by_slug = {}
    for record in records:
        by_slug.setdefault(record['slug'], []).append(record)
    updates = []
    for product in drafts['products']:
        slug = Path(product['image']).stem
        group = by_slug.get(slug, [])
        alternates = [r for r in group if r['name'] != product['base_color']]
        if len(alternates) != 2 or len({r['name'] for r in alternates}) != 2:
            raise ValueError(f'Expected two reviewed alternate colors for {slug}')
        for record in group:
            if not Path(record['path']).is_file():
                raise ValueError(f'Missing generated image for {slug}')
        updates.append((product, group))
    for product, group in updates:
        poses, colors = [], []
        for record in group:
            suffix = re.sub(r'[^a-z0-9]+', '-', record['name'].lower()).strip('-')
            relative = f"assets/gallery/new-arrivals/variants/{record['slug']}-{suffix}-pose.jpg"
            target = ROOT / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(record['path']) as photo:
                photo.convert('RGB').save(target, quality=92, subsampling=0)
            record['website_image'] = relative
            if record['name'] == product['base_color']:
                poses.append(relative)
            else:
                colors.append({'name': record['name'], 'hex': record['hex'], 'image': relative})
        product['images'] = [product['image'], *poses]
        product['color_variants'] = colors
        mapping[product['image']] = [
            {'name': product['base_color'], 'hex': product['color_hex'], 'image': product['image'], 'poses': poses},
            *colors,
        ]
        for existing in catalog['products']:
            if existing['id'] == product['id']:
                existing['images'] = product['images']
                existing['color_variants'] = colors
    database = ROOT / '.velora/velora.sqlite3'
    with sqlite3.connect(database) as connection:
        for product, _ in updates:
            cursor = connection.execute(
                'UPDATE products SET images=?,color_variants=? WHERE id=?',
                (json.dumps(product['images']), json.dumps(product['color_variants']), product['id']),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"Missing database product: {product['id']}")
    catalog_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    draft_path.write_text(json.dumps(drafts, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    mapping_path.write_text('// The first color always uses the untouched original product photo.\nwindow.veloraColorImages = '
                            + json.dumps(mapping, indent=2, ensure_ascii=False) + ';\n', encoding='utf-8')
    (ROOT / 'json/reports/imagegen/new-arrival-variations.json').write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Installed {len(records)} variations for {len(updates)} products.')


if __name__ == '__main__':
    main()
