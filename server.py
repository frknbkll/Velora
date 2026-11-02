"""Velora's dependency-free local account and catalog server.

Run ``python server.py``; see ACCOUNT_SETUP.md before deployment.
This development server is intentionally not a production hosting stack.
"""

from __future__ import annotations

import argparse
import base64
import binascii
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import getpass
import hashlib
import hmac
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
from urllib.parse import unquote, urlsplit

from security_core import HandlerSecurity, ServerSecurity, SecurityError, masked_email


ROOT = Path(__file__).resolve().parent
PASSWORD_ITERATIONS = 600_000
COOKIE_NAME = "velora_session"
MAX_BODY_BYTES = 16_384
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_UPLOAD_BODY_BYTES = 12 * 1024 * 1024
MAX_REQUEST_WORKERS = 32
MAX_RATE_KEYS = 4096
MAX_HEADER_BYTES = 32_768
SECURITY_REVISION = "2026-11-01.2"
PRODUCT_COLLECTIONS = (
    "THE EVERYDAY EDIT", "THE SOFT EDIT", "THE AFTER-HOURS EDIT",
    "THE MODEST EDIT", "THE POLISHED EDIT", "THE TAILORED EDIT",
    "THE OCCASION EDIT", "THE EVENING EDIT",
)
PRODUCT_SIZES = ("XS", "S", "M", "L", "XL", "XXL", "3XL", "One size")
PRODUCT_FIELDS = {"name", "images", "founder", "collection", "price", "description", "published", "sku", "stock", "sizes", "base_color", "color_hex"}
USER_FIELDS = ("id", "name", "firstName", "lastName", "city", "country", "email", "role", "created_at")
TERMS_VERSION = "2026-11-01"
MINIMUM_ACCOUNT_AGE = 16
BUSINESS_FIELDS = {
    "legalName": ("the legal business name", 200),
    "country": ("the country", 100),
    "registrationNumber": ("the business registration number", 200),
    "vatNumber": ("the VAT number", 200),
    "businessAddress": ("the business address", 1000),
    "customerServiceEmail": ("the customer-service email address", 200),
    "returnAddress": ("the return address", 1000),
}
DUMMY_PASSWORD_HASH = hashlib.pbkdf2_hmac(
    "sha256", b"unusable account password", b"velora timing comparison", PASSWORD_ITERATIONS
).hex()


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def hash_password(password):
    salt = secrets.token_hex(24)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PASSWORD_ITERATIONS).hex()
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest}"


def verify_password(password, encoded):
    if not isinstance(password, str) or len(password) > 128:
        return False
    if not encoded:
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), b"velora timing comparison", PASSWORD_ITERATIONS
        ).hex()
        hmac.compare_digest(digest, DUMMY_PASSWORD_HASH)
        return False
    try:
        if not isinstance(encoded, str):
            return False
        algorithm, rounds, salt, expected = encoded.split("$")
        if (algorithm != "pbkdf2_sha256" or not re.fullmatch(r"[0-9]{1,7}", rounds)
                or not 100_000 <= int(rounds) <= 2_000_000
                or not re.fullmatch(r"[0-9a-f]{48}", salt)
                or not re.fullmatch(r"[0-9a-f]{64}", expected)):
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


class APIError(Exception):
    def __init__(self, status, message, retry_after=None):
        self.status = status
        self.message = message
        self.retry_after = retry_after


def security_response_headers(secure_cookies=False):
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "same-origin",
        "X-Frame-Options": "SAMEORIGIN",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
        "X-Permitted-Cross-Domain-Policies": "none",
        "X-XSS-Protection": "0",
        "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'; form-action 'self'",
    }
    if secure_cookies:
        headers["Strict-Transport-Security"] = "max-age=31536000"
    return headers


