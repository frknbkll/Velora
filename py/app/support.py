"""Private customer/staff conversations with short polling and guest sessions."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import hmac
from http.cookies import CookieError, SimpleCookie
import re
import secrets
import time
from urllib.parse import parse_qs, urlsplit

import commerce
from security_core import ADMIN_ABSOLUTE_SECONDS, ADMIN_IDLE_SECONDS


COOKIE_NAME = "velora_support"
GUEST_SESSION_SECONDS = 7 * 24 * 60 * 60
GUEST_RETENTION_SECONDS = 30 * 24 * 60 * 60
PRESENCE_SECONDS = 45
MAX_INTEGER = 9_223_372_036_854_775_807


class SupportError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def initialize(connection):
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS support_guests (
            id TEXT PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            csrf_token TEXT NOT NULL,
            name TEXT NOT NULL DEFAULT 'Guest',
            expires_at INTEGER NOT NULL,
            last_seen INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS support_conversations (
            id TEXT PRIMARY KEY,
            user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            guest_id TEXT UNIQUE REFERENCES support_guests(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_message_id INTEGER NOT NULL DEFAULT 0,
            customer_read INTEGER NOT NULL DEFAULT 0,
            staff_read INTEGER NOT NULL DEFAULT 0,
            CHECK((user_id IS NOT NULL AND guest_id IS NULL) OR (user_id IS NULL AND guest_id IS NOT NULL))
        );
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL REFERENCES support_conversations(id) ON DELETE CASCADE,
            sender TEXT NOT NULL CHECK(sender IN ('customer','staff')),
            sender_key TEXT NOT NULL,
            author_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            body TEXT NOT NULL,
            client_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(conversation_id,sender_key,client_id)
        );
        CREATE INDEX IF NOT EXISTS support_messages_thread ON support_messages(conversation_id,id);
        CREATE INDEX IF NOT EXISTS support_conversations_activity ON support_conversations(last_message_id DESC,id DESC);
        CREATE TABLE IF NOT EXISTS support_presence (
            session_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            lease_until INTEGER NOT NULL
        );
    """)
    cleanup(connection)


def cleanup(connection):
    now = int(time.time())
    connection.execute("DELETE FROM support_guests WHERE last_seen<=?", (now - GUEST_RETENTION_SECONDS,))
    connection.execute("DELETE FROM support_presence WHERE lease_until<=? OR session_hash NOT IN (SELECT token_hash FROM sessions)", (now,))


def availability(connection):
    now = int(time.time())
    rows = connection.execute("""SELECT u.* FROM support_presence p JOIN users u ON u.id=p.user_id
        JOIN sessions s ON s.token_hash=p.session_hash AND s.user_id=u.id
        WHERE p.lease_until>? AND s.expires_at>? AND s.auth_version=u.auth_version
        AND u.role='admin' AND s.last_seen>? AND s.created_at>?""",
        (now, now, now - ADMIN_IDLE_SECONDS, now - ADMIN_ABSOLUTE_SECONDS)).fetchall()
    return {"online": any(commerce.role(connection, user) in {"owner", "manager"} for user in rows)}


def guest_cookie(token, secure=False):
    return f"{COOKIE_NAME}={token}; Path=/api/support; Max-Age={GUEST_SESSION_SECONDS}; HttpOnly; SameSite=Strict" + ("; Secure" if secure else "")


def guest_token(handler):
    raw = handler.headers.get("Cookie", "")
    if len(re.findall(r"(?:^|;)\s*" + COOKIE_NAME + r"\s*=", raw)) > 1:
        raise SupportError(401, "Open support again to start a new session.")
    try:
        cookie = SimpleCookie()
        cookie.load(raw)
        value = cookie[COOKIE_NAME].value if COOKIE_NAME in cookie else ""
    except CookieError:
        value = ""
    return value if re.fullmatch(r"[A-Za-z0-9_-]{43}", value) else None


