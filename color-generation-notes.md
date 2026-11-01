# Product color images

Generated with the built-in imagegen tool. Original product photographs are preserved.
Each product has its original color and two generated alternate colors.
The second alternate adds a new pose, or a different arrangement for garment-only
previews. The full prompt set for these is in color-pose-prompts.json.

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