def validate_name(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 80:
        raise APIError(400, "Enter a name between 1 and 80 characters.")
    value = value.strip()
    if any(ord(character) < 32 for character in value):
        raise APIError(400, "Enter a valid name.")
    return value


def validate_profile_field(value, label, maximum=100):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum:
        raise APIError(400, f"Enter {label} between 1 and {maximum} characters.")
    value = value.strip()
    if any(ord(character) < 32 for character in value):
        raise APIError(400, f"Enter a valid {label}.")
    return value


def validate_email(value):
    if not isinstance(value, str):
        raise APIError(400, "Enter a valid email address.")
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[^\s@\x00-\x1f]+@[^\s@.\x00-\x1f]+(?:\.[^\s@.\x00-\x1f]+)+", value):
        raise APIError(400, "Enter a valid email address.")
    return value


def validate_password(value):
    if not isinstance(value, str) or not 15 <= len(value) <= 128:
        raise APIError(400, "Use a password between 15 and 128 characters.")
    return value


def public_user(row):
    user = {field: row[field] for field in USER_FIELDS if field not in {"firstName", "lastName", "city", "country"}}
    user.update({
        "firstName": row["first_name"],
        "lastName": row["last_name"],
        "city": row["city"],
        "country": row["country"],
    })
    return user


def public_product(row):
    product = dict(row)
    product["published"] = bool(product["published"])
    product["images"] = json.loads(product["images"])
    product["sizes"] = json.loads(product["sizes"])
    return product


def validate_text(value, label, maximum):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum:
        raise APIError(400, f"Enter {label} between 1 and {maximum:,} characters.")
    value = value.strip()
    if any(ord(character) < 32 and character not in "\n\r\t" for character in value):
        raise APIError(400, f"Enter valid {label}.")
    return value


def product_sku(connection, product_id):
    candidate = "VL-" + product_id[:12].upper()
    while connection.execute("SELECT 1 FROM products WHERE sku = ? COLLATE NOCASE", (candidate,)).fetchone():
        candidate = "VL-" + secrets.token_hex(6).upper()
    return candidate


def image_extension(data):
    """Check raster format headers and bounded dimensions before storing an upload."""
    extension = None
    width = height = 0
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        if len(data) < 45 or data[12:16] != b"IHDR" or data[-8:-4] != b"IEND":
            return None
        width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
        extension = "png"
    elif data.startswith(b"\xff\xd8"):
        if not data.endswith(b"\xff\xd9"):
            return None
        position = 2
        while position + 4 <= len(data):
            if data[position] != 255:
                return None
            while position < len(data) and data[position] == 255:
                position += 1
            if position >= len(data):
                return None
            marker, position = data[position], position + 1
            if marker in {0xDA, 0xD9}:
                break
            if marker == 0x01 or 0xD0 <= marker <= 0xD8:
                continue
            length = int.from_bytes(data[position:position + 2], "big")
            if length < 2 or position + length > len(data):
                return None
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                if length < 8:
                    return None
                height = int.from_bytes(data[position + 3:position + 5], "big")
                width = int.from_bytes(data[position + 5:position + 7], "big")
                extension = "jpg"
                break
            position += length
    elif len(data) >= 30 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        if int.from_bytes(data[4:8], "little") + 8 != len(data):
            return None
        kind = data[12:16]
        if kind == b"VP8X":
            width, height = int.from_bytes(data[24:27], "little") + 1, int.from_bytes(data[27:30], "little") + 1
        elif kind == b"VP8 " and data[23:26] == b"\x9d\x01\x2a":
            width = int.from_bytes(data[26:28], "little") & 0x3FFF
            height = int.from_bytes(data[28:30], "little") & 0x3FFF
        elif kind == b"VP8L" and data[20] == 0x2F:
            bits = int.from_bytes(data[21:25], "little")
            width, height = (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        extension = "webp"
    if not extension or not 1 <= width <= 16000 or not 1 <= height <= 16000 or width * height > 40_000_000:
        return None
    return extension


class VeloraServer(ServerSecurity, ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, database, catalog, root=ROOT, secure_cookies=False):
        self.root = Path(root).resolve()
        self.database = Path(database).resolve()
        self.secure_cookies = secure_cookies
        self.rate_lock = threading.Lock()
        self.rate_events = {}
        self.request_workers = threading.BoundedSemaphore(MAX_REQUEST_WORKERS)
        self.initialize_database(catalog)
        self.initialize_security()
        super().__init__(address, VeloraHandler)
        host, port = address[0].lower(), self.server_port
        names = {host}
        if host in {"127.0.0.1", "localhost"}:
            names.update({"127.0.0.1", "localhost"})
        self.allowed_hosts = {f"{name}:{port}" for name in names}
        if port in {80, 443}:
            self.allowed_hosts.update(names)

    @property
    def private_files(self):
        return {self.database, self.database.with_name("security.key"),
                Path(str(self.database) + "-wal"), Path(str(self.database) + "-shm")}

    def process_request(self, request, client_address):
        if not self.request_workers.acquire(blocking=False):
            # Bound slow/idle connections before starting another request thread.
            body = b'{"error":"Please try again soon."}'
            headers = {"Connection": "close", "Content-Type": "application/json",
                       "Content-Length": str(len(body)), "Cache-Control": "no-store", "Retry-After": "1",
                       **security_response_headers(self.secure_cookies)}
            response = ("HTTP/1.0 503 Service Unavailable\r\n" + "".join(f"{name}: {value}\r\n" for name, value in headers.items()) + "\r\n").encode("ascii") + body
            try:
                request.settimeout(1)
                request.sendall(response)
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.request_workers.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.request_workers.release()

    def handle_error(self, request, client_address):
        # Do not expose request contents or Python tracebacks in normal operation.
        print("A Velora request could not be completed.")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA trusted_schema = OFF")
        connection.execute("PRAGMA secure_delete = ON")
        # SQLite flags provide defense in depth; no endpoint accepts SQL text.
        if hasattr(connection, "setconfig"):
            connection.setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE, True)
            connection.setconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION, False)
        connection.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)
        connection.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 1_000_000)
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_UPLOAD_BODY_BYTES)
        connection.setlimit(sqlite3.SQLITE_LIMIT_EXPR_DEPTH, 100)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize_database(self, catalog):
        self.database.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt":
            if self.database.parent.name == ".velora":
                self.database.parent.chmod(0o700)
            if self.database.exists():
                self.database.chmod(0o600)
            else:
                try:
                    descriptor = os.open(self.database, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    os.close(descriptor)
                except FileExistsError:
                    self.database.chmod(0o600)
        seed = json.loads(Path(catalog).read_text(encoding="utf-8"))
        products = seed["products"] if isinstance(seed, dict) else seed
        copy_updates_file = Path(catalog).resolve().with_name("catalog-copy-updates.json")
        copy_updates = json.loads(copy_updates_file.read_text(encoding="utf-8")) if copy_updates_file.is_file() else []
        if not isinstance(copy_updates, list) or any(
            not isinstance(update, dict) or not all(isinstance(update.get(field), str) for field in ("id", "previous", "replacement"))
            for update in copy_updates
        ):
            raise ValueError("The catalog copy update file must contain product IDs and previous/replacement descriptions.")
        legacy_keys = {product["id"]: f"{product['name']}:{product['image']}" for product in products}
        with self.connect() as connection:
            connection.executescript("""
                PRAGMA journal_mode = DELETE;
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    first_name TEXT NOT NULL DEFAULT '',
                    last_name TEXT NOT NULL DEFAULT '',
                    city TEXT NOT NULL DEFAULT '',
                    country TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('customer', 'admin')),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    csrf_token TEXT NOT NULL,
                    expires_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
                CREATE TABLE IF NOT EXISTS user_consents (
                    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    terms_version TEXT NOT NULL,
                    terms_accepted_at TEXT NOT NULL,
                    age_minimum INTEGER NOT NULL,
                    age_confirmed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS business_settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    details TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS products (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    image TEXT NOT NULL,
                    founder TEXT NOT NULL,
                    collection TEXT NOT NULL,
                    price REAL NOT NULL CHECK (price >= 1 AND price <= 100000),
                    description TEXT NOT NULL,
                    published INTEGER NOT NULL DEFAULT 1 CHECK (published IN (0, 1)),
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS product_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    actor_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    product_id TEXT,
                    product_name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)
            user_columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
            profile_additions = {
                "first_name": "TEXT NOT NULL DEFAULT ''",
                "last_name": "TEXT NOT NULL DEFAULT ''",
                "city": "TEXT NOT NULL DEFAULT ''",
                "country": "TEXT NOT NULL DEFAULT ''",
            }
            for name, declaration in profile_additions.items():
                if name not in user_columns:
                    connection.execute(f"ALTER TABLE users ADD COLUMN {name} {declaration}")
            for row in connection.execute("SELECT id,name FROM users WHERE first_name='' AND last_name=''").fetchall():
                parts = row["name"].strip().split(maxsplit=1)
                connection.execute("UPDATE users SET first_name=?,last_name=? WHERE id=?", (
                    parts[0] if parts else "",
                    parts[1] if len(parts) > 1 else "",
                    row["id"],
                ))
            connection.execute("INSERT OR IGNORE INTO business_settings VALUES (1,?)", (json.dumps(dict.fromkeys(BUSINESS_FIELDS, "")),))
            # Add fields in place so existing accounts, sessions and catalog edits survive.
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(products)")}
            additions = {
                "images": "TEXT NOT NULL DEFAULT '[]'",
                "color_key": "TEXT NOT NULL DEFAULT ''",
                "legacy_key": "TEXT NOT NULL DEFAULT ''",
                "base_color": "TEXT NOT NULL DEFAULT 'Original'",
                "color_hex": "TEXT NOT NULL DEFAULT '#d1c8bd'",
                "sku": "TEXT NOT NULL DEFAULT ''",
                "stock": "INTEGER CHECK (stock IS NULL OR (stock >= 0 AND stock <= 999999))",
                "sizes": "TEXT NOT NULL DEFAULT '[\"XS\",\"S\",\"M\",\"L\"]'",
                "deleted_at": "TEXT",
                "created_at": "TEXT NOT NULL DEFAULT ''",
            }
            for name, declaration in additions.items():
                if name not in columns:
                    connection.execute(f"ALTER TABLE products ADD COLUMN {name} {declaration}")
            for row in connection.execute("SELECT * FROM products").fetchall():
                connection.execute("""
                    UPDATE products SET images = ?, color_key = ?, legacy_key = ?, sku = ?, created_at = ? WHERE id = ?
                """, (
                    row["images"] if row["images"] != "[]" else json.dumps([row["image"]]),
                    row["color_key"] if "color_key" in columns else row["image"],
                    row["legacy_key"] or legacy_keys.get(row["id"], ""), row["sku"] or product_sku(connection, row["id"]),
                    row["created_at"] or row["updated_at"], row["id"],
                ))
            connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS products_sku ON products(sku COLLATE NOCASE)")
            for product in products:
                if connection.execute("SELECT 1 FROM products WHERE id = ?", (product["id"],)).fetchone():
                    continue
                images = product.get("images") or [product["image"]]
                stamp = product.get("updated_at") or now_iso()
                connection.execute("""
                    INSERT INTO products
                    (id, name, image, founder, collection, price, description, published, updated_at,
                     images, color_key, legacy_key, base_color, color_hex, sku, stock, sizes, deleted_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    product["id"], product["name"], images[0], product["founder"],
                    product["collection"], product["price"], product["description"],
                    int(product.get("published", True)), stamp, json.dumps(images),
                    product.get("color_key", product["image"]), legacy_keys[product["id"]], product.get("base_color", "Original"),
                    product.get("color_hex", "#d1c8bd"), product.get("sku") or product_sku(connection, product["id"]),
                    product.get("stock"), json.dumps(product.get("sizes", ["XS", "S", "M", "L"])),
                    product.get("deleted_at"), product.get("created_at") or stamp,
                ))
            for update in copy_updates:
                # Update untouched seed copy only; preserve the owner's descriptions.
                connection.execute("UPDATE products SET description=?,updated_at=? WHERE id=? AND description=?", (
                    update["replacement"], now_iso(), update["id"], update["previous"],
                ))
            connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (int(time.time()),))
        if os.name != "nt":
            for path in (self.database, Path(str(self.database) + "-wal"), Path(str(self.database) + "-shm")):
                if path.exists():
                    path.chmod(0o600)

    def rate_limit(self, key, limit, window):
        current = time.monotonic()
        with self.rate_lock:
            # Prune all stale keys to bound memory even when emails are randomized.
            if len(self.rate_events) > 2000 or len(self.rate_events) >= MAX_RATE_KEYS:
                self.rate_events = {
                    item: events for item, events in self.rate_events.items()
                    if events and current - events[-1] < 3600
                }
            if key not in self.rate_events and len(self.rate_events) >= MAX_RATE_KEYS:
                raise APIError(429, "Too many attempts. Please try again later.", retry_after=3600)
            events = [stamp for stamp in self.rate_events.get(key, []) if current - stamp < window]
            if len(events) >= limit:
                raise APIError(429, "Too many attempts. Please try again later.", retry_after=max(1, math.ceil(window)))
            events.append(current)
            self.rate_events[key] = events