def principal(handler, create=False, csrf=False):
    user = handler.session()
    if user is not None:
        if csrf:
            user = handler.require_user(csrf=True)
        return {"user": user, "guest": None, "key": f"user:{user['id']}"}, None
    token = guest_token(handler)
    now = int(time.time())
    with handler.server.connect() as connection:
        guest = connection.execute("SELECT * FROM support_guests WHERE token_hash=? AND expires_at>?",
            (hashlib.sha256(token.encode()).hexdigest(), now)).fetchone() if token else None
        cookie = None
        if guest is None and create:
            handler.server.rate_limit(("support-session", handler.client_address[0]), 20, 3600)
            cleanup(connection)
            token, guest_id, csrf_token = secrets.token_urlsafe(32), secrets.token_hex(16), secrets.token_urlsafe(32)
            connection.execute("INSERT INTO support_guests VALUES (?,?,?,?,?,?)",
                (guest_id, hashlib.sha256(token.encode()).hexdigest(), csrf_token, "Guest", now + GUEST_SESSION_SECONDS, now))
            guest = connection.execute("SELECT * FROM support_guests WHERE id=?", (guest_id,)).fetchone()
            cookie = guest_cookie(token, handler.server.secure_cookies)
        if guest is None:
            raise SupportError(401, "Open support again to start a new session.")
        if csrf and (len(handler.headers.get_all("X-CSRF-Token", [])) != 1 or not hmac.compare_digest(
                handler.headers.get("X-CSRF-Token", "").encode(), guest["csrf_token"].encode())):
            raise SupportError(403, "Your support session could not be verified. Open support again.")
        if create:
            connection.execute("UPDATE support_guests SET last_seen=? WHERE id=?", (now, guest["id"]))
    return {"user": None, "guest": guest, "key": f"guest:{guest['id']}"}, cookie


def fresh_principal(handler, connection, person):
    if person["user"] is not None:
        user = handler.fresh_security_user(connection, person["user"])
        return {**person, "user": user}
    guest = connection.execute("SELECT * FROM support_guests WHERE id=? AND token_hash=? AND expires_at>?",
        (person["guest"]["id"], person["guest"]["token_hash"], int(time.time()))).fetchone()
    if guest is None:
        raise SupportError(401, "Open support again to start a new session.")
    return {**person, "guest": guest}


def staff_user(handler, csrf=False):
    return handler.require_user(admin=True, csrf=csrf)


def fresh_staff(handler, connection, user):
    user = handler.fresh_security_user(connection, user, admin=True)
    if commerce.role(connection, user) not in {"owner", "manager"}:
        raise SupportError(403, "Your staff role does not permit customer support access.")
    return user


def own_thread(connection, person):
    column, value = ("user_id", person["user"]["id"]) if person["user"] is not None else ("guest_id", person["guest"]["id"])
    return connection.execute(f"SELECT * FROM support_conversations WHERE {column}=?", (value,)).fetchone()


def customer_name(connection, thread):
    if thread["user_id"] is not None:
        row = connection.execute("SELECT name FROM users WHERE id=?", (thread["user_id"],)).fetchone()
    else:
        row = connection.execute("SELECT name FROM support_guests WHERE id=?", (thread["guest_id"],)).fetchone()
    return row["name"] if row else "Customer"


def message_payload(connection, message, name):
    if message["sender"] == "staff":
        author = connection.execute("SELECT name FROM users WHERE id=?", (message["author_id"],)).fetchone()
        author_name = author["name"] if author else "Velora support"
    else:
        author_name = name
    return {"id": message["id"], "body": message["body"], "sender": message["sender"],
        "authorName": author_name, "createdAt": message["created_at"]}


def summary(connection, thread, staff=False):
    if thread is None:
        return None
    name = customer_name(connection, thread)
    last = connection.execute("SELECT * FROM support_messages WHERE id=? AND conversation_id=?",
        (thread["last_message_id"], thread["id"])).fetchone()
    cursor = thread["staff_read" if staff else "customer_read"]
    unread = connection.execute("SELECT COUNT(*) FROM support_messages WHERE conversation_id=? AND sender=? AND id>?",
        (thread["id"], "customer" if staff else "staff", cursor)).fetchone()[0]
    return {"id": thread["id"], "customerName": name, "status": thread["status"], "updatedAt": thread["updated_at"],
        "lastMessage": message_payload(connection, last, name) if last else None, "unreadCount": unread}


def query_values(handler, allowed):
    values = parse_qs(urlsplit(handler.path).query, keep_blank_values=True)
    if set(values) - allowed or any(len(items) != 1 for items in values.values()):
        raise SupportError(400, "Choose valid support pagination.")
    return {key: items[0] for key, items in values.items()}


