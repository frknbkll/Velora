"""Transactional fashion operations, stored alongside the existing catalog."""
import json
import secrets
import sqlite3
from datetime import datetime, timezone, timedelta


def initialize(connection):
    connection.execute("CREATE TABLE IF NOT EXISTS commerce_state (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL)")
    connection.execute("INSERT OR IGNORE INTO commerce_state VALUES (1,?)", (json.dumps({"variants": [], "locations": ["Main warehouse"], "orders": [], "returns": [], "staff": {}, "guides": {}, "tags": {}, "returnDays": 30, "revision": 0}),))


def role(connection, user):
    row = connection.execute("SELECT data FROM commerce_state WHERE id=1").fetchone()
    return json.loads(row[0])["staff"].get(str(user["id"]), "owner") if row else "owner"


def handle(handler, method):
    from server import APIError, now_iso, public_product
    user = handler.require_user(admin=True, csrf=method == "POST")
    def fail(message):
        raise APIError(400, message)
    def text(value, label, maximum=200):
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            fail("Enter a valid " + label + ".")
        return value.strip()
    def number(value, label, maximum=1000000):
        if type(value) is not int or not 0 <= value <= maximum:
            fail(label + " must be a nonnegative whole number.")
        return value
    def find(rows, key):
        item = next((r for r in rows if r["id"] == key), None)
        if item is None:
            fail("The selected record no longer exists.")
        return item
    with handler.server.connect() as c:
        c.execute("BEGIN IMMEDIATE")
        handler.fresh_security_user(c, user, admin=True)
        s = json.loads(c.execute("SELECT data FROM commerce_state WHERE id=1").fetchone()[0])
        access = s["staff"].get(str(user["id"]), "owner")
        products = {p["id"]: public_product(p) for p in c.execute("SELECT * FROM products WHERE deleted_at IS NULL")}
        if method == "POST":
            p = handler.read_json()
            action = p.get("action")
            if not isinstance(action, str): fail("Choose a valid action.")
            if "product" in p and not isinstance(p["product"], str): fail("Select a valid product.")
            for key in ("customer", "user"):
                if key in p: number(p[key], key)
            for key in ("role", "condition", "resolution"):
                if key in p and not isinstance(p[key], str): fail("Choose a valid " + key + ".")
            allowed = {"owner": {"variant", "location", "bulk", "guide", "order", "ship", "deliver", "return", "staff", "settings"}, "manager": {"variant", "location", "bulk", "guide", "order", "ship", "deliver", "return", "settings"}, "warehouse": {"ship", "deliver"}}
            if action not in allowed.get(access, set()):
                raise APIError(403, "Your staff role does not permit this action.")
            if p.get("revision") != s["revision"]:
                raise APIError(409, "Another staff member changed these records. Refresh and try again.")
            if action == "location":
                name = text(p.get("name"), "location", 80)
                if name in s["locations"]: fail("That location already exists.")
                s["locations"].append(name)
            elif action == "variant":
                product = products.get(p.get("product"))
                if not product: fail("Select an active product.")
                size = text(p.get("size"), "size", 30)
                color = text(p.get("color"), "color", 80)
                location = p.get("location")
                if location not in s["locations"]: fail("Select a stock location.")
                existing = next((v for v in s["variants"] if (v["product"], v["size"].casefold(), v["color"].casefold(), v["location"]) == (product["id"], size.casefold(), color.casefold(), location)), None)
                v = existing or {"id": secrets.token_hex(8), "product": product["id"], "size": size, "color": color, "location": location}
                v.update(stock=number(p.get("stock"), "Stock"), threshold=number(p.get("threshold"), "Safety threshold"), target=number(p.get("target"), "Reorder target"), lot=text(p.get("lot", "Default"), "color lot", 80))
                if v["target"] < v["threshold"]: fail("Reorder target must be at least the safety threshold.")
                # A stable style/color/size code identifies the garment across locations.
                identity = product["id"] + "|" + color.casefold() + "|" + size.casefold()
                import hashlib
                v["sku"] = product["sku"] + "-" + hashlib.sha256(identity.encode()).hexdigest()[:10].upper()
                v["barcode"] = str(int(hashlib.sha256(identity.encode()).hexdigest()[:12], 16)).zfill(15)
                if not existing: s["variants"].append(v)
                total = sum(x["stock"] for x in s["variants"] if x["product"] == product["id"])
                c.execute("UPDATE products SET stock=?,updated_at=? WHERE id=?", (total, now_iso(), product["id"]))
            elif action == "bulk":
                ids = p.get("products")
                if not isinstance(ids, list) or not ids or len(ids) > 200 or any(not isinstance(i, str) or i not in products for i in ids): fail("Select up to 200 active products.")
                patch = {}
                if p.get("price") is not None:
                    value = p["price"]
                    if type(value) not in (float, int) or not 1 <= value <= 100000: fail("Enter a price from 1 to 100000 EUR.")
                    patch["price"] = round(value, 2)
                if p.get("published") is not None:
                    if type(p["published"]) is not bool: fail("Choose a valid visibility.")
                    patch["published"] = int(p["published"])
                for key in ids:
                    if patch:
                        c.execute("UPDATE products SET " + ",".join(k + "=?" for k in patch) + ",updated_at=? WHERE id=?", (*patch.values(), now_iso(), key))
                    s["tags"][key] = text(p.get("tag") or "Seasonal", "discount tag", 80)
                    handler.record_product_activity(c, user, "bulk update", products[key])
            elif action == "guide":
                if p.get("product") not in products: fail("Select a product.")
                s["guides"][p["product"]] = text(p.get("guide"), "size guide", 5000)
            elif action == "settings":
                days = number(p.get("days"), "Return window", 365)
                if days < 1: fail("Return window must be at least one day.")
                s["returnDays"] = days
            elif action == "staff":
                target = c.execute("SELECT * FROM users WHERE id=? AND role='admin'", (p.get("user"),)).fetchone()
                if not target or target["id"] == user["id"]: fail("Select another administrator account.")
                if p.get("role") not in {"owner", "manager", "warehouse"}: fail("Select a staff role.")
                s["staff"][str(target["id"])] = p["role"]
            elif action == "order":
                customer = c.execute("SELECT id,name,email FROM users WHERE id=? AND role='customer'", (p.get("customer"),)).fetchone()
                if not customer: fail("Select a registered customer.")
                lines = p.get("lines")
                if not isinstance(lines, list) or not 1 <= len(lines) <= 100: fail("Add 1 to 100 order lines.")
                order = {"id": secrets.token_hex(6).upper(), "customer": customer["id"], "customerName": customer["name"], "address": text(p.get("address"), "shipping address", 1000), "createdAt": now_iso(), "status": "incoming", "lines": [], "shipments": [], "returnDays": s["returnDays"]}
                for line in lines:
                    if not isinstance(line, dict): fail("Enter valid order lines.")
                    v = find(s["variants"], line.get("variant"))
                    qty = number(line.get("quantity"), "Quantity", 10000)
                    product = products.get(v["product"])
                    if not qty or qty > v["stock"] or not product: fail("Insufficient stock or unavailable product.")
                    v["stock"] -= qty
                    order["lines"].append({"id": secrets.token_hex(6), "variant": v["id"], "product": v["product"], "name": product["name"], "sku": v["sku"], "size": v["size"], "color": v["color"], "quantity": qty, "shipped": 0, "returned": 0, "priceCents": round(product["price"] * 100)})
                s["orders"].append(order)
            elif action in {"ship", "deliver"}:
                order = find(s["orders"], p.get("order"))
                if action == "ship":
                    line = find(order["lines"], p.get("line"))
                    qty = number(p.get("quantity"), "Shipment quantity")
                    if not qty or qty > line["quantity"] - line["shipped"]: fail("Shipment exceeds remaining quantity.")
                    tracking = text(p.get("tracking"), "carrier and tracking reference")
                    line["shipped"] += qty
                    order["shipments"].append({"line": line["id"], "quantity": qty, "tracking": tracking, "createdAt": now_iso()})
                    order["status"] = "shipped" if all(l["shipped"] == l["quantity"] for l in order["lines"]) else "processing"
                else:
                    if order["status"] != "shipped": fail("Ship every item before marking the order delivered.")
                    order["status"] = "delivered"
                    order["deliveredAt"] = now_iso()
            elif action == "return":
                order = find(s["orders"], p.get("order"))
                line = find(order["lines"], p.get("line"))
                if not order.get("deliveredAt"): fail("Returns require a delivered order.")
                deadline = datetime.fromisoformat(order["deliveredAt"].replace("Z", "+00:00")) + timedelta(days=order["returnDays"])
                if datetime.now(timezone.utc) > deadline: fail("This order is outside its return window.")
                qty = number(p.get("quantity"), "Return quantity")
                if not qty or qty > line["shipped"] - line["returned"]: fail("Return exceeds eligible quantity.")
                resolution = p.get("resolution")
                if resolution not in {"refund", "store credit", "exchange"}: fail("Choose a return resolution.")
                condition = p.get("condition")
                if condition not in {"unworn", "worn", "damaged"}: fail("Record the item condition.")
                r = {"id": secrets.token_hex(6), "order": order["id"], "line": line["id"], "product": line["product"], "quantity": qty, "resolution": resolution, "condition": condition, "reason": text(p.get("reason"), "return reason", 500), "amountCents": qty * line["priceCents"], "createdAt": now_iso(), "paymentStatus": "pending external settlement" if resolution == "refund" else "recorded"}
                if resolution == "exchange":
                    replacement = find(s["variants"], p.get("replacement"))
                    if replacement["product"] != line["product"] or replacement["stock"] < qty: fail("Choose an in-stock size or color of the same product.")
                    replacement["stock"] -= qty
                    exchange = {**order, "id": secrets.token_hex(6).upper(), "status": "incoming", "createdAt": now_iso(), "shipments": [], "lines": [{**line, "id": secrets.token_hex(6), "variant": replacement["id"], "sku": replacement["sku"], "size": replacement["size"], "color": replacement["color"], "quantity": qty, "shipped": 0, "returned": 0, "priceCents": 0}]}
                    exchange.pop("deliveredAt", None)
                    s["orders"].append(exchange)
                    r["exchangeOrder"] = exchange["id"]
                if condition == "unworn": find(s["variants"], line["variant"])["stock"] += qty
                line["returned"] += qty
                s["returns"].append(r)
            if action in {"order", "return"}:
                for key in {v["product"] for v in s["variants"]}:
                    c.execute("UPDATE products SET stock=?,updated_at=? WHERE id=?", (sum(v["stock"] for v in s["variants"] if v["product"] == key), now_iso(), key))
            s["revision"] += 1
            c.execute("UPDATE commerce_state SET data=? WHERE id=1", (json.dumps(s),))
        elif method not in {"GET", "HEAD"}:
            raise APIError(405, "Use GET or POST.")
        # Warehouse accounts receive fulfillment data only; no customer directory or revenue.
        result = {**s, "role": access, "products": [public_product(p) for p in c.execute("SELECT * FROM products WHERE deleted_at IS NULL")]}
        if access != "owner": result.pop("staff", None)
        if access == "warehouse":
            result = {"role": access, "revision": s["revision"], "orders": [{k: v for k, v in o.items() if k not in {"customer", "returnDays"}} for o in s["orders"]]}
            for order in result["orders"]:
                order["lines"] = [{k: v for k, v in l.items() if k != "priceCents"} for l in order["lines"]]
        else:
            result["customers"] = [dict(r) for r in c.execute("SELECT id,name,email FROM users WHERE role='customer'")]
            if access == "owner": result["admins"] = [dict(r) for r in c.execute("SELECT id,name,email FROM users WHERE role='admin'")]
    handler.send_json(200, result)
