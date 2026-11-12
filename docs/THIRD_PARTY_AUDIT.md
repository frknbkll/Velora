# Browser third-party audit

Reviewed 11 November 2026. Scope: root HTML/JavaScript/CSS, bundled browser libraries, referenced local images and font delivery. This is a dependency and data-flow inventory, not a penetration test or an endorsement of future integrations.

| Component | Delivery / data flow | Decision |
| --- | --- | --- |
| Site JavaScript and CSS | First-party local files; account/catalog requests use the site's account server | Retained. Account request bodies are not copied to another origin to recover static previews |
| Nayuki QR Code Generator 1.8.0 | `js/vendor/qrcodegen.js`; generates MFA QR modules in the browser | Retained, MIT notice in file. No external QR API receives the setup key. Release metadata is in `json/vendor/qrcodegen-source.json` |
| Three.js 0.180.0, OrbitControls and GLTFExporter | Four local ES modules in `assets/vendor/three/`; used by the school 3D studio, with local model export | Retained, MIT licence bundled. Official archive hash and all four module bytes verified on 11 November; documented relative-import adjustment and per-file hashes in `json/vendor/three-source.json`. No remote CDN or model service receives studio designs |
| DM Sans / Playfair Display | Three local variable TTF font files plus two SIL Open Font License 1.1 notices in `assets/fonts/` | Self-hosted; Google Fonts preconnects/stylesheet requests removed from page delivery. Official Google Fonts repository URLs and SHA-256 hashes are in `json/vendor/font-sources.json` |
| Product, founder and team images | First-party asset paths; no remote image service in page delivery | Retained as supplied/generated assets. Publication rights are a separate unresolved review; see `IMAGE_RIGHTS.md` |
| Analytics, advertising, tag managers | No enabled SDK or pixel | Absent. Cookie choices do not load or enable any |
| Social embeds / payment / CAPTCHA | No enabled external embed or SDK | Absent |
| Support chat | First-party browser code and `/api/support/` endpoints on the same account server | Retained. No third-party chat SDK; customer messages and guest sessions use the local application database |
| Newsletter / marketing email | No mailing service | No email collection or simulated subscription confirmation |
| Browser storage | Essential session cookie and privacy choice; optional wishlist/bag persistence | Optional persistence defaults off; refusing does not prevent account use |
| Hosting / server logs | Local Python account server. Public provider not configured | Operator must document actual provider, retention and agreements before public deployment |

External policy-reference links are navigation only: they are not embedded scripts. Visiting them creates a request to the destination site under its own practices. AI image-generation tools were used during asset creation; those tools are not runtime SDKs embedded in the website.

## Recheck when adding a dependency

Record the exact version and source, licence, fields collected, recipients, storage region, purpose and retention. Verify whether it executes before a visitor's choice and how it stops after withdrawal. Avoid putting account identifiers, email addresses or MFA secrets in analytics events or URLs. Update this inventory and the visitor-facing policy together with the code.