def integer(value, label, minimum=0, maximum=MAX_INTEGER):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,19}", value) or not minimum <= int(value) <= maximum:
        raise SupportError(400, f"Choose a valid {label}.")
    return int(value)


def thread_envelope(connection, thread, handler, staff=False):
    query = query_values(handler, {"after", "before", "limit"})
    if "after" in query and "before" in query:
        raise SupportError(400, "Choose one message cursor.")
    limit = integer(query.get("limit", "50"), "message page size", 1, 100)
    after = integer(query["after"], "message cursor") if "after" in query else None
    before = integer(query["before"], "message cursor", 1) if "before" in query else None
    messages, has_more, has_earlier = [], False, False
    if thread is not None:
        if after is not None:
            rows = connection.execute("SELECT * FROM support_messages WHERE conversation_id=? AND id>? ORDER BY id LIMIT ?",
                (thread["id"], after, limit + 1)).fetchall()
            messages, has_more = rows[:limit], len(rows) > limit
        else:
            rows = connection.execute("SELECT * FROM support_messages WHERE conversation_id=? AND id<? ORDER BY id DESC LIMIT ?",
                (thread["id"], before or MAX_INTEGER, limit + 1)).fetchall()
            messages, has_earlier = list(reversed(rows[:limit])), len(rows) > limit
    name = customer_name(connection, thread) if thread else "Customer"
    return {"conversation": summary(connection, thread, staff),
        "messages": [message_payload(connection, message, name) for message in messages],
        "hasMore": has_more, "nextAfter": messages[-1]["id"] if messages else after or 0,
        "hasEarlier": has_earlier, "nextBefore": messages[0]["id"] if has_earlier else None,
        "availability": availability(connection)}


def read_cursor(connection, thread, payload, staff=False):
    through = payload.get("through")
    if set(payload) != {"through"} or type(through) is not int or not 1 <= through <= MAX_INTEGER:
        raise SupportError(400, "Choose a message to mark as read.")
    if thread is None or connection.execute("SELECT 1 FROM support_messages WHERE id=? AND conversation_id=?", (through, thread["id"])).fetchone() is None:
        raise SupportError(404, "This support message was not found.")
    column = "staff_read" if staff else "customer_read"
    connection.execute(f"UPDATE support_conversations SET {column}=MAX({column},?) WHERE id=?", (through, thread["id"]))


def message_values(payload, guest=False):
    if set(payload) - ({"body", "clientId", "name"} if guest else {"body", "clientId"}):
        raise SupportError(400, "Some support message fields are not supported.")
    body, client_id = payload.get("body"), payload.get("clientId")
    if not isinstance(body, str) or not 1 <= len(body.strip()) <= 2000 or any(ord(char) < 32 and char not in "\n\r\t" for char in body):
        raise SupportError(400, "Write a message between 1 and 2,000 characters.")
    if not isinstance(client_id, str) or not re.fullmatch(r"(?:[A-Za-z0-9]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})", client_id):
        raise SupportError(400, "Add a valid message identifier before sending.")
    name = payload.get("name")
    if name is not None and (not isinstance(name, str) or not 1 <= len(name.strip()) <= 80 or any(ord(char) < 32 for char in name)):
        raise SupportError(400, "Choose a display name up to 80 characters.")
    return body.strip(), client_id, name.strip() if name is not None else None


def create_message(connection, thread, body, client_id, sender, sender_key, author_id):
    existing = connection.execute("SELECT * FROM support_messages WHERE conversation_id=? AND sender_key=? AND client_id=?",
        (thread["id"], sender_key, client_id)).fetchone()
    if existing:
        if existing["body"] != body:
            raise SupportError(409, "This message identifier was already used. Start a new message.")
        return existing
    created = stamp()
    message_id = connection.execute("INSERT INTO support_messages (conversation_id,sender,sender_key,author_id,body,client_id,created_at) VALUES (?,?,?,?,?,?,?)",
        (thread["id"], sender, sender_key, author_id, body, client_id, created)).lastrowid
    connection.execute("UPDATE support_conversations SET updated_at=?,last_message_id=?,status='open' WHERE id=?", (created, message_id, thread["id"]))
    return connection.execute("SELECT * FROM support_messages WHERE id=?", (message_id,)).fetchone()


