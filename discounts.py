"""Seasonal discount codes and server-priced, non-redeeming bag previews."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
import secrets
import sqlite3

import commerce


class DiscountError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


THEMES = (
    {"id": "black-friday", "name": "Black Friday"},
    {"id": "halloween", "name": "Halloween"},
    {"id": "christmas", "name": "Christmas"},
    {"id": "new-year", "name": "New Year"},
    {"id": "summer", "name": "Summer"},
    {"id": "custom", "name": "Custom campaign"},
)
THEME_IDS = {theme["id"] for theme in THEMES}
FIELDS = {"code", "name", "theme", "type", "amount", "minSubtotal", "startsAt", "endsAt", "active"}


def now():
    return datetime.now(timezone.utc)


def timestamp():
    return now().isoformat(timespec="seconds").replace("+00:00", "Z")


def initialize(server):
    with server.connect() as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS discount_codes (
            id TEXT PRIMARY KEY,
            code TEXT NOT NULL UNIQUE COLLATE NOCASE,
            name TEXT NOT NULL,
            theme TEXT NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('percent','fixed')),
            amount_units INTEGER NOT NULL CHECK(amount_units > 0),
            min_subtotal_cents INTEGER NOT NULL CHECK(min_subtotal_cents >= 0),
            starts_at TEXT,
            ends_at TEXT,
            active INTEGER NOT NULL CHECK(active IN (0,1)),
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")


def code_value(value, *, allow_empty=False):
    if not isinstance(value, str):
        raise DiscountError(400, "Enter a discount code.")
    value = value.strip().upper()
    if allow_empty and not value:
        return ""
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{2,39}", value):
        raise DiscountError(400, "Use a discount code of 3 to 40 letters, numbers or hyphens, starting with a letter or number.")
    return value


def decimal_units(value, label, minimum, maximum):
    if type(value) not in {int, float}:
        raise DiscountError(400, f"Enter a valid {label}.")
    try:
        decimal = Decimal(str(value))
        if not decimal.is_finite() or not Decimal(str(minimum)) <= decimal <= Decimal(str(maximum)):
            raise ValueError()
        units = decimal * 100
        if units != units.to_integral_value():
            raise ValueError()
        return int(units)
    except (InvalidOperation, ValueError, OverflowError):
        raise DiscountError(400, f"Enter a {label} between {minimum} and {maximum}, with at most two decimal places.")


def date_value(value):
    if value is None:
        return None
    if not isinstance(value, str) or not 1 <= len(value) <= 40:
        raise DiscountError(400, "Choose valid start and end dates, including a time zone.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError()
        parsed = parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise DiscountError(400, "Choose valid start and end dates, including a time zone.")
    return parsed.isoformat(timespec="microseconds" if parsed.microsecond else "seconds").replace("+00:00", "Z")


def public_discount(row):
    return {"id": row["id"], "code": row["code"], "name": row["name"], "theme": row["theme"],
            "type": row["kind"], "amount": row["amount_units"] / 100,
            "minSubtotal": row["min_subtotal_cents"] / 100, "startsAt": row["starts_at"], "endsAt": row["ends_at"],
            "active": bool(row["active"]), "createdAt": row["created_at"], "updatedAt": row["updated_at"]}


def validated_fields(payload, previous=None):
    if not isinstance(payload, dict) or not payload or set(payload) - FIELDS or (previous is None and set(payload) != FIELDS):
        raise DiscountError(400, "Send the discount code, campaign, amount, minimum spend, dates and status.")
    values = ({field: public_discount(previous)[field] for field in FIELDS} if previous is not None else {})
    values.update(payload)
    code = code_value(values.get("code"), allow_empty=previous is None)
    name = values.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100 or any(ord(char) < 32 for char in name):
        raise DiscountError(400, "Enter a campaign name between 1 and 100 characters.")
    theme, kind = values.get("theme"), values.get("type")
    if not isinstance(theme, str) or theme not in THEME_IDS or kind not in ("percent", "fixed"):
        raise DiscountError(400, "Choose a valid theme and discount type.")
    amount = decimal_units(values.get("amount"), "percentage" if kind == "percent" else "discount amount", 1 if kind == "percent" else .01, 100 if kind == "percent" else 100000)
    minimum = decimal_units(values.get("minSubtotal"), "minimum spend", 0, 1000000)
    starts, ends = date_value(values.get("startsAt")), date_value(values.get("endsAt"))
    if starts and ends and datetime.fromisoformat(ends.replace("Z", "+00:00")) <= datetime.fromisoformat(starts.replace("Z", "+00:00")):
        raise DiscountError(400, "The end date must be after the start date.")
    active = values.get("active")
    if type(active) is not bool:
        raise DiscountError(400, "Choose whether this discount code is active.")
    return {"code": code, "name": name.strip(), "theme": theme, "kind": kind, "amount_units": amount,
            "min_subtotal_cents": minimum, "starts_at": starts, "ends_at": ends, "active": int(active)}


def require_manager(handler, connection, user):
    current = handler.fresh_security_user(connection, user, admin=True)
    if commerce.role(connection, current) not in {"owner", "manager"}:
        raise DiscountError(403, "Your staff role does not permit discount-code management.")


def create_code(handler, user, payload):
    values = validated_fields(payload)
    with handler.server.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        require_manager(handler, connection, user)
        if not values["code"]:
            prefix = values["theme"].replace("-", "").upper()
            for _ in range(12):
                candidate = f"{prefix}-{secrets.token_hex(3).upper()}"
                if not connection.execute("SELECT 1 FROM discount_codes WHERE code=?", (candidate,)).fetchone():
                    values["code"] = candidate
                    break
            if not values["code"]:
                raise DiscountError(409, "A unique code could not be generated. Please try again.")
        if connection.execute("SELECT 1 FROM discount_codes WHERE code=?", (values["code"],)).fetchone():
            raise DiscountError(409, "This discount code already exists. Choose another code.")
        key, stamp = secrets.token_hex(16), timestamp()
        connection.execute("""INSERT INTO discount_codes
            (id,code,name,theme,kind,amount_units,min_subtotal_cents,starts_at,ends_at,active,created_by,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", (key, values["code"], values["name"], values["theme"], values["kind"], values["amount_units"], values["min_subtotal_cents"], values["starts_at"], values["ends_at"], values["active"], user["id"], stamp, stamp))
        row = connection.execute("SELECT * FROM discount_codes WHERE id=?", (key,)).fetchone()
        handler.audit("discount_created", user=user, detail=f"Created {values['theme']} discount {key}; active={bool(values['active'])}.", connection=connection)
        result = public_discount(row)
    handler.send_json(201, {"discount": result})


def change_code(handler, user, key, payload, delete=False):
    if delete and payload:
        raise DiscountError(400, "This action does not accept additional fields.")
    with handler.server.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        require_manager(handler, connection, user)
        previous = connection.execute("SELECT * FROM discount_codes WHERE id=?", (key,)).fetchone()
        if previous is None:
            raise DiscountError(404, "This discount code was not found.")
        if delete:
            connection.execute("DELETE FROM discount_codes WHERE id=?", (key,))
            handler.audit("discount_deleted", user=user, detail=f"Deleted discount {key}.", connection=connection)
            result = {"deleted": True}
        else:
            values = validated_fields(payload, previous)
            if connection.execute("SELECT 1 FROM discount_codes WHERE code=? AND id!=?", (values["code"], key)).fetchone():
                raise DiscountError(409, "This discount code already exists. Choose another code.")
            connection.execute("""UPDATE discount_codes SET code=?,name=?,theme=?,kind=?,amount_units=?,min_subtotal_cents=?,starts_at=?,ends_at=?,active=?,updated_at=? WHERE id=?""",
                               (values["code"], values["name"], values["theme"], values["kind"], values["amount_units"], values["min_subtotal_cents"], values["starts_at"], values["ends_at"], values["active"], timestamp(), key))
            handler.audit("discount_updated", user=user, detail=f"Updated discount {key}; active={bool(values['active'])}.", connection=connection)
            result = {"discount": public_discount(connection.execute("SELECT * FROM discount_codes WHERE id=?", (key,)).fetchone())}
    handler.send_json(200, result)


def quoted_items(payload):
    if set(payload) != {"code", "items"}:
        raise DiscountError(400, "Send a discount code and bag items. Prices are calculated by Velora.")
    code = code_value(payload["code"])
    items = payload["items"]
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        raise DiscountError(400, "Add between 1 and 100 bag items to apply a code.")
    quantities = {}
    for item in items:
        if not isinstance(item, dict) or set(item) != {"productId", "quantity"}:
            raise DiscountError(400, "Each bag item needs a product and quantity.")
        product, quantity = item["productId"], item["quantity"]
        if not isinstance(product, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", product) or type(quantity) is not int or not 1 <= quantity <= 100:
            raise DiscountError(400, "Choose valid products and quantities between 1 and 100.")
        quantities[product] = quantities.get(product, 0) + quantity
        if quantities[product] > 100:
            raise DiscountError(400, "Each product can have at most 100 items in a discount preview.")
    return code, quantities


def validate_code(handler, payload):
    code, quantities = quoted_items(payload)
    with handler.server.connect() as connection:
        # Use one read snapshot for the code, availability and all current prices.
        connection.execute("BEGIN")
        row = connection.execute("SELECT * FROM discount_codes WHERE code=?", (code,)).fetchone()
        current = now()
        if (row is None or not row["active"]
                or row["starts_at"] and current < datetime.fromisoformat(row["starts_at"].replace("Z", "+00:00"))
                or row["ends_at"] and current >= datetime.fromisoformat(row["ends_at"].replace("Z", "+00:00"))):
            raise DiscountError(400, "This discount code is unavailable or outside its active dates.")
        subtotal = 0
        for product, quantity in quantities.items():
            item = connection.execute("SELECT price,stock FROM products WHERE id=? AND published=1 AND deleted_at IS NULL", (product,)).fetchone()
            if item is None or item["stock"] is not None and item["stock"] < quantity:
                raise DiscountError(400, "A bag item is no longer available in the requested quantity. Refresh your bag.")
            price = int((Decimal(str(item["price"])) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            subtotal += price * quantity
        if subtotal < row["min_subtotal_cents"]:
            minimum = Decimal(row["min_subtotal_cents"]) / 100
            raise DiscountError(400, f"This code requires a bag subtotal of at least EUR {minimum:.2f}.")
        discount = ((subtotal * row["amount_units"] + 5000) // 10000 if row["kind"] == "percent" else row["amount_units"])
        discount = min(subtotal, discount)
        result = {"code": row["code"], "name": row["name"], "theme": row["theme"], "type": row["kind"], "amount": row["amount_units"] / 100,
                  "currency": "EUR", "subtotalCents": subtotal, "discountCents": discount, "totalCents": subtotal - discount, "scope": "bag-preview"}
    handler.send_json(200, result)


def handle(handler, method, path):
    if path == "/api/discounts/validate":
        if method != "POST":
            raise DiscountError(405, "Use POST to validate a discount code.")
        handler.server.rate_limit(("discount-preview", handler.client_address[0]), 60, 60)
        validate_code(handler, handler.read_json())
        return True
    if path != "/api/admin/discounts" and not path.startswith("/api/admin/discounts/"):
        return False
    reading = method in {"GET", "HEAD"}
    user = handler.require_user(admin=True, csrf=not reading)
    with handler.server.connect() as connection:
        require_manager(handler, connection, user)
        if reading and path == "/api/admin/discounts":
            result = {"discounts": [public_discount(row) for row in connection.execute("SELECT * FROM discount_codes ORDER BY created_at DESC,id DESC")], "themes": list(THEMES), "currency": "EUR"}
            handler.send_json(200, result)
            return True
    if method == "POST" and path == "/api/admin/discounts":
        create_code(handler, user, handler.read_json())
        return True
    match = re.fullmatch(r"/api/admin/discounts/([a-f0-9]{32})", path)
    if match and method in {"PATCH", "DELETE"}:
        change_code(handler, user, match[1], handler.read_json(), delete=method == "DELETE")
        return True
    raise DiscountError(405 if match or path == "/api/admin/discounts" else 404, "This discount-code action is not supported.")
