"""Account-backed public reviews and private, metadata-free review photographs.

No image-processing dependency is needed by the bundled Python runtime. Raster
containers are checked structurally and their metadata segments are removed.
The client also resizes/re-encodes photographs before uploading them.
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import re
import secrets
import struct
import time
from urllib.parse import parse_qs, urlsplit
import zlib


MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_BODY = 7 * 1024 * 1024 + 2048
UPLOAD_LIFETIME = 24 * 60 * 60
REVIEW_COLUMNS = "r.*,u.name AS account_name"
REVIEW_JOIN = "customer_reviews r JOIN users u ON u.id=r.user_id"


class ReviewError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def initialize(connection):
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS review_uploads (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            data BLOB NOT NULL,
            mime TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS review_uploads_user ON review_uploads(user_id);
        CREATE TABLE IF NOT EXISTS customer_reviews (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            id TEXT NOT NULL UNIQUE,
            user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            title TEXT NOT NULL DEFAULT '',
            body TEXT NOT NULL,
            anonymous INTEGER NOT NULL DEFAULT 0 CHECK(anonymous IN (0,1)),
            image_id TEXT UNIQUE REFERENCES review_uploads(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    cleanup_uploads(connection)


def cleanup_uploads(connection):
    connection.execute("""DELETE FROM review_uploads WHERE created_at<=?
        AND id NOT IN (SELECT image_id FROM customer_reviews WHERE image_id IS NOT NULL)""",
        (int(time.time()) - UPLOAD_LIFETIME,))


def public_review(row):
    return {
        "id": row["id"], "rating": row["rating"], "title": row["title"],
        "body": row["body"], "authorName": "Anonymous" if row["anonymous"] else row["account_name"],
        "anonymous": bool(row["anonymous"]),
        "image": "/api/reviews/images/" + row["image_id"] if row["image_id"] else None,
        "createdAt": row["created_at"],
    }


def strip_png(data):
    result = bytearray(data[:8])
    position, seen_header, seen_data, ended = 8, False, False, False
    allowed = {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"gAMA", b"cHRM", b"sRGB"}
    while position < len(data):
        if position + 12 > len(data):
            raise ValueError("Truncated PNG")
        size = int.from_bytes(data[position:position + 4], "big")
        end = position + size + 12
        if end > len(data):
            raise ValueError("Invalid PNG chunk")
        kind = data[position + 4:position + 8]
        payload = data[position + 8:end - 4]
        if not re.fullmatch(b"[A-Za-z]{4}", kind):
            raise ValueError("Invalid PNG chunk type")
        if zlib.crc32(kind + payload) != int.from_bytes(data[end - 4:end], "big"):
            raise ValueError("Invalid PNG checksum")
        if not seen_header and (kind != b"IHDR" or size != 13):
            raise ValueError("Missing PNG header")
        if kind == b"IHDR":
            if seen_header or size != 13:
                raise ValueError("Duplicate PNG header")
            seen_header = True
        elif kind == b"IDAT":
            seen_data = True
        elif kind == b"IEND":
            if size or end != len(data) or not seen_data:
                raise ValueError("Invalid PNG end")
            ended = True
        elif not kind[0] & 32 and kind not in allowed:
            raise ValueError("Unsupported critical PNG chunk")
        if kind in allowed:
            result.extend(data[position:end])
        position = end
    if not ended:
        raise ValueError("Missing PNG end")
    return bytes(result)


def strip_jpeg(data):
    result = bytearray(b"\xff\xd8")
    position, saw_scan = 2, False
    while position < len(data):
        start = position
        if data[position] != 255:
            raise ValueError("Invalid JPEG marker")
        while position < len(data) and data[position] == 255:
            position += 1
        if position >= len(data):
            raise ValueError("Incomplete JPEG marker")
        marker, position = data[position], position + 1
        if marker == 0xD9:
            if position != len(data) or not saw_scan:
                raise ValueError("Invalid JPEG end")
            result.extend(b"\xff\xd9")
            return bytes(result)
        if marker in {0, 0xD8} or 0xD0 <= marker <= 0xD7:
            raise ValueError("Unexpected JPEG marker")
        if marker == 1:
            result.extend(data[start:position])
            continue
        if position + 2 > len(data):
            raise ValueError("Missing JPEG segment size")
        size = int.from_bytes(data[position:position + 2], "big")
        end = position + size
        if size < 2 or end > len(data):
            raise ValueError("Invalid JPEG segment")
        # APP containers and comments may contain EXIF, GPS, XMP or IPTC names.
        if not (0xE0 <= marker <= 0xEF or marker == 0xFE):
            result.extend(data[start:end])
        position = end
        if marker == 0xDA:
            saw_scan = True
            scan_start = position
            while position < len(data):
                if data[position] != 255:
                    position += 1
                    continue
                candidate = position
                while position < len(data) and data[position] == 255:
                    position += 1
                if position >= len(data):
                    raise ValueError("Incomplete JPEG scan")
                if data[position] == 0 or 0xD0 <= data[position] <= 0xD7:
                    position += 1
                    continue
                result.extend(data[scan_start:candidate])
                position = candidate
                break
    raise ValueError("Missing JPEG end")


def strip_webp(data):
    chunks, position, compressed = [], 12, 0
    while position < len(data):
        if position + 8 > len(data):
            raise ValueError("Truncated WebP")
        kind = data[position:position + 4]
        size = int.from_bytes(data[position + 4:position + 8], "little")
        end = position + 8 + size
        padded = end + size % 2
        if padded > len(data):
            raise ValueError("Invalid WebP chunk")
        payload = data[position + 8:end]
        if kind in {b"ANIM", b"ANMF"}:
            raise ValueError("Choose a still photo")
        if kind == b"VP8X":
            if size != 10 or payload[0] & 2:
                raise ValueError("Unsupported WebP")
            payload = bytes([payload[0] & ~(0x20 | 0x08 | 0x04)]) + payload[1:]
        if kind in {b"VP8 ", b"VP8L"}:
            compressed += 1
        if kind in {b"VP8X", b"VP8 ", b"VP8L", b"ALPH"}:
            chunks.append(kind + struct.pack("<I", len(payload)) + payload + (b"\0" if len(payload) % 2 else b""))
        position = padded
    if compressed != 1:
        raise ValueError("Missing WebP photograph")
    content = b"WEBP" + b"".join(chunks)
    return b"RIFF" + struct.pack("<I", len(content)) + content


def clean_image(payload, image_extension):
    if set(payload) != {"name", "data"} or not isinstance(payload.get("name"), str) or not 1 <= len(payload["name"]) <= 255:
        raise ReviewError(400, "Choose a JPEG, PNG or WebP photo.")
    value = payload.get("data")
    match = re.fullmatch(r"data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=]+)", value) if isinstance(value, str) else None
    if not match:
        raise ReviewError(400, "Choose a JPEG, PNG or WebP photo.")
    try:
        data = base64.b64decode(match[2], validate=True)
    except (ValueError, binascii.Error):
        raise ReviewError(400, "This photo could not be read.")
    if not 0 < len(data) <= MAX_IMAGE_BYTES:
        raise ReviewError(413, "Choose a photo no larger than 5 MB.")
    extension = image_extension(data)
    if extension is None or {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}[extension] != match[1]:
        raise ReviewError(400, "The file is not a valid JPEG, PNG or WebP photo.")
    try:
        data = {"png": strip_png, "jpg": strip_jpeg, "webp": strip_webp}[extension](data)
        if image_extension(data) != extension:
            raise ValueError("Invalid cleaned photo")
    except (ValueError, IndexError, OverflowError):
        raise ReviewError(400, "This photo could not be read. Choose a different still photo.")
    return data, match[1]


def validate_review(payload, creating):
    if set(payload) - {"rating", "title", "body", "anonymous", "image"}:
        raise ReviewError(400, "Some review fields are not supported.")
    if not {"rating", "body", "anonymous"}.issubset(payload):
        raise ReviewError(400, "Add a star rating, review and posting preference.")
    rating, body, anonymous = payload["rating"], payload["body"], payload["anonymous"]
    title = payload.get("title", "")
    if type(rating) is not int or not 1 <= rating <= 5:
        raise ReviewError(400, "Choose a rating from 1 to 5 stars.")
    if not isinstance(body, str) or not 20 <= len(body.strip()) <= 2000:
        raise ReviewError(400, "Write a review between 20 and 2,000 characters.")
    if not isinstance(title, str) or len(title.strip()) > 100:
        raise ReviewError(400, "Keep the review title within 100 characters.")
    if type(anonymous) is not bool:
        raise ReviewError(400, "Choose whether to post anonymously.")
    if any(ord(character) < 32 and character not in "\n\r\t" for character in body + title):
        raise ReviewError(400, "Remove unsupported characters from your review.")
    image = payload.get("image")
    if image is not None and (not isinstance(image, str) or not re.fullmatch(r"[0-9a-f]{32}", image)):
        raise ReviewError(400, "Upload a review photo before attaching it.")
    return {"rating": rating, "title": title.strip(), "body": body.strip(), "anonymous": int(anonymous)}, "image" in payload or creating, image


def list_reviews(handler):
    query = parse_qs(urlsplit(handler.path).query, keep_blank_values=True)
    if set(query) - {"limit", "cursor"} or any(len(values) != 1 for values in query.values()):
        raise ReviewError(400, "Choose valid review pagination.")
    limit = query.get("limit", ["12"])[0]
    if not re.fullmatch(r"[0-9]{1,2}", limit) or not 1 <= int(limit) <= 24:
        raise ReviewError(400, "Choose a review page size from 1 to 24.")
    limit = int(limit)
    before = 9_223_372_036_854_775_807
    if "cursor" in query:
        cursor = query["cursor"][0]
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", cursor):
            raise ReviewError(400, "This review page could not be found.")
        try:
            raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode("ascii")
            if not re.fullmatch(r"[0-9]{1,19}", raw) or not 1 <= int(raw) <= before:
                raise ValueError()
            before = int(raw)
        except (ValueError, UnicodeError, binascii.Error):
            raise ReviewError(400, "This review page could not be found.")
    with handler.server.connect() as connection:
        connection.execute("BEGIN")
        rows = connection.execute(f"SELECT {REVIEW_COLUMNS} FROM {REVIEW_JOIN} WHERE r.sequence<? ORDER BY r.sequence DESC LIMIT ?", (before, limit + 1)).fetchall()
        aggregate = connection.execute("SELECT COUNT(*) AS count,AVG(rating) AS average FROM customer_reviews").fetchone()
        distribution = {str(star): 0 for star in range(1, 6)}
        for row in connection.execute("SELECT rating,COUNT(*) AS count FROM customer_reviews GROUP BY rating"):
            distribution[str(row["rating"])] = row["count"]
    next_cursor = base64.urlsafe_b64encode(str(rows[limit - 1]["sequence"]).encode("ascii")).rstrip(b"=").decode("ascii") if len(rows) > limit else None
    return handler.send_json(200, {"reviews": [public_review(row) for row in rows[:limit]], "summary": {
        "count": aggregate["count"], "average": round(aggregate["average"] or 0, 1), "distribution": distribution,
    }, "nextCursor": next_cursor})


def handle(handler, method, image_extension):
    path = handler.path_only
    reading = method in {"GET", "HEAD"}
    if path == "/api/reviews" and reading:
        return list_reviews(handler)
    if path == "/api/reviews/mine" and reading:
        user = handler.require_user()
        with handler.server.connect() as connection:
            row = connection.execute(f"SELECT {REVIEW_COLUMNS} FROM {REVIEW_JOIN} WHERE r.user_id=?", (user["id"],)).fetchone()
        return handler.send_json(200, {"review": public_review(row) if row else None})
    image = re.fullmatch(r"/api/reviews/images/([0-9a-f]{32})", path)
    if image and reading:
        with handler.server.connect() as connection:
            row = connection.execute("""SELECT p.data,p.mime FROM review_uploads p
                JOIN customer_reviews r ON r.image_id=p.id WHERE p.id=?""", (image[1],)).fetchone()
        if row is None:
            raise ReviewError(404, "This review photo was not found.")
        handler.send_response(200)
        handler.send_header("Content-Type", row["mime"])
        handler.send_header("Content-Length", str(len(row["data"])))
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("Content-Disposition", "inline")
        handler.common_headers()
        handler.end_headers()
        if method != "HEAD":
            handler.wfile.write(row["data"])
        return
    review = re.fullmatch(r"/api/reviews/([0-9a-f]{32})", path)
    writing = (path == "/api/reviews" and method == "POST") or (review and method in {"PATCH", "DELETE"})
    uploading = path == "/api/reviews/uploads" and method == "POST"
    if not writing and not uploading:
        known = path in {"/api/reviews", "/api/reviews/mine", "/api/reviews/uploads"} or review or image
        raise ReviewError(405 if known else 404, "This method is not supported." if known else "This page was not found.")
    user = handler.require_user(csrf=True)
    handler.server.rate_limit(("review-upload" if uploading else "review-write", user["id"]), 20 if uploading else 30, 3600)
    payload = handler.read_json(MAX_IMAGE_BODY if uploading else 16384)
    if uploading:
        data, mime = clean_image(payload, image_extension)
        token = secrets.token_hex(16)
        with handler.server.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            user = handler.fresh_security_user(connection, user)
            cleanup_uploads(connection)
            connection.execute("DELETE FROM review_uploads WHERE user_id=? AND id NOT IN (SELECT image_id FROM customer_reviews WHERE image_id IS NOT NULL)", (user["id"],))
            connection.execute("INSERT INTO review_uploads (id,user_id,data,mime,created_at) VALUES (?,?,?,?,?)", (token, user["id"], data, mime, int(time.time())))
        return handler.send_json(201, {"uploadToken": token})
    if method == "DELETE" and payload:
        raise ReviewError(400, "Delete the review without additional fields.")
    values, set_image, image_id = validate_review(payload, method == "POST") if method != "DELETE" else ({}, False, None)
    with handler.server.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        user = handler.fresh_security_user(connection, user)
        cleanup_uploads(connection)
        current = connection.execute("SELECT * FROM customer_reviews WHERE id=? AND user_id=?", (review[1], user["id"])).fetchone() if review else None
        if review and current is None:
            raise ReviewError(404, "This review was not found in your account.")
        if method == "POST" and connection.execute("SELECT 1 FROM customer_reviews WHERE user_id=?", (user["id"],)).fetchone():
            raise ReviewError(409, "You already have a review. Edit your existing review instead.")
        if set_image and image_id:
            upload = connection.execute("SELECT * FROM review_uploads WHERE id=? AND user_id=?", (image_id, user["id"])).fetchone()
            attached = connection.execute("SELECT id FROM customer_reviews WHERE image_id=?", (image_id,)).fetchone()
            if upload is None or (attached and (current is None or attached["id"] != current["id"])) or (not attached and upload["created_at"] <= int(time.time()) - UPLOAD_LIFETIME):
                raise ReviewError(400, "Upload your own photo again before attaching it.")
        review_id = current["id"] if current else secrets.token_hex(16)
        old_image = current["image_id"] if current else None
        if method == "DELETE":
            connection.execute("DELETE FROM customer_reviews WHERE id=?", (review_id,))
        elif method == "POST":
            created = stamp()
            connection.execute("""INSERT INTO customer_reviews (id,user_id,rating,title,body,anonymous,image_id,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""", (review_id, user["id"], values["rating"], values["title"], values["body"], values["anonymous"], image_id, created, created))
        else:
            if set_image:
                values["image_id"] = image_id
            connection.execute(f"UPDATE customer_reviews SET {','.join(field + '=?' for field in values)},updated_at=? WHERE id=?", (*values.values(), stamp(), review_id))
        if old_image and (method == "DELETE" or set_image and old_image != image_id):
            connection.execute("DELETE FROM review_uploads WHERE id=?", (old_image,))
        event = {"POST": "review_created", "PATCH": "review_updated", "DELETE": "review_deleted"}[method]
        handler.audit(event, user=user, detail="A customer review was " + {"POST": "published.", "PATCH": "updated.", "DELETE": "deleted."}[method], connection=connection)
        row = connection.execute(f"SELECT {REVIEW_COLUMNS} FROM {REVIEW_JOIN} WHERE r.id=?", (review_id,)).fetchone() if method != "DELETE" else None
    return handler.send_json(201 if method == "POST" else 200, {"review": public_review(row)} if row else {"deleted": True})
