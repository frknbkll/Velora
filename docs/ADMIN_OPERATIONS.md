# Fashion shop operations

Open **Admin → Shop operations** after restarting `python py/app/server.py` (or the normal Velora launcher). The server creates the commerce table in the existing SQLite database without replacing accounts or catalog records.

## First setup

1. Create or review product galleries and color photos in Products.
2. In Shop operations → Inventory, add warehouses, stores and supplier locations.
3. Allocate each product's stock explicitly by size, color and location. The first variant replaces that product's legacy shared-stock count with the matrix total. Do not copy the entire shared count into every size. Use the same color names and sizes as the product options.
4. Set a safety threshold and replenishment target for each location record. SKU and internal barcode values are generated consistently for a product/color/size across locations. These are internal identifiers, not registered GS1/EAN codes.
5. In Products, select multiple products (optionally filtered by collection) to update price, publication and seasonal tags. Save a measurement guide to make it available in storefront product options. Existing product galleries can include size-chart images.
6. Staff access applies to existing administrator accounts. An owner can assign another administrator as warehouse staff or manager. Self-demotion is blocked. Warehouse accounts receive fulfillment data only; managers can edit catalog/pricing and process returns. Business/security settings and staff assignments require owner access.

## Orders and returns

Orders are entered manually for registered customers, with one or more stock-location variant lines. Creation reserves available inventory atomically; partial shipments record quantities and carrier references. Mark delivery only after all items ship. Print selected packing slips or address labels from the dispatch desk.

Return eligibility starts on recorded delivery. Each order retains the return window that applied at creation (default 30 days). Returns record condition, reason and resolution; only unworn items return to available stock. Exchanges reserve the replacement and create a new fulfillment order. Refund decisions remain pending external payment settlement. Store-credit amounts are recorded in the ledger; this does not create a redeemable checkout balance.

Sales reports show recorded order merchandise value for trailing 1/7/30-day periods and the preceding matching period, variant sales and return rates. Exchanges carry zero incremental revenue. Replenishment shows 30-day units and recommends the larger of the configured target or recent demand, less stock. In-app stock attention checks every minute while the admin page is active. Refresh retrieves current data; concurrent edits are rejected rather than overwritten.

## Integration boundaries

This local server has no connected payment processor, carrier API, supplier/retail POS integration or server-side checkout. Therefore it does not purchase carrier postage, send external low-stock notifications, settle refunds, redeem credits, synchronize external warehouse systems or automatically import webshop orders. Location balances are synchronized within Velora's database and aggregate into catalog stock. Storefront bag checks respect configured size/color availability but are not a checkout reservation.

Size guides support measurement text and existing gallery images. Seasonal tags are metadata, not a separate discount-rules engine. Reports are based on recorded merchandise values, excluding tax/shipping and actual payment settlement. The generic state table serializes updates with SQLite transactions; large-scale commerce needs normalized records, pagination and external service integrations before production use.

## Verification

- `python -m unittest discover -s py/tests -p 'test_*py/app/server.py'`
- `python py/tests/run-commerce-browser.py` (requires the project's Chrome test harness to start successfully)

Commerce tests cover transactional stock reservation, duplicate/expired returns, partial dispatch, exchanges, stale revisions, CSRF and role boundaries. Browser tests use disposable accounts and a temporary database, never the live database.
