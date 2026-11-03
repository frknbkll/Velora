# Velora accounts and administration

The storefront, registration, login, customer account and admin portal run together using Python 3.10 or newer. No package installation is needed.

On Windows, double-click **`Start-Velora.cmd`** to open the correct sign-in page. It reuses the server when it is already running; otherwise it starts Velora on port 8000. Keep the terminal window open while using the site.

To start the server manually, open a terminal in this project folder:

```powershell
python server.py
```

Visit [Velora](http://127.0.0.1:8000), [Create an account](http://127.0.0.1:8000/register.html), or [Sign in](http://127.0.0.1:8000/login.html). Use this server rather than opening HTML files directly or using a static Live Server: account actions need the API on the same origin. The existing collection still works as a static showcase.

If a preview on port 5500 says it cannot connect to accounts, use the **Open Velora sign in** link or the Windows launcher. Live Server serves the page but cannot run the account API. The launcher does not create accounts or change passwords.

## Create your administrator

In a second terminal, run:

```powershell
python server.py --create-admin
```

Enter your name, email, and a password of 12–128 characters. The password input is hidden. Use a separate email if you already registered a customer account. There is no default password, public admin registration, or role selector. Sign in using that account, then visit [Admin portal](http://127.0.0.1:8000/admin.html).

The admin portal shows product/customer counts, stock alerts, registered customers, and recent catalog activity. The Products section supports creating, editing, duplicating, and deleting products. Published changes appear in the storefront; drafts stay hidden. Order processing, checkout, email verification, and email password recovery are outside this implementation.

## Manage the collection

- **Add product:** enter a name, designer, category, euro price and description. Choose available sizes and a primary color. A unique SKU is generated if you leave it blank.
- **AI product draft:** upload a cover photo and select **Generate product from photo**. On click, only that image is sent to OpenAI. AI suggests the name, category, visible color, description, price and sizes; Velora assigns a SKU when saved, uses **Velora Studio** as the designer label, and starts stock at an estimated 10 units. The product remains an unpublished draft. Price, sizes and stock are suggestions—not facts from the photo—so confirm them before publishing. AI also suggests one complementary color; to add it as a product variant, upload a separate photo for that color. Review and edit all details before saving.
- **AI description draft:** select **Generate draft with AI** to create an editable description from the product name, category, primary color and cover photo. Review and edit the result; it is not saved until you save the product.
- Both AI actions require the server-side `VELORA_OPENAI_API_KEY` environment variable. Optionally set `VELORA_OPENAI_MODEL` (defaults to `gpt-4o-mini`). Never put the key in browser code, source control or chat; restart the server after configuring it. Generation is limited to 30 requests per administrator per hour.
- **Product photos:** upload up to 12 JPEG, PNG or WebP images per product, up to 8 MB each. Choose the cover, reorder photos, or remove them from the gallery. The storefront has previous/next controls and thumbnails on product cards and in quick view. Additional photos belong to the primary color; existing alternate-color photos are preserved.
- **Stock:** enter a total quantity across the product's sizes and colors, or leave it blank when stock is not tracked. Zero shows Sold out and disables adding the product to the bag. Quantities of 1–5 appear in the low-stock view. Existing products start with untracked stock. The bag is a preview and does not reserve or decrement stock.
- **Visibility:** publish a product to show it in the collection, or save it as a draft. Duplicated products start as drafts with a new SKU.
- **Delete and restore:** Move to trash removes a product from the storefront after confirmation. Select Trash in the visibility filter to restore it as a draft. Trashed products stay deleted after a server restart. Shared image files are retained so other products that use them keep working.
- **Find and export:** search names, SKUs, designers and categories; filter visibility and stock; sort the list; or export the active catalog to CSV.
- **Activity:** see who created, edited, duplicated, trashed or restored a product. The portal displays the latest 100 changes.

Products keep their identity when you change their names or cover photos, so saved wishlist and shopping-bag entries can follow those edits. Published products and their categories, designers, photos and sizes are loaded from the saved catalog by the storefront.

## Account behavior and data

See [Account security](SECURITY.md) for authenticator setup, recovery codes, session controls, security events, and backup requirements.

- New registrations are customer accounts and collect first name, last name, city and country. The storefront header shows the signed-in customer's name. Customers can update their profile details and change their password from the account page.
- Existing accounts keep their credentials; the first and last name are populated from the existing account name when the server starts. City and country remain blank until the customer provides them.
- Password changes require the current password and invalidate the account's other sessions.
- Customer sessions expire after 12 hours, or up to 30 days when “Remember me” is selected. Administrator sessions expire after 30 minutes without authenticated activity or eight hours overall. Sign out invalidates the current session immediately.
- Passwords use salted PBKDF2-SHA256 hashes with 600,000 iterations. Session cookies are HttpOnly and SameSite=Lax. Session tokens are hashed in the database.
- APIs enforce administrator permissions on the server. Mutations require JSON and the matching website origin; authenticated mutations also require the session's CSRF token. Login and registration attempts are throttled.
- Data persists in `.velora/velora.sqlite3`; the matching private security key is `.velora/security.key`, and uploaded product images are stored in `assets/uploads/`. Back up the entire `.velora` folder and uploads while the server is stopped. The database and security key must be backed up and restored together. Private account data must stay out of source control and public hosting. The included server does not expose it over HTTP.
- `product-catalog.json` seeds new products at startup. Existing database edits are preserved when the server restarts.

Use `python server.py --port 8080` for a different port. `--database PATH` selects a separate SQLite database; pass the same path to `--create-admin` when using it. Bind to a specific IP with `--host`; wildcard hosts are intentionally rejected so the server can validate incoming hosts and origins.

## Hosting

This is a working **local development server**. Python's `http.server` is [not recommended for production hosting](https://docs.python.org/3/library/http.server.html). Before accepting real customer accounts on the internet, move the handlers to a maintained application server/framework, serve the site and API over HTTPS, configure trusted hosts/proxy behavior and durable private database storage, and arrange backups. `--secure-cookies` marks session cookies Secure and expects an HTTPS origin; it does not provide TLS by itself and should only be used behind a deliberately configured trusted HTTPS endpoint. The server does not trust forwarded headers.

The implementation follows the core safeguards in the [OWASP authentication guidance](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html) and [CSRF prevention guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).

## Verification

Privacy controls, optional device storage, age confirmation and account deletion are described in [COMPLIANCE.md](COMPLIANCE.md). Public operator fields are edited in **Admin → Business details**. Missing values remain clearly marked until entered; no registration number or address has been invented. The server automatically adds the new schema when started. Existing accounts retain their sign-in credentials.

```powershell
python -m unittest discover -s tests -p test_auth_server.py -v
python -m unittest discover -s tests -p test_catalog_server.py -v
python -m unittest discover -s tests -p test_security_server.py -v
python -m unittest discover -s tests -p test_privacy_server.py -v
```

The checks run against a temporary database and local HTTP server. They cover registration, sign-in/sign-out, session expiry, password changes, role and CSRF enforcement, throttling, catalog edits, input validation and private-file protection. They do not change your real accounts or catalog.

For browser verification on this Windows setup with Chrome installed:

```powershell
python tests/run-account-browser.py
python tests/run-account-connection.py
python tests/run-catalog-browser.py
python tests/run-security-browser.py
python tests/run-privacy-browser.py
python tests/run-account-privacy-browser.py
python tests/run-business-browser.py
```

This checks the account and admin forms, storefront updates, and responsive layouts against a disposable database. Reports and preview screenshots are saved in `tmp/`.
