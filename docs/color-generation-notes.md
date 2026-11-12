# Product color images

## Pose revisions — 3 November 2026

Product color variants now use revised poses: walking, three-quarter views,
crossed ankles, hands at the waist, sleeve adjustments and relaxed standing
positions. Seated looks retain seated compositions. Garment-only previews use
rearranged flat lays. Five newer single-photo products also have revised poses.

The active replacements and generation source paths are recorded in
`json/creative/product-pose-revisions.json`. Revised assets use `-pose-v2` filenames; original
files are retained. The live admin catalog's uploaded galleries and color
variants are included. A product-image-field backup is saved under
`output/imagegen/product-poses-20261103/` when updating the live catalog.

The sage Ivory Tie-Neck Set uses a fully buttoned blouse for full chest coverage.

Generated with the built-in imagegen tool. Original product photographs are preserved.
Each product has its original color and two generated alternate colors.
The second alternate adds a new pose, or a different arrangement for garment-only
previews. The full prompt set for these is in data/creative/color-pose-prompts.json.

Prompt template:

> Use case: identity-preserve. Edit target: supplied original product photo of PRODUCT.
> Recolor only the main garment to COLOR (HEX), including matching trousers when
> coordinated. Preserve contrasting layers, model identity, face, skin, hair, pose,
> clothing design, fabric texture, folds, background, lighting, accessories, shoes,
> and original framing. One photorealistic ecommerce color variant photograph;
> no text or collage.

For matching modest sets, the coordinating hijab changes with the garment.
For denim looks, only the denim changes color. For striped pajamas, only the
colored stripes change; the white stripes remain white.

Image mappings are in product-color-images.js. Generated assets are saved in
assets/gallery/colors/. The first entry always points to the untouched original.

The image tool rejected five model-photo edits. These alternate colors use
garment-only studio previews: Rose-Stripe Pajama Set, Taupe Satin Lounge Set,
Midnight Satin Gown, Champagne Satin Evening Dress, and Champagne Halter Gown.
For these, the prompt uses the source only as a clothing-design reference and
requests the same garments laid flat on a warm white studio surface, in the
alternate color from the mapping, with no person, body, mannequin, props, or text.
Original photographs remain the first selectable color.