class VeloraHandler(HandlerSecurity, BaseHTTPRequestHandler):
    server_version = "Velora"
    sys_version = ""
    password_checker = staticmethod(verify_password)
    user_payload = staticmethod(public_user)

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, format, *args):
        # Log status and path only. Request bodies, credentials and cookies stay private.
        try:
            path = urlsplit(getattr(self, "path", "")).path
        except ValueError:
            path = "[invalid address]"
        path = "".join(character for character in path if ord(character) >= 32)[:256]
        print(f"{self.client_address[0]} {self.command} {path} {args[1] if len(args) > 1 else ''}")

    def do_GET(self):
        self.dispatch()

    def do_HEAD(self):
        self.dispatch()

    def do_POST(self):
        self.dispatch()

    def do_PATCH(self):
        self.dispatch()

    def do_PUT(self):
        self.dispatch()

    def do_DELETE(self):
        self.dispatch()

    def do_OPTIONS(self):
        self.dispatch()

    def send_error(self, code, message=None, explain=None):
        # BaseHTTPRequestHandler also uses this path for malformed HTTP and unknown verbs.
        self.close_connection = True
        self.send_json(code, {"error": "This request could not be processed."})

    def dispatch(self):
        try:
            host = self.headers.get("Host", "").strip().lower()
            if len(self.headers.get_all("Host", [])) != 1 or host not in self.server.allowed_hosts:
                raise APIError(400, "This host is not allowed.")
            if sum(len(key) + len(value) for key, value in self.headers.items()) > MAX_HEADER_BYTES:
                raise APIError(431, "The request headers are too large.")
            if len(self.path) > 4096:
                raise APIError(414, "The request address is too long.")
            target = urlsplit(self.path)
            if target.scheme or target.netloc or target.fragment or not self.path.startswith("/"):
                raise APIError(400, "Send a local website address.")
            self.path_only = target.path
            if (len(self.headers.get_all("Cookie", [])) > 1 or self.headers.get("Transfer-Encoding") is not None
                    or len(self.headers.get_all("Content-Length", [])) > 1):
                raise APIError(400, "This request format is not supported.")
            length = self.headers.get("Content-Length")
            if length is not None and not re.fullmatch(r"[0-9]{1,10}", length):
                raise APIError(400, "Invalid request length.")
            if self.command in {"GET", "HEAD"} and length is not None and int(length) != 0:
                raise APIError(400, "This request does not accept a body.")
            if self.path_only.startswith("/api/"):
                self.server.rate_limit(("api-request", self.client_address[0]), 600, 60)
                self.handle_api()
            elif self.command in {"GET", "HEAD"}:
                self.serve_static()
            else:
                raise APIError(405, "This method is not supported.")
        except (APIError, SecurityError) as error:
            self.send_json(error.status, {"error": error.message}, retry_after=getattr(error, "retry_after", None))
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError):
            pass
        except (sqlite3.Error, OSError, ValueError, KeyError):
            self.send_json(500, {"error": "Something went wrong. Please try again."})
        except Exception:
            self.send_json(500, {"error": "Something went wrong. Please try again."})

    def common_headers(self):
        for name, value in security_response_headers(self.server.secure_cookies).items():
            self.send_header(name, value)

    def send_json(self, status, payload, cookie=None, retry_after=None):
        data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            if status == 429:
                self.send_header("Retry-After", str(retry_after or 900))
            self.common_headers()
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()
            if getattr(self, "command", None) != "HEAD":
                self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError):
            # Browser navigation can close the socket while an error response is
            # being sent from dispatch's exception handler.
            pass

    def read_json(self, maximum=MAX_BODY_BYTES):
        expected_scheme = "https" if self.server.secure_cookies else "http"
        expected_origin = f"{expected_scheme}://{self.headers['Host'].strip().lower()}"
        origin = self.headers.get("Origin")
        if len(self.headers.get_all("Origin", [])) != 1 or origin != expected_origin or self.headers.get("Sec-Fetch-Site") == "cross-site":
            self.audit("csrf_rejected", user=self.security_session(touch=False), detail="A request from an unexpected origin was rejected.", severity="warning")
            raise APIError(403, "Please submit this request from the Velora website.")
        if len(self.headers.get_all("Content-Type", [])) != 1 or self.headers.get_content_type() != "application/json":
            raise APIError(415, "Send the request as application/json.")
        if self.headers.get_content_charset("utf-8").lower() not in {"utf-8", "utf8"}:
            raise APIError(415, "Send JSON encoded as UTF-8.")
        if self.headers.get("Transfer-Encoding"):
            raise APIError(400, "This request format is not supported.")
        if len(self.headers.get_all("Content-Length", [])) != 1:
            raise APIError(400, "Send one valid request length.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise APIError(400, "Invalid request length.")
        if not 0 < length <= maximum:
            raise APIError(413, "This request is too large or empty.")
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("Incomplete body")
            def distinct_object(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("Duplicate JSON member")
                    result[key] = value
                return result
            payload = json.loads(raw.decode("utf-8"), object_pairs_hook=distinct_object,
                                 parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            pending = [payload]
            while pending:
                value = pending.pop()
                if isinstance(value, str):
                    value.encode("utf-8")
                elif isinstance(value, dict):
                    pending.extend(value.keys())
                    pending.extend(value.values())
                elif isinstance(value, list):
                    pending.extend(value)
        except (ValueError, UnicodeDecodeError, RecursionError):
            raise APIError(400, "Send a valid JSON request.")
        if not isinstance(payload, dict):
            raise APIError(400, "Send a JSON object.")
        return payload

    def session(self):
        return self.security_session()

    def require_user(self, admin=False, csrf=False):
        user = self.session()
        if user is None:
            if admin:
                self.audit("permission_denied", detail="An unsigned request for administrator data was rejected.", severity="warning")
            raise APIError(401, "Please sign in to continue.")
        if admin and user["role"] != "admin":
            self.audit("permission_denied", user=user, detail="A non-administrator request for administrator data was rejected.", severity="warning")
            raise APIError(403, "Administrator access is required.")
        if csrf and (len(self.headers.get_all("X-CSRF-Token", [])) != 1 or not hmac.compare_digest(self.headers.get("X-CSRF-Token", "").encode("utf-8"), user["csrf_token"].encode("utf-8"))):
            self.audit("csrf_rejected", user=user, detail="A request with a missing or invalid CSRF token was rejected.", severity="warning")
            raise APIError(403, "Your session could not be verified. Refresh the page and try again.")
        return user

    def issue_session(self, user, remember=False, mfa_verified=False):
        return self.create_secure_session(user, remember, mfa_verified)

    def handle_api(self):
        path, method = self.path_only, self.command
        reading = method in {"GET", "HEAD"}
        if reading and path == "/api/health":
            return self.send_json(200, {"service": "velora", "securityRevision": SECURITY_REVISION})
        if self.handle_security_api(path, method):
            return
        if reading and path == "/api/auth/me":
            user = self.session()
            return self.send_json(200, {
                "user": public_user(user) if user else None,
                "csrfToken": user["csrf_token"] if user else None,
            })
        if reading and path == "/api/catalog":
            with self.server.connect() as connection:
                products = connection.execute("SELECT * FROM products WHERE published = 1 AND deleted_at IS NULL ORDER BY rowid").fetchall()
            return self.send_json(200, {"products": [public_product(product) for product in products]})
        if reading and path in {"/api/business-details", "/api/admin/business-details"}:
            if path.startswith("/api/admin/"):
                self.require_user(admin=True)
            with self.server.connect() as connection:
                details = self.business_details(connection)
            return self.send_json(200, {"businessDetails": details})
        if reading and path in {"/api/admin/overview", "/api/admin/products", "/api/admin/customers", "/api/admin/activity"}:
            self.require_user(admin=True)
            with self.server.connect() as connection:
                if path.endswith("/products"):
                    products = connection.execute("SELECT * FROM products ORDER BY rowid").fetchall()
                    return self.send_json(200, {"products": [public_product(product) for product in products]})
                if path.endswith("/activity"):
                    events = connection.execute("SELECT id,actor_name,action,product_id,product_name,created_at FROM product_activity ORDER BY id DESC LIMIT 100").fetchall()
                    return self.send_json(200, {"events": [dict(event) for event in events]})
                customers = [public_user(row) for row in connection.execute(
                    "SELECT * FROM users WHERE role = 'customer' ORDER BY id DESC"
                ).fetchall()]
                if path.endswith("/customers"):
                    return self.send_json(200, {"customers": customers})
                counts = connection.execute("""
                    SELECT COUNT(*) AS total, COALESCE(SUM(published), 0) AS published,
                           COALESCE(SUM(stock BETWEEN 1 AND 5), 0) AS low_stock,
                           COALESCE(SUM(stock = 0), 0) AS out_of_stock
                    FROM products WHERE deleted_at IS NULL
                """).fetchone()
                return self.send_json(200, {
                    "totalProducts": counts["total"], "publishedProducts": counts["published"],
                    "draftProducts": counts["total"] - counts["published"],
                    "totalCustomers": len(customers), "recentCustomers": customers[:5],
                    "lowStockProducts": counts["low_stock"], "outOfStockProducts": counts["out_of_stock"],
                    "trashedProducts": connection.execute("SELECT COUNT(*) FROM products WHERE deleted_at IS NOT NULL").fetchone()[0],
                })
        if method == "POST" and path in {"/api/auth/register", "/api/auth/login"}:
            payload = self.read_json()
            return self.register(payload) if path.endswith("register") else self.login(payload)
        if method == "POST" and path == "/api/auth/logout":
            self.read_json()
            user = self.require_user(csrf=True)
            with self.server.connect() as connection:
                connection.execute("DELETE FROM sessions WHERE token_hash = ?", (user["token_hash"],))
                self.audit("logout", user=user, detail="Signed out of the current session.", connection=connection)
            cookie = f"{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"
            if self.server.secure_cookies:
                cookie += "; Secure"
            return self.send_json(200, {"ok": True}, cookie=cookie)
        if method == "PATCH" and path == "/api/account":
            payload = self.read_json()
            user = self.require_user(csrf=True)
            return self.update_account(user, payload)
        if method == "DELETE" and path == "/api/account":
            payload = self.read_json()
            user = self.require_user(csrf=True)
            return self.delete_account(user, payload)
        if method == "PATCH" and path == "/api/admin/business-details":
            user = self.require_user(admin=True, csrf=True)
            return self.update_business_details(user, self.read_json())
        if method == "POST" and path == "/api/admin/uploads":
            user = self.require_user(admin=True, csrf=True)
            self.server.rate_limit(("upload", user["id"]), 100, 3600)
            return self.upload_image(self.read_json(MAX_UPLOAD_BODY_BYTES), user)
        if method == "POST" and path == "/api/admin/products":
            user = self.require_user(admin=True, csrf=True)
            return self.create_product(user, self.read_json())
        action = re.fullmatch(r"/api/admin/products/([A-Za-z0-9_-]{1,64})(?:/(restore|duplicate))?", path)
        if action and method in {"POST", "PATCH", "DELETE"}:
            user = self.require_user(admin=True, csrf=True)
            payload = self.read_json()
            product_id, operation = action.groups()
            if operation is None and method == "PATCH":
                return self.update_product(product_id, payload, user)
            if operation is None and method == "DELETE":
                return self.product_action(product_id, "trash", payload, user)
            if operation and method == "POST":
                return self.product_action(product_id, operation, payload, user)
            raise APIError(405, "This method is not supported.")
        known_path = path in {
            "/api/auth/me", "/api/auth/register", "/api/auth/login", "/api/auth/logout",
            "/api/account", "/api/catalog", "/api/health", "/api/admin/overview", "/api/admin/products", "/api/admin/customers",
            "/api/admin/activity", "/api/admin/uploads",
            "/api/business-details", "/api/admin/business-details",
        }
        raise APIError(405 if known_path else 404, "This method is not supported." if known_path else "This page was not found.")

    def register(self, payload):
        self.server.rate_limit(("register", self.client_address[0]), 10, 3600)
        if set(payload) - {"firstName", "lastName", "city", "country", "email", "password", "terms", "ageConfirmed"}:
            raise APIError(400, "Some account fields are not supported.")
        first_name = validate_name(payload.get("firstName"))
        last_name = validate_name(payload.get("lastName"))
        city = validate_profile_field(payload.get("city"), "a city")
        country = validate_profile_field(payload.get("country"), "a country")
        name = f"{first_name} {last_name}"
        email = validate_email(payload.get("email"))
        password = validate_password(payload.get("password"))
        if payload.get("terms") is not True:
            raise APIError(400, "Please accept the terms to create your account.")
        if payload.get("ageConfirmed") is not True:
            raise APIError(400, "You must confirm that you are at least 16 to create an account.")
        encoded = hash_password(password)
        try:
            with self.server.connect() as connection:
                stamp = now_iso()
                cursor = connection.execute(
                    """INSERT INTO users
                    (name,first_name,last_name,city,country,email,password_hash,role,created_at)
                    VALUES (?,?,?,?,?,?,?,'customer',?)""",
                    (name, first_name, last_name, city, country, email, encoded, stamp),
                )
                connection.execute("INSERT INTO user_consents VALUES (?,?,?,?,?)", (
                    cursor.lastrowid, TERMS_VERSION, stamp, MINIMUM_ACCOUNT_AGE, stamp,
                ))
                user = connection.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        except sqlite3.IntegrityError:
            raise APIError(409, "An account with this email already exists. Please sign in.")
        cookie, csrf_token = self.issue_session(user)
        self.audit("account_registered", user=user, detail="A customer account was created.")
        self.send_json(201, {"user": public_user(user), "csrfToken": csrf_token}, cookie=cookie)

    def login(self, payload):
        if set(payload) - {"email", "password", "remember"}:
            raise APIError(400, "Some sign-in fields are not supported.")
        email = validate_email(payload.get("email"))
        if "remember" in payload and not isinstance(payload["remember"], bool):
            raise APIError(400, "Choose whether to remember this device.")
        self.server.check_login_failures(email, self.client_address[0])
        try:
            self.server.rate_limit(("login-ip", self.client_address[0]), 30, 900)
            self.server.rate_limit(("login-email", email), 10, 900)
        except APIError:
            self.audit("login_blocked", email=email, detail="The sign-in attempt limit was reached.", severity="warning")
            raise APIError(429, "Too many sign-in attempts. Please try again in 15 minutes.")
        with self.server.connect() as connection:
            user = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        accepted = verify_password(payload.get("password"), user["password_hash"] if user else None)
        self.server.login_outcome(email, self.client_address[0], accepted)
        if not accepted:
            raise APIError(401, "The email address or password is incorrect.")
        if user["mfa_enabled"]:
            return self.begin_mfa_login(user, payload.get("remember", False))
        cookie, csrf_token = self.issue_session(user, payload.get("remember", False))
        self.send_json(200, {"user": public_user(user), "csrfToken": csrf_token}, cookie=cookie)

    def update_account(self, user, payload):
        profile_fields = {"name", "firstName", "lastName", "city", "country"}
        if not payload or set(payload) - profile_fields - {"currentPassword", "newPassword"}:
            raise APIError(400, "Some account fields are not supported.")
        if "name" in payload and {"firstName", "lastName"} & set(payload):
            raise APIError(400, "Choose either a display name or first and last name.")
        if "name" in payload:
            name = validate_name(payload["name"])
            name_parts = name.split(maxsplit=1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""
        else:
            first_name = validate_name(payload["firstName"]) if "firstName" in payload else user["first_name"]
            if "lastName" in payload:
                supplied_last_name = payload["lastName"]
                last_name = "" if isinstance(supplied_last_name, str) and not supplied_last_name.strip() else validate_name(supplied_last_name)
            else:
                last_name = user["last_name"]
            name = f"{first_name} {last_name}".strip()
            if not name:
                raise APIError(400, "Enter your first and last name.")
        city = validate_profile_field(payload["city"], "a city") if "city" in payload else user["city"]
        country = validate_profile_field(payload["country"], "a country") if "country" in payload else user["country"]
        new_password_hash = None
        if "newPassword" in payload:
            password = validate_password(payload["newPassword"])
            self.server.rate_limit(("change-password", user["id"]), 10, 900)
            if not verify_password(payload.get("currentPassword"), user["password_hash"]):
                raise APIError(400, "Your current password is incorrect.")
            new_password_hash = hash_password(password)
        elif "currentPassword" in payload:
            raise APIError(400, "Enter a new password to change your password.")
        with self.server.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self.fresh_security_user(connection, user)
            connection.execute(
                "UPDATE users SET name=?,first_name=?,last_name=?,city=?,country=? WHERE id=?",
                (name, first_name, last_name, city, country, user["id"]),
            )
            if new_password_hash:
                version = current["auth_version"] + 1
                connection.execute("UPDATE users SET password_hash = ?,auth_version=? WHERE id = ?", (new_password_hash, version, user["id"]))
                cookie, csrf = self.rotate_security_session(connection, current, version)
                self.audit("password_changed", user=current, detail="Password changed; other sessions signed out.", connection=connection)
            updated = connection.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
        self.send_json(200, {"user": public_user(updated), **({"csrfToken": csrf} if new_password_hash else {})}, cookie=cookie if new_password_hash else None)

    def delete_account(self, user, payload):
        if set(payload) - {"password", "code"} or "password" not in payload:
            raise APIError(400, "Enter your current password to delete your account.")
        self.server.rate_limit(("account-delete", user["id"]), 10, 900)
        self.server.check_login_failures(user["email"], self.client_address[0])
        accepted = verify_password(payload["password"], user["password_hash"])
        self.server.login_outcome(user["email"], self.client_address[0], accepted)
        if not accepted:
            raise APIError(400, "Your current password is incorrect.")
        if user["mfa_enabled"]:
            self.check_mfa_failures(user)
        error = None
        with self.server.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self.fresh_security_user(connection, user)
            if current["role"] == "admin" and connection.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0] <= 1:
                raise APIError(409, "This is the last administrator account. Create another administrator before deleting it.")
            if current["mfa_enabled"]:
                self.guard_mfa_budget(connection, current)
                if not self.verify_mfa_factor(connection, current, payload.get("code")):
                    self.server.add_login_failure(current["email"], self.client_address[0], user=current, mfa=True, connection=connection)
                    error = APIError(400, "Enter a fresh authenticator code or an unused recovery code to delete your account.")
            if error is None:
                # Retain nonpersonal catalog history, but remove the person's name.
                connection.execute("UPDATE product_activity SET actor_id=NULL,actor_name='Deleted account' WHERE actor_id=?", (current["id"],))
                # Older events had no actor_id; remove their identifying hints too.
                connection.execute("""UPDATE security_events SET actor_id=NULL,actor_name='',email_hint='',ip=''
                    WHERE actor_id=? OR (actor_id IS NULL AND (actor_name=? OR email_hint=?))""",
                    (current["id"], current["name"], masked_email(current["email"])))
                connection.execute("DELETE FROM security_failures WHERE bucket IN (?,?)", (
                    self.server.keyed_digest("login-email", current["email"]),
                    self.server.keyed_digest("mfa-user", current["id"]),
                ))
                # FK cascades remove sessions, MFA challenges/recovery codes and consents.
                connection.execute("DELETE FROM users WHERE id=?", (current["id"],))
                self.server.security_event("account_deleted", detail="An account was deleted at its owner's request.", connection=connection)
        if error:
            raise error
        with self.server.rate_lock:
            for key in list(self.server.rate_events):
                if key == ("login-email", user["email"]) or (len(key) > 1 and key[1] == user["id"]):
                    self.server.rate_events.pop(key, None)
        cookie = f"{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"
        if self.server.secure_cookies:
            cookie += "; Secure"
        self.send_json(200, {"ok": True, "deleted": True, "user": None}, cookie=cookie)

    def business_details(self, connection):
        row = connection.execute("SELECT details FROM business_settings WHERE id=1").fetchone()
        stored = json.loads(row["details"]) if row else {}
        # Publish only the explicitly allowed public fields, even after a restore.
        return {field: stored.get(field, "") for field in BUSINESS_FIELDS}

    def update_business_details(self, user, payload):
        if not payload or set(payload) - BUSINESS_FIELDS.keys():
            raise APIError(400, "Some business detail fields are not supported.")
        values = {}
        for field, value in payload.items():
            label, maximum = BUSINESS_FIELDS[field]
            if not isinstance(value, str) or len(value) > maximum:
                raise APIError(400, f"Enter {label} using no more than {maximum:,} characters.")
            value = value.strip()
            allowed_controls = "\r\n" if field in {"businessAddress", "returnAddress"} else ""
            if any(ord(character) < 32 and character not in allowed_controls for character in value):
                raise APIError(400, f"Enter valid text for {label}.")
            if field == "customerServiceEmail" and value:
                value = validate_email(value)
            values[field] = value
        with self.server.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self.fresh_security_user(connection, user)
            if current["role"] != "admin":
                raise APIError(403, "Administrator access is required.")
            details = self.business_details(connection)
            details.update(values)
            connection.execute("UPDATE business_settings SET details=? WHERE id=1", (json.dumps(details, ensure_ascii=False),))
            self.audit("business_details_updated", user=current, detail="Public business details were updated.", connection=connection)
        self.send_json(200, {"businessDetails": details})

    def validate_product_fields(self, payload, creating=False):
        if not payload or set(payload) - PRODUCT_FIELDS:
            raise APIError(400, "Some product fields are not supported.")
        required = {"name", "images", "founder", "collection", "price", "description"}
        if creating and required - set(payload):
            raise APIError(400, "Add a name, images, founder, category, price and description.")
        values = {}
        for field, label, maximum in (("name", "a product name", 160), ("founder", "a founder name", 80),
                                      ("description", "a description", 2000), ("base_color", "a color name", 40)):
            if field in payload:
                values[field] = validate_text(payload[field], label, maximum)
        if "collection" in payload:
            if not isinstance(payload["collection"], str) or payload["collection"] not in PRODUCT_COLLECTIONS:
                raise APIError(400, "Choose one of the collection categories.")
            values["collection"] = payload["collection"]
        if "price" in payload:
            price = payload["price"]
            if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price):
                raise APIError(400, "Enter a valid price.")
            try:
                decimal_price = Decimal(str(price))
                valid = 1 <= decimal_price <= 100000 and decimal_price == decimal_price.quantize(Decimal("0.01"))
            except InvalidOperation:
                valid = False
            if not valid:
                raise APIError(400, "Enter a price from 1 to 100,000 euros, with at most two decimal places.")
            values["price"] = float(price)
        if "published" in payload:
            if not isinstance(payload["published"], bool):
                raise APIError(400, "Choose whether this product is published.")
            values["published"] = int(payload["published"])
        if "images" in payload:
            images = payload["images"]
            if not isinstance(images, list) or not 1 <= len(images) <= 12:
                raise APIError(400, "Add between 1 and 12 product images.")
            if any(not isinstance(image, str) for image in images) or len(set(images)) != len(images):
                raise APIError(400, "Each product image must be a different local image.")
            for image in images:
                self.validate_image_path(image)
            values["images"], values["image"] = json.dumps(images), images[0]
        if "sku" in payload:
            sku = payload["sku"]
            if not isinstance(sku, str) or len(sku.strip()) > 64 or (sku.strip() and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", sku.strip())):
                raise APIError(400, "Use a SKU of up to 64 letters, numbers, dots, dashes or underscores.")
            # A blank SKU on creation is generated; an existing SKU cannot be blanked.
            if sku.strip():
                values["sku"] = sku.strip().upper()
            elif not creating:
                raise APIError(400, "Enter a SKU for this product.")
        if "stock" in payload:
            stock = payload["stock"]
            if stock is not None and (isinstance(stock, bool) or not isinstance(stock, int) or not 0 <= stock <= 999999):
                raise APIError(400, "Enter a stock quantity from 0 to 999,999, or leave stock untracked.")
            values["stock"] = stock
        if "sizes" in payload:
            sizes = payload["sizes"]
            if not isinstance(sizes, list) or not 1 <= len(sizes) <= len(PRODUCT_SIZES):
                raise APIError(400, "Choose at least one available size.")
            if any(not isinstance(size, str) or size not in PRODUCT_SIZES for size in sizes) or len(set(sizes)) != len(sizes):
                raise APIError(400, "Choose distinct sizes from the available size options.")
            values["sizes"] = json.dumps(sizes)
        if "color_hex" in payload:
            if not isinstance(payload["color_hex"], str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", payload["color_hex"]):
                raise APIError(400, "Choose a valid six-digit color.")
            values["color_hex"] = payload["color_hex"].lower()
        return values

    def validate_image_path(self, image):
        if len(image) > 512 or not image.startswith("assets/") or "\\" in image or "%" in image or any(ord(c) < 32 for c in image):
            raise APIError(400, "Choose an uploaded image from this site's assets.")
        parts = image.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise APIError(400, "Choose an uploaded image from this site's assets.")
        target = (self.server.root / image).resolve()
        assets = self.server.root / "assets"
        if target in self.server.private_files or not target.is_relative_to(assets) or target.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"} or not target.is_file():
            raise APIError(400, "Choose an existing JPEG, PNG or WebP image from this site's assets.")

    def record_product_activity(self, connection, user, action, product):
        connection.execute("""
            INSERT INTO product_activity (actor_id,actor_name,action,product_id,product_name,created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user["id"], user["name"], action, product["id"], product["name"], now_iso()))

    def create_product(self, user, payload):
        values = self.validate_product_fields(payload, creating=True)
        product_id, stamp = secrets.token_hex(8), now_iso()
        try:
            with self.server.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                user = self.fresh_security_user(connection, user, admin=True)
                values = {
                    "id": product_id, "published": 0, "stock": None,
                    "sizes": json.dumps(["XS", "S", "M", "L"]), "base_color": "Original",
                    "color_hex": "#d1c8bd", "sku": product_sku(connection, product_id),
                    "color_key": "", "legacy_key": "", "deleted_at": None, "created_at": stamp, "updated_at": stamp,
                    **values,
                }
                columns = ", ".join(values)
                connection.execute(f"INSERT INTO products ({columns}) VALUES ({', '.join('?' for _ in values)})", tuple(values.values()))
                product = connection.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
                self.record_product_activity(connection, user, "create", product)
        except sqlite3.IntegrityError:
            raise APIError(409, "That SKU is already used by another product.")
        self.send_json(201, {"product": public_product(product)})

    def update_product(self, product_id, payload, user):
        values = self.validate_product_fields(payload)
        values["updated_at"] = now_iso()
        assignments = ", ".join(f"{field} = ?" for field in values)
        try:
            with self.server.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                user = self.fresh_security_user(connection, user, admin=True)
                current = connection.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
                if current is None:
                    raise APIError(404, "This product was not found.")
                if current["deleted_at"] is not None:
                    raise APIError(409, "Restore this product from the trash before editing it.")
                connection.execute(f"UPDATE products SET {assignments} WHERE id = ?", (*values.values(), product_id))
                product = connection.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
                self.record_product_activity(connection, user, "update", product)
        except sqlite3.IntegrityError:
            raise APIError(409, "That SKU is already used by another product.")
        self.send_json(200, {"product": public_product(product)})

    def product_action(self, product_id, action, payload, user):
        if payload:
            raise APIError(400, "This product action does not accept extra fields.")
        stamp = now_iso()
        with self.server.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            user = self.fresh_security_user(connection, user, admin=True)
            product = connection.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
            if product is None:
                raise APIError(404, "This product was not found.")
            if action == "restore":
                if product["deleted_at"] is None:
                    raise APIError(409, "This product is not in the trash.")
                connection.execute("UPDATE products SET deleted_at = NULL,published = 0,updated_at = ? WHERE id = ?", (stamp, product_id))
            elif action == "trash":
                if product["deleted_at"] is not None:
                    raise APIError(409, "This product is already in the trash.")
                connection.execute("UPDATE products SET deleted_at = ?,published = 0,updated_at = ? WHERE id = ?", (stamp, stamp, product_id))
            elif action == "duplicate":
                if product["deleted_at"] is not None:
                    raise APIError(409, "Restore this product before duplicating it.")
                values = dict(product)
                product_id = secrets.token_hex(8)
                values.update(id=product_id, name=product["name"][:153] + " (copy)", published=0,
                              sku=product_sku(connection, product_id), legacy_key="", deleted_at=None, created_at=stamp, updated_at=stamp)
                connection.execute(f"INSERT INTO products ({', '.join(values)}) VALUES ({', '.join('?' for _ in values)})", tuple(values.values()))
            product = connection.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
            self.record_product_activity(connection, user, action, product)
        self.send_json(201 if action == "duplicate" else 200, {"product": public_product(product)})

    def upload_image(self, payload, user):
        if set(payload) != {"name", "data"}:
            raise APIError(400, "Choose an image file to upload.")
        if not isinstance(payload["name"], str) or not 1 <= len(payload["name"]) <= 255:
            raise APIError(400, "Choose an image file with a valid name.")
        if not isinstance(payload["data"], str):
            raise APIError(400, "Choose a JPEG, PNG or WebP image.")
        match = re.fullmatch(r"data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=]+)", payload["data"])
        if match is None:
            raise APIError(400, "Choose a JPEG, PNG or WebP image.")
        try:
            data = base64.b64decode(match[2], validate=True)
        except (ValueError, binascii.Error):
            raise APIError(400, "This image could not be read.")
        if not 0 < len(data) <= MAX_UPLOAD_BYTES:
            raise APIError(413, "Choose an image no larger than 8 MB.")
        extension = image_extension(data)
        expected = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
        if extension is None or expected[extension] != match[1]:
            raise APIError(400, "The file is not a valid JPEG, PNG or WebP image.")
        assets = self.server.root / "assets"
        directory = (assets / "uploads").resolve()
        if not directory.is_relative_to(assets):
            raise APIError(500, "The upload folder is unavailable.")
        with self.server.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            user = self.fresh_security_user(connection, user, admin=True)
            directory.mkdir(parents=True, exist_ok=True)
            name = secrets.token_hex(16) + "." + extension
            with (directory / name).open("xb") as stream:
                stream.write(data)
            self.audit("product_image_uploaded", user=user, detail="A product image was uploaded.", connection=connection)
        self.send_json(201, {"image": "assets/uploads/" + name})

    def serve_static(self):
        decoded = unquote(self.path_only)
        if "\\" in decoded or "\x00" in decoded:
            raise APIError(404, "This page was not found.")
        relative = decoded.lstrip("/") or "index.html"
        target = (self.server.root / relative).resolve()
        try:
            target.relative_to(self.server.root)
        except ValueError:
            raise APIError(404, "This page was not found.")
        if target in self.server.private_files:
            raise APIError(404, "This page was not found.")
        public_page = target.parent == self.server.root and target.suffix.lower() in {".html", ".css", ".js"}
        public_asset = target.is_relative_to(self.server.root / "assets") and target.suffix.lower() in {
            ".jpg", ".jpeg", ".png", ".webp", ".avif", ".svg", ".gif", ".ico", ".woff", ".woff2", ".ttf",
        }
        public_asset = public_asset or target == self.server.root / "assets" / "vendor" / "qrcodegen.js"
        if not (public_page or public_asset) or not target.is_file():
            raise APIError(404, "This page was not found.")
        if target.parent == self.server.root and target.name.lower() in {"account.html", "admin.html"}:
            page = target.name.lower()
            user = self.security_session()
            if user is None:
                self.send_response(302)
                self.send_header("Location", "/login.html?next=" + page)
                self.send_header("Content-Length", "0")
                self.send_header("Cache-Control", "no-store")
                self.common_headers()
                self.end_headers()
                return
            if page == "admin.html" and user["role"] != "admin":
                self.audit("permission_denied", user=user, detail="A non-administrator request for the administrator page was rejected.", severity="warning")
                raise APIError(403, "Administrator access is required.")
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or target.suffix == ".js":
            content_type += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(target.stat().st_size))
        self.send_header("Cache-Control", "no-store" if target.name in {"login.html", "register.html", "account.html", "admin.html"} else "no-cache")
        self.common_headers()
        self.end_headers()
        if self.command != "HEAD":
            with target.open("rb") as stream:
                while chunk := stream.read(65536):
                    self.wfile.write(chunk)


def make_server(host="127.0.0.1", port=8000, database=None, catalog=None, root=ROOT, secure_cookies=False):
    if host in {"", "0.0.0.0", "::"}:
        raise ValueError("Use a specific host address so request origins can be verified.")
    root = Path(root)
    return VeloraServer(
        (host, port), database or root / ".velora" / "velora.sqlite3",
        catalog or root / "product-catalog.json", root, secure_cookies,
    )


def create_admin(server):
    print("Create a Velora administrator. Passwords are never displayed or stored as plain text.")
    try:
        name = validate_name(input("Name: "))
        email = validate_email(input("Email: "))
        password = validate_password(getpass.getpass("Password (15–128 characters): "))
        if not hmac.compare_digest(password.encode("utf-8"), getpass.getpass("Confirm password: ").encode("utf-8")):
            raise APIError(400, "The passwords do not match.")
        with server.connect() as connection:
            connection.execute("INSERT INTO users (name, email, password_hash, role, created_at) VALUES (?, ?, ?, 'admin', ?)", (
                name, email, hash_password(password), now_iso(),
            ))
    except sqlite3.IntegrityError:
        raise SystemExit("An account with that email already exists. Use a different email for the administrator.")
    except APIError as error:
        raise SystemExit(error.message)
    print("Administrator created. Sign in at /login.html to open the admin portal.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--database", type=Path, default=ROOT / ".velora" / "velora.sqlite3")
    parser.add_argument("--create-admin", action="store_true")
    parser.add_argument("--secure-cookies", action="store_true", help="Use only when served through a trusted HTTPS endpoint.")
    args = parser.parse_args()
    try:
        server = make_server(args.host, 0 if args.create_admin else args.port, args.database, secure_cookies=args.secure_cookies)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Unable to start Velora: {error}\n")
    try:
        if args.create_admin:
            create_admin(server)
            return
        print(f"Velora is running at http://{args.host}:{server.server_port}")
        print("Local development server. Press Ctrl+C to stop.")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nVelora stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