def list_threads(handler, connection):
    query = query_values(handler, {"status", "limit", "before"})
    status = query.get("status", "open")
    if status not in {"open", "closed", "all"}:
        raise SupportError(400, "Choose open, closed or all conversations.")
    limit = integer(query.get("limit", "50"), "conversation page size", 1, 100)
    cursor_id, cursor_message = "f" * 32, MAX_INTEGER
    if "before" in query:
        cursor = query["before"]
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", cursor):
            raise SupportError(400, "Choose a valid conversation cursor.")
        try:
            decoded = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode("ascii")
            parts = decoded.split("|")
            if len(parts) != 2 or not re.fullmatch(r"[0-9a-f]{32}", parts[1]):
                raise ValueError()
            cursor_message, cursor_id = integer(parts[0], "conversation cursor"), parts[1]
        except (ValueError, UnicodeError):
            raise SupportError(400, "Choose a valid conversation cursor.")
    rows = connection.execute("""SELECT * FROM support_conversations WHERE (?='all' OR status=?)
        AND (last_message_id<? OR (last_message_id=? AND id<?)) ORDER BY last_message_id DESC,id DESC LIMIT ?""",
        (status, status, cursor_message, cursor_message, cursor_id, limit + 1)).fetchall()
    next_cursor = base64.urlsafe_b64encode(f"{rows[limit - 1]['last_message_id']}|{rows[limit - 1]['id']}".encode()).rstrip(b"=").decode() if len(rows) > limit else None
    unread = connection.execute("SELECT COUNT(*) FROM support_messages m JOIN support_conversations c ON c.id=m.conversation_id WHERE m.sender='customer' AND m.id>c.staff_read").fetchone()[0]
    return {"conversations": [summary(connection, row, True) for row in rows[:limit]], "nextCursor": next_cursor, "unreadCount": unread}


def handle_customer(handler, method):
    path = handler.path_only
    reading = method in {"GET", "HEAD"}
    if path == "/api/support/session" and reading:
        query_values(handler, set())
        person, cookie = principal(handler, create=True)
        with handler.server.connect() as connection:
            connection.execute("BEGIN")
            person = fresh_principal(handler, connection, person)
            thread = own_thread(connection, person)
            identity = person["user"] or person["guest"]
            result = {"csrfToken": identity["csrf_token"], "customer": {"name": identity["name"], "guest": person["user"] is None},
                "conversation": summary(connection, thread), "availability": availability(connection)}
        return handler.send_json(200, result, cookie=cookie)
    if path == "/api/support/conversation" and reading:
        # The widget binds every history poll to the identity it opened with.
        # Headerless API clients still read only the current cookie principal.
        person, _ = principal(handler, csrf=handler.headers.get("X-CSRF-Token") is not None)
        with handler.server.connect() as connection:
            connection.execute("BEGIN")
            person = fresh_principal(handler, connection, person)
            return handler.send_json(200, thread_envelope(connection, own_thread(connection, person), handler))
    if not ((path == "/api/support/messages" and method == "POST") or
            (path == "/api/support/read" and method == "POST") or
            (path == "/api/support/conversation" and method == "DELETE")):
        raise SupportError(405 if path in {"/api/support/session", "/api/support/conversation", "/api/support/messages", "/api/support/read"} else 404, "This support request is not available.")
    person, _ = principal(handler, csrf=True)
    handler.server.rate_limit(("support-message" if path.endswith("messages") else "support-update", person["key"]), 60, 60)
    payload = handler.read_json()
    values = message_values(payload, person["guest"] is not None) if path.endswith("messages") else None
    with handler.server.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        cleanup(connection)
        person = fresh_principal(handler, connection, person)
        if person["guest"] is not None:
            connection.execute("UPDATE support_guests SET last_seen=? WHERE id=?", (int(time.time()), person["guest"]["id"]))
        thread = own_thread(connection, person)
        if method == "DELETE":
            if payload:
                raise SupportError(400, "Delete the conversation without additional fields.")
            if thread:
                connection.execute("DELETE FROM support_conversations WHERE id=?", (thread["id"],))
            if person["guest"] is not None:
                connection.execute("UPDATE support_guests SET name='Guest' WHERE id=?", (person["guest"]["id"],))
            return handler.send_json(200, {"deleted": True})
        if path.endswith("read"):
            read_cursor(connection, thread, payload)
            thread = own_thread(connection, person)
            return handler.send_json(200, {"conversation": summary(connection, thread)})
        body, client_id, name = values
        if name is not None:
            connection.execute("UPDATE support_guests SET name=? WHERE id=?", (name, person["guest"]["id"]))
        if thread is None:
            thread_id, created = secrets.token_hex(16), stamp()
            connection.execute("INSERT INTO support_conversations(id,user_id,guest_id,created_at,updated_at) VALUES (?,?,?,?,?)",
                (thread_id, person["user"]["id"] if person["user"] is not None else None,
                 person["guest"]["id"] if person["guest"] is not None else None, created, created))
            thread = own_thread(connection, person)
        message = create_message(connection, thread, body, client_id, "customer", person["key"], person["user"]["id"] if person["user"] is not None else None)
        thread = own_thread(connection, person)
        result = {"conversation": summary(connection, thread), "message": message_payload(connection, message, customer_name(connection, thread))}
    return handler.send_json(201, result)


