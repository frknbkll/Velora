# Velora accounts and administration

Public metadata, favicons, sharing images and the dynamic sitemap are documented
in [LAUNCH_SETUP.md](LAUNCH_SETUP.md). The configured public origin is
`https://velora.org`; local previews remain noindex.

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

The active preview bag is shared between the collection and product pages using tab session storage, including when visitors choose necessary storage only. Optional saved looks remember the bag and wishlist between visits. Withdrawing optional storage removes the long-term copy and wishlist while preserving the active session bag; **Clear device data** also empties the session bag. Prices are shown in euros throughout.

Use **Shop operations → Inventory** to allocate stock to a product's listed sizes and colors. Unknown options are rejected. Before removing or renaming an option with stock or an outstanding order, resolve its inventory and order records first; catalog edits cannot silently detach those records. Product editors warn before discarding unsaved changes. On mobile, the Admin menu exposes every section and product actions remain visible in each product row.

## Department folders and colleague access

Open **Admin portal → Velora accounts** using an owner administrator account. Select **Create Velora account**, enter the colleague's name, an unused `@velora.com` work address and a starting password, then choose the department and access role. This creates a website sign-in account for the work address; it does not create an email mailbox. Passwords are hashed and never returned by the API. The colleague can change the starting password after signing in.

Public registration always creates a customer account, including registration using an `@velora.com` address. Gmail, Hotmail and other public/customer accounts stay under **Customers** and never appear in colleague folder access. Only explicitly provisioned Velora accounts are listed in **Velora accounts**. Existing customer accounts are never silently converted when a colleague address is already in use. Existing administrator credentials continue working. During migration, existing owner-assigned workspace profiles on `@velora.com` are retained as Velora accounts; other customer email domains do not gain colleague privileges.

Choose **Colleague** for the intranet and assigned folders, **Store manager** for collection and commerce tools, **Warehouse** for fulfillment, or **Full control** for owner administration and management of every shared folder, including Finance and HR. Only owners can create colleagues or change these roles. Disabling an account prevents sign-in and revokes its sessions; role changes also revoke existing sessions. Self-demotion and removing the last enabled owner are prevented.

**Velora accounts** is the single place to change colleague roles and folder access. The former role editor under **Shop operations → Staff** links here; its old role-changing API no longer accepts changes.

Enabled colleagues can open **My account → Team workspace**. Shared folders include a company library and nine department folders. The company library references the existing public website images and current published product catalog without moving the storefront originals. It also accepts private uploads when a colleague has explicit Manage access. Website originals are read-only here and remain public on the storefront.

For colleagues with assigned access, Finance and Human Resources require both a matching primary department and an explicit folder permission. An explicitly granted **Full control** role includes Read and Manage access to all department folders. Other department folders require explicit grants for regular colleagues; company-library Read access is included for enabled colleagues and administrators. Full control is an owner-assigned privilege, never something obtained by entering a work-looking email during registration.

Private uploads are stored in `.velora/shared-folders/` (next to the selected database when using `--database`). They are not published under `assets/`. Every list, upload, download, preview and deletion checks current permissions, including existing sessions after revocation. Supported uploads are JPG, PNG, WebP, GIF, PDF, UTF-8 TXT/CSV and DOCX/XLSX/PPTX, up to 8 MB each. Notes support up to 20,000 characters. Only raster images have inline previews; documents are downloaded as attachments. Back up the shared-folder directory together with the database and security key while the server is stopped.

Each department's starter library contains six country briefs and a CSV work tracker covering the Netherlands, France, United Kingdom, Germany, United Arab Emirates and Türkiye. File names begin with **Sample**. Use the folder search to find a country, select **Read note** to open a brief, or download the tracker. These are draft working templates with ownership and dates ready to complete.

To add this starter library to another initialized database, run `python tools/seed-department-documents.py --database PATH`. It adds 63 private files, preserves existing files and permissions, and records the import in the security log. Repeating the command skips existing examples and respects examples deliberately deleted through the intranet. The server does not automatically recreate them at startup.

## Seasonal discount codes

Open **Admin → Discount codes** as an owner or store manager. Start with Black Friday, Halloween, Christmas, New Year, Summer or a custom campaign, then enter a unique code, percentage or fixed EUR reduction, optional minimum spend and optional start/end times. Templates open as inactive drafts; save and activate the intended offer when ready. Codes can be edited or deactivated later. Warehouse accounts and customers cannot manage codes.

Customers can apply or remove a code in the shopping-bag preview. Velora validates the code, dates, stock, minimum spend and current published product prices on the server; client-provided totals are not accepted. Changing the bag or continuing through the preview revalidates the offer. Discounts are capped at the subtotal. The existing checkout remains a no-charge demonstration: applying or previewing a code does not create an order, collect payment or consume a redemption.

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
python -m unittest discover -s tests -p test_shared_folders.py -v
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
python tests/run-shared-folders.py
```

This checks the account and admin forms, storefront updates, and responsive layouts against a disposable database. Reports and preview screenshots are saved in `tmp/`.