def handle_staff(handler, method):
    path, reading = handler.path_only, method in {"GET", "HEAD"}
    thread_match = re.fullmatch(r"/api/admin/support/([0-9a-f]{32})(?:/(messages|read))?", path)
    if path not in {"/api/admin/support", "/api/admin/support/presence"} and not thread_match:
        raise SupportError(404, "This support request was not found.")
    writing = (path == "/api/admin/support/presence" and method == "POST") or (thread_match and (
        thread_match[2] in {"messages", "read"} and method == "POST" or thread_match[2] is None and method == "PATCH"))
    if not writing and not (reading and (path == "/api/admin/support" or thread_match and thread_match[2] is None)):
        raise SupportError(405, "This support method is not supported.")
    user = staff_user(handler, csrf=bool(writing))
    payload = handler.read_json() if writing else None
    if writing:
        handler.server.rate_limit(("support-staff", user["id"]), 180, 60)
    with handler.server.connect() as connection:
        connection.execute("BEGIN IMMEDIATE" if writing else "BEGIN")
        user = fresh_staff(handler, connection, user)
        if path == "/api/admin/support" and reading:
            return handler.send_json(200, list_threads(handler, connection))
        if path == "/api/admin/support/presence":
            if set(payload) != {"available"} or type(payload["available"]) is not bool:
                raise SupportError(400, "Choose whether you are available for support.")
            cleanup(connection)
            connection.execute("DELETE FROM support_presence WHERE session_hash=?", (user["token_hash"],))
            if payload["available"]:
                connection.execute("INSERT INTO support_presence VALUES (?,?,?)", (user["token_hash"], user["id"], int(time.time()) + PRESENCE_SECONDS))
            return handler.send_json(200, {"availability": availability(connection), "expiresIn": PRESENCE_SECONDS})
        thread = connection.execute("SELECT * FROM support_conversations WHERE id=?", (thread_match[1],)).fetchone()
        if thread is None:
            raise SupportError(404, "This conversation was not found.")
        if reading:
            return handler.send_json(200, thread_envelope(connection, thread, handler, True))
        if thread_match[2] == "messages":
            body, client_id, _ = message_values(payload)
            message = create_message(connection, thread, body, client_id, "staff", f"staff:{user['id']}", user["id"])
            thread = connection.execute("SELECT * FROM support_conversations WHERE id=?", (thread["id"],)).fetchone()
            result = {"conversation": summary(connection, thread, True), "message": message_payload(connection, message, customer_name(connection, thread))}
            status = 201
        elif thread_match[2] == "read":
            read_cursor(connection, thread, payload, True)
            thread = connection.execute("SELECT * FROM support_conversations WHERE id=?", (thread["id"],)).fetchone()
            result, status = {"conversation": summary(connection, thread, True)}, 200
        else:
            if set(payload) != {"status"} or payload.get("status") not in {"open", "closed"}:
                raise SupportError(400, "Choose an open or closed conversation.")
            connection.execute("UPDATE support_conversations SET status=?,updated_at=? WHERE id=?", (payload["status"], stamp(), thread["id"]))
            thread = connection.execute("SELECT * FROM support_conversations WHERE id=?", (thread["id"],)).fetchone()
            result, status = {"conversation": summary(connection, thread, True)}, 200
    return handler.send_json(status, result)


def handle(handler, method):
    if handler.path_only.startswith("/api/admin/support"):
        return handle_staff(handler, method)
    return handle_customer(handler, method)
