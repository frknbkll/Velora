"""Account security primitives and handlers. No authentication secrets are logged."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import sqlite3
import struct
import time
from urllib.parse import quote, urlencode


ADMIN_IDLE_SECONDS = 1800
ADMIN_ABSOLUTE_SECONDS = 28800
FAILURE_WINDOW = 900
EMAIL_FAILURE_LIMIT = 5
IP_FAILURE_LIMIT = 20
MFA_FAILURE_LIMIT = 10
CHALLENGE_SECONDS = 300
ENROLLMENT_SECONDS = 600


class SecurityError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def iso_time(timestamp=None):
    return datetime.fromtimestamp(time.time() if timestamp is None else timestamp, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def totp(secret, timestamp=None, digits=6):
    """Return the RFC 6238 SHA-1 code at a Unix timestamp (not a counter)."""
    secret = secret.upper().replace(" ", "")
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    counter = int(time.time() if timestamp is None else timestamp) // 30
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 15
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7fffffff
    return str(value % 10 ** digits).zfill(digits)


def matching_counter(secret, code, timestamp=None, after=-1):
    if not isinstance(code, str) or not re.fullmatch(r"[0-9]{6}", code.strip()):
        return None
    current = int(time.time() if timestamp is None else timestamp) // 30
    for counter in (current, current - 1, current + 1):
        if counter > after and counter >= 0 and hmac.compare_digest(totp(secret, counter * 30), code.strip()):
            return counter
    return None


def safe_text(value, maximum):
    return "".join(character for character in str(value or "") if ord(character) >= 32)[:maximum]


def masked_email(email):
    if not email or "@" not in email:
        return ""
    local, domain = email.rsplit("@", 1)
    return safe_text((local[:1] or "*") + "***@" + domain, 254)


def device_label(user_agent):
    value = str(user_agent or "")
    browser = next((label for token, label in (("Edg/", "Edge"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"), ("Safari/", "Safari")) if token in value), "Browser")
    platform = next((label for token, label in (("Android", "Android"), ("iPhone", "iPhone"), ("iPad", "iPad"), ("Windows", "Windows"), ("Macintosh", "macOS"), ("Linux", "Linux")) if token in value), "Unknown device")
    return browser + " on " + platform


class ServerSecurity:
    def initialize_security(self):
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS security_config (name TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS security_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL,
                    severity TEXT NOT NULL, actor_name TEXT NOT NULL, email_hint TEXT NOT NULL,
                    ip TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL, occurred_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS security_events_time ON security_events(occurred_at);
                CREATE TABLE IF NOT EXISTS security_failures (
                    bucket TEXT NOT NULL, occurred_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS security_failures_bucket ON security_failures(bucket, occurred_at);
                CREATE TABLE IF NOT EXISTS mfa_recovery_codes (
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    code_hash TEXT NOT NULL, PRIMARY KEY(user_id, code_hash)
                );
                CREATE TABLE IF NOT EXISTS mfa_challenges (
                    token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    auth_version INTEGER NOT NULL, password_hash TEXT NOT NULL,
                    remember INTEGER NOT NULL, expires_at INTEGER NOT NULL, ip TEXT NOT NULL,
                    ua_hash TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0
                );
            """)
            additions = {
                "users": {
                    "auth_version": "INTEGER NOT NULL DEFAULT 0", "mfa_enabled": "INTEGER NOT NULL DEFAULT 0",
                    "mfa_nonce": "TEXT", "mfa_pending_nonce": "TEXT", "mfa_pending_expires_at": "INTEGER NOT NULL DEFAULT 0",
                    "mfa_last_counter": "INTEGER NOT NULL DEFAULT -1",
                },
                "sessions": {
                    "session_id": "TEXT NOT NULL DEFAULT ''", "created_at": "INTEGER NOT NULL DEFAULT 0",
                    "last_seen": "INTEGER NOT NULL DEFAULT 0", "ip": "TEXT NOT NULL DEFAULT ''",
                    "device": "TEXT NOT NULL DEFAULT ''", "auth_version": "INTEGER NOT NULL DEFAULT 0",
                },
                "security_events": {
                    "actor_id": "INTEGER REFERENCES users(id) ON DELETE SET NULL",
                },
            }
            original_session_columns = {row["name"] for row in connection.execute("PRAGMA table_info(sessions)")}
            for table, fields in additions.items():
                columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
                for name, declaration in fields.items():
                    if name not in columns:
                        connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")
            stamp = int(time.time())
            for session in connection.execute("SELECT s.*, u.role, u.auth_version AS user_version FROM sessions s JOIN users u ON u.id=s.user_id").fetchall():
                created = session["created_at"] or stamp
                expires = min(session["expires_at"], created + ADMIN_ABSOLUTE_SECONDS) if session["role"] == "admin" else session["expires_at"]
                connection.execute("UPDATE sessions SET session_id=?,created_at=?,last_seen=?,expires_at=?,auth_version=? WHERE token_hash=?", (
                    session["session_id"] or secrets.token_urlsafe(18), created, session["last_seen"] or stamp, expires,
                    session["auth_version"] if "auth_version" in original_session_columns else session["user_version"], session["token_hash"],
                ))
            connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS sessions_public_id ON sessions(session_id)")
            fingerprint = connection.execute("SELECT value FROM security_config WHERE name='key_fingerprint'").fetchone()
            enrolled = connection.execute("SELECT 1 FROM users WHERE mfa_enabled=1 LIMIT 1").fetchone() is not None
        path = self.database.with_name("security.key")
        if not path.exists():
            if fingerprint is not None or enrolled:
                raise ValueError("The account security key is missing. Restore security.key with its matching database backup.")
            try:
                descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(secrets.token_bytes(32))
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileExistsError:
                pass
        key = path.read_bytes()
        if len(key) != 32:
            raise ValueError("The account security key is invalid. Restore security.key from its matching backup.")
        actual = hashlib.sha256(key).hexdigest()
        if fingerprint is not None and not hmac.compare_digest(fingerprint["value"], actual):
            raise ValueError("The account security key does not match this database.")
        self.security_key = key
        with self.connect() as connection:
            connection.execute("INSERT OR IGNORE INTO security_config VALUES ('key_fingerprint',?)", (actual,))
            self.prune_security(connection)

    def keyed_digest(self, domain, value):
        return hmac.new(self.security_key, (domain + "\0" + str(value)).encode("utf-8"), hashlib.sha256).hexdigest()

    def mfa_secret(self, user_id, nonce):
        material = hmac.new(self.security_key, f"velora-totp-v1\0{user_id}\0{nonce}".encode(), hashlib.sha256).digest()[:20]
        return base64.b32encode(material).decode().rstrip("=")

    def prune_security(self, connection):
        stamp = int(time.time())
        connection.execute("DELETE FROM security_events WHERE occurred_at < ?", (stamp - 30 * 86400,))
        connection.execute("DELETE FROM security_events WHERE id NOT IN (SELECT id FROM security_events ORDER BY id DESC LIMIT 2000)")
        connection.execute("DELETE FROM security_failures WHERE occurred_at <= ?", (stamp - FAILURE_WINDOW,))
        connection.execute("DELETE FROM mfa_challenges WHERE expires_at <= ?", (stamp,))

    def security_event(self, event_type, *, user=None, email="", ip="", detail="", severity="info", connection=None):
        if connection is None:
            with self.connect() as database:
                self.security_event(event_type, user=user, email=email, ip=ip, detail=detail, severity=severity, connection=database)
            return
        actor_id = user["id"] if user is not None else None
        # Resolve actor existence within the atomic INSERT. A request that finished
        # after account deletion must neither fail its FK nor restore personal data.
        connection.execute("""WITH actor AS (
                SELECT ? AS requested_id, EXISTS(SELECT 1 FROM users WHERE id=?) AS present
            )
            INSERT INTO security_events (event_type,severity,actor_name,email_hint,ip,detail,created_at,occurred_at,actor_id)
            SELECT ?,?,
                CASE WHEN requested_id IS NULL OR present THEN ? ELSE '' END,
                CASE WHEN requested_id IS NULL OR present THEN ? ELSE '' END,
                CASE WHEN requested_id IS NULL OR present THEN ? ELSE '' END,
                ?,?,?,CASE WHEN present THEN requested_id ELSE NULL END FROM actor""", (
            actor_id, actor_id,
            safe_text(event_type, 64), severity if severity in {"info", "warning", "critical"} else "info",
            safe_text(user["name"] if user is not None else "", 80), masked_email(email), safe_text(ip, 64), safe_text(detail, 300), iso_time(), int(time.time()),
        ))
        self.prune_security(connection)

    def failure_count(self, connection, domain, value):
        return connection.execute("SELECT COUNT(*) FROM security_failures WHERE bucket=? AND occurred_at>?", (
            self.keyed_digest(domain, value), int(time.time()) - FAILURE_WINDOW,
        )).fetchone()[0]

    def check_login_failures(self, email, ip):
        with self.connect() as connection:
            blocked = self.login_failure_limit_reached(connection, email, ip)
        if blocked:
            self.security_event("login_blocked", email=email, ip=ip, detail="Sign-in temporarily blocked after repeated failed attempts.", severity="warning")
            raise SecurityError(429, "Too many failed sign-in attempts. Please try again in 15 minutes.")

    def login_failure_limit_reached(self, connection, email, ip):
        return self.failure_count(connection, "login-email", email) >= EMAIL_FAILURE_LIMIT or self.failure_count(connection, "login-ip", ip) >= IP_FAILURE_LIMIT

    def login_outcome(self, email, ip, accepted):
        # Recheck under the same write lock as failure insertion. Parallel guesses
        # cannot all spend a stale budget measured before password hashing.
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if self.login_failure_limit_reached(connection, email, ip):
                self.security_event("login_blocked", email=email, ip=ip, detail="Sign-in temporarily blocked after repeated failed attempts.", severity="warning", connection=connection)
                connection.commit()
                raise SecurityError(429, "Too many failed sign-in attempts. Please try again in 15 minutes.")
            if not accepted:
                self.add_login_failure(email, ip, connection=connection)

    def add_login_failure(self, email, ip, *, user=None, mfa=False, connection=None):
        if connection is None:
            with self.connect() as database:
                self.add_login_failure(email, ip, user=user, mfa=mfa, connection=database)
            return
        buckets = [("login-email", email), ("login-ip", ip)]
        if mfa and user is not None:
            buckets.append(("mfa-user", user["id"]))
        connection.executemany("INSERT INTO security_failures VALUES (?,?)", [(self.keyed_digest(domain, value), int(time.time())) for domain, value in buckets])
        self.security_event("mfa_failed" if mfa else "login_failed", user=user, email=email, ip=ip,
                            detail="Two-factor verification failed." if mfa else "An email and password did not match.", severity="warning", connection=connection)

    def clear_login_failures(self, connection, email):
        connection.execute("DELETE FROM security_failures WHERE bucket=?", (self.keyed_digest("login-email", email),))

    def new_recovery_codes(self, connection, user_id):
        connection.execute("DELETE FROM mfa_recovery_codes WHERE user_id=?", (user_id,))
        codes = ["-".join(re.findall(".{4}", secrets.token_hex(8).upper())) for _ in range(10)]
        connection.executemany("INSERT INTO mfa_recovery_codes VALUES (?,?)", [
            (user_id, self.keyed_digest("recovery-v1", f"{user_id}\0{code.replace('-', '')}")) for code in codes
        ])
        return codes


class HandlerSecurity:
    def audit(self, event_type, *, user=None, email="", detail="", severity="info", connection=None):
        self.server.security_event(event_type, user=user, email=email, ip=self.client_address[0], detail=detail, severity=severity, connection=connection)

    def security_session(self, touch=True):
        from http.cookies import SimpleCookie, CookieError
        try:
            cookie = SimpleCookie()
            cookie.load(self.headers.get("Cookie", ""))
            token = cookie["velora_session"].value if "velora_session" in cookie else ""
        except CookieError:
            return None
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            return None
        digest, stamp = hashlib.sha256(token.encode()).hexdigest(), int(time.time())
        with self.server.connect() as connection:
            user = connection.execute("""SELECT u.*,s.token_hash,s.csrf_token,s.expires_at,s.session_id,
                s.created_at AS session_created_at,s.last_seen,s.ip AS session_ip,s.device AS session_device,
                s.auth_version AS session_auth_version FROM users u JOIN sessions s ON u.id=s.user_id WHERE s.token_hash=?""", (digest,)).fetchone()
            if user is None:
                return None
            expired = not user["account_enabled"] or user["expires_at"] <= stamp or user["auth_version"] != user["session_auth_version"]
            expired = expired or (user["role"] == "admin" and (user["last_seen"] <= stamp - ADMIN_IDLE_SECONDS or user["session_created_at"] <= stamp - ADMIN_ABSOLUTE_SECONDS))
            if expired:
                connection.execute("DELETE FROM sessions WHERE token_hash=?", (digest,))
                return None
            if touch and stamp - user["last_seen"] >= 60:
                connection.execute("UPDATE sessions SET last_seen=? WHERE token_hash=?", (stamp, digest))
            return user

    def session_cookie(self, token, remember=False, lifetime=None):
        cookie = f"velora_session={token}; Path=/; HttpOnly; SameSite=Lax"
        if remember:
            cookie += f"; Max-Age={lifetime or 30 * 86400}"
        if self.server.secure_cookies:
            cookie += "; Secure"
        return cookie

    def create_secure_session(self, user, remember=False, mfa_verified=False):
        previous = self.security_session(touch=False)
        token, csrf, stamp = secrets.token_urlsafe(32), secrets.token_urlsafe(32), int(time.time())
        lifetime = ADMIN_ABSOLUTE_SECONDS if user["role"] == "admin" else 30 * 86400 if remember else 12 * 3600
        with self.server.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
            if current is None or not current["account_enabled"] or current["auth_version"] != user["auth_version"] or not hmac.compare_digest(current["password_hash"], user["password_hash"]) or (current["mfa_enabled"] and not mfa_verified):
                raise SecurityError(401, "Your sign-in details changed. Please sign in again.")
            if previous:
                connection.execute("DELETE FROM sessions WHERE token_hash=?", (previous["token_hash"],))
            connection.execute("DELETE FROM sessions WHERE expires_at<=?", (stamp,))
            connection.execute("""INSERT INTO sessions (token_hash,user_id,csrf_token,expires_at,session_id,created_at,last_seen,ip,device,auth_version)
                VALUES (?,?,?,?,?,?,?,?,?,?)""", (hashlib.sha256(token.encode()).hexdigest(), user["id"], csrf, stamp + lifetime,
                    secrets.token_urlsafe(18), stamp, stamp, self.client_address[0], device_label(self.headers.get("User-Agent", "")), current["auth_version"]))
            self.server.clear_login_failures(connection, current["email"])
            self.audit("login_success", user=current, email=current["email"], detail="Signed in with two factors." if mfa_verified else "Signed in successfully.", connection=connection)
        return self.session_cookie(token, remember, lifetime), csrf

    def fresh_security_user(self, connection, user, admin=False):
        stamp = int(time.time())
        current = connection.execute("""SELECT u.*,s.token_hash,s.csrf_token,s.session_id,s.created_at AS session_created_at,
            s.last_seen,s.expires_at,s.ip AS session_ip,s.device AS session_device FROM users u JOIN sessions s ON s.user_id=u.id
            WHERE u.id=? AND s.token_hash=? AND s.auth_version=u.auth_version AND s.expires_at>?""", (user["id"], user["token_hash"], int(time.time()))).fetchone()
        if current is None or not current["account_enabled"] or current["auth_version"] != user["auth_version"] or not hmac.compare_digest(current["password_hash"], user["password_hash"]):
            raise SecurityError(401, "Your account changed. Please sign in again.")
        if current["role"] == "admin" and (current["last_seen"] <= stamp - ADMIN_IDLE_SECONDS or current["session_created_at"] <= stamp - ADMIN_ABSOLUTE_SECONDS):
            raise SecurityError(401, "Your session expired. Please sign in again.")
        if admin and current["role"] != "admin":
            raise SecurityError(403, "Administrator access is required.")
        return current

    def rotate_security_session(self, connection, user, new_version):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        connection.execute("DELETE FROM sessions WHERE user_id=?", (user["id"],))
        connection.execute("DELETE FROM mfa_challenges WHERE user_id=?", (user["id"],))
        connection.execute("""INSERT INTO sessions (token_hash,user_id,csrf_token,expires_at,session_id,created_at,last_seen,ip,device,auth_version)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", (hashlib.sha256(token.encode()).hexdigest(), user["id"], csrf, user["expires_at"], secrets.token_urlsafe(18),
                user["session_created_at"], int(time.time()), user["session_ip"], user["session_device"], new_version))
        # Preserve the existing absolute expiry; cookie persistence may only last as
        # long as that server-side expiry, even when the old cookie was remembered.
        remaining = max(1, user["expires_at"] - int(time.time()))
        return self.session_cookie(token, False, remaining), csrf

    def begin_mfa_login(self, user, remember=False):
        token, stamp = secrets.token_urlsafe(32), int(time.time())
        with self.server.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
            if current is None or current["auth_version"] != user["auth_version"] or not current["mfa_enabled"] or not hmac.compare_digest(current["password_hash"], user["password_hash"]):
                raise SecurityError(401, "Your sign-in details changed. Please sign in again.")
            connection.execute("DELETE FROM mfa_challenges WHERE expires_at<=?", (stamp,))
            connection.execute("INSERT INTO mfa_challenges VALUES (?,?,?,?,?,?,?,?,0)", (hashlib.sha256(token.encode()).hexdigest(), user["id"], user["auth_version"], user["password_hash"], int(remember), stamp + CHALLENGE_SECONDS, self.client_address[0], hashlib.sha256(self.headers.get("User-Agent", "").encode()).hexdigest()))
        self.send_json(200, {"requiresTwoFactor": True, "challenge": token, "expiresIn": CHALLENGE_SECONDS})

    def check_mfa_failures(self, user):
        with self.server.connect() as connection:
            blocked = self.server.failure_count(connection, "mfa-user", user["id"]) >= MFA_FAILURE_LIMIT or self.server.failure_count(connection, "login-ip", self.client_address[0]) >= IP_FAILURE_LIMIT
        if blocked:
            self.audit("mfa_blocked", user=user, email=user["email"], detail="Two-factor verification temporarily blocked after repeated failures.", severity="warning")
            raise SecurityError(429, "Too many verification attempts. Please try again in 15 minutes.")

    def guard_mfa_budget(self, connection, user):
        blocked = self.server.failure_count(connection, "mfa-user", user["id"]) >= MFA_FAILURE_LIMIT or self.server.failure_count(connection, "login-ip", self.client_address[0]) >= IP_FAILURE_LIMIT
        if blocked:
            self.audit("mfa_blocked", user=user, email=user["email"], detail="Two-factor verification temporarily blocked after repeated failures.", severity="warning", connection=connection)
            # Called before any credential mutation; retain the audit when the
            # control-flow exception leaves the transaction context.
            connection.commit()
            raise SecurityError(429, "Too many verification attempts. Please try again in 15 minutes.")

    def verify_mfa_factor(self, connection, user, code):
        if not isinstance(code, str) or len(code) > 64:
            return False
        normalized = re.sub(r"[\s-]", "", code).upper()
        if re.fullmatch(r"[0-9]{6}", normalized):
            counter = matching_counter(self.server.mfa_secret(user["id"], user["mfa_nonce"]), normalized, after=user["mfa_last_counter"])
            if counter is not None:
                connection.execute("UPDATE users SET mfa_last_counter=? WHERE id=?", (counter, user["id"]))
                return True
        if re.fullmatch(r"[0-9A-F]{16}", normalized):
            digest = self.server.keyed_digest("recovery-v1", f"{user['id']}\0{normalized}")
            changed = connection.execute("DELETE FROM mfa_recovery_codes WHERE user_id=? AND code_hash=?", (user["id"], digest)).rowcount
            if changed:
                self.audit("mfa_recovery_used", user=user, email=user["email"], detail="A one-use recovery code was used.", severity="warning", connection=connection)
                return True
        return False

    def finish_mfa_login(self, payload):
        if set(payload) != {"challenge", "code"} or not isinstance(payload["challenge"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", payload["challenge"]):
            raise SecurityError(400, "Enter the verification code for your sign-in.")
        digest, stamp = hashlib.sha256(payload["challenge"].encode()).hexdigest(), int(time.time())
        with self.server.connect() as connection:
            preview = connection.execute("SELECT u.* FROM users u JOIN mfa_challenges c ON c.user_id=u.id WHERE c.token_hash=?", (digest,)).fetchone()
        if preview is None:
            raise SecurityError(401, "This verification has expired. Please sign in again.")
        self.check_mfa_failures(preview)
        error = None
        with self.server.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            challenge = connection.execute("SELECT * FROM mfa_challenges WHERE token_hash=?", (digest,)).fetchone()
            user = connection.execute("SELECT * FROM users WHERE id=?", (preview["id"],)).fetchone()
            if user is not None:
                self.guard_mfa_budget(connection, user)
            valid = challenge is not None and challenge["expires_at"] > stamp and challenge["attempts"] < 5
            valid = valid and user is not None and user["mfa_enabled"] and user["auth_version"] == challenge["auth_version"] and hmac.compare_digest(user["password_hash"], challenge["password_hash"])
            valid = valid and challenge["ip"] == self.client_address[0] and hmac.compare_digest(challenge["ua_hash"], hashlib.sha256(self.headers.get("User-Agent", "").encode()).hexdigest())
            if not valid:
                if challenge is not None:
                    connection.execute("DELETE FROM mfa_challenges WHERE token_hash=?", (digest,))
                error = SecurityError(401, "This verification has expired. Please sign in again.")
            elif not self.verify_mfa_factor(connection, user, payload["code"]):
                connection.execute("UPDATE mfa_challenges SET attempts=attempts+1 WHERE token_hash=?", (digest,))
                self.server.add_login_failure(user["email"], self.client_address[0], user=user, mfa=True, connection=connection)
                error = SecurityError(401, "The verification code is invalid, expired, or already used. Try a fresh code.")
            else:
                connection.execute("DELETE FROM mfa_challenges WHERE token_hash=?", (digest,))
                remember = bool(challenge["remember"])
        if error:
            raise error
        cookie, csrf = self.issue_session(user, remember, mfa_verified=True)
        self.send_json(200, {"user": self.user_payload(user), "csrfToken": csrf}, cookie=cookie)

    def security_status(self, user):
        with self.server.connect() as connection:
            count = connection.execute("SELECT COUNT(*) FROM mfa_recovery_codes WHERE user_id=?", (user["id"],)).fetchone()[0]
        self.send_json(200, {"mfaEnabled": bool(user["mfa_enabled"]), "recoveryCodesRemaining": count,
                             "adminIdleTimeoutSeconds": ADMIN_IDLE_SECONDS, "adminAbsoluteTimeoutSeconds": ADMIN_ABSOLUTE_SECONDS})

    def security_sessions(self, user):
        stamp = int(time.time())
        with self.server.connect() as connection:
            rows = connection.execute("SELECT * FROM sessions WHERE user_id=? AND auth_version=? AND expires_at>? ORDER BY last_seen DESC", (user["id"], user["auth_version"], stamp)).fetchall()
        sessions = [{"id": row["session_id"], "created_at": iso_time(row["created_at"]), "last_seen": iso_time(row["last_seen"]),
                     "expires_at": iso_time(row["expires_at"]), "ip": row["ip"], "device": row["device"], "current": row["token_hash"] == user["token_hash"]}
                    for row in rows if user["role"] != "admin" or row["last_seen"] > stamp - ADMIN_IDLE_SECONDS]
        self.send_json(200, {"sessions": sessions})

    def revoke_security_sessions(self, user, payload, session_id=None):
        if payload:
            raise SecurityError(400, "This action does not accept additional fields.")
        with self.server.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self.fresh_security_user(connection, user)
            if session_id is None:
                revoked = connection.execute("DELETE FROM sessions WHERE user_id=? AND token_hash!=?", (user["id"], user["token_hash"])).rowcount
                self.audit("session_revoked", user=user, detail="Other sign-in sessions were revoked.", connection=connection)
            else:
                target = connection.execute("SELECT token_hash FROM sessions WHERE session_id=? AND user_id=?", (session_id, user["id"])).fetchone()
                if target is None:
                    raise SecurityError(404, "This session was not found.")
                current = target["token_hash"] == user["token_hash"]
                connection.execute("DELETE FROM sessions WHERE session_id=? AND user_id=?", (session_id, user["id"]))
                self.audit("session_revoked", user=user, detail="A sign-in session was revoked.", connection=connection)
        self.send_json(200, {"revoked": revoked} if session_id is None else {"ok": True, "current": current})

    def mfa_setup(self, user, payload):
        if set(payload) != {"password"}:
            raise SecurityError(400, "Enter your current password to set up two-factor sign-in.")
        self.server.rate_limit(("security-reauth", user["id"]), 10, 900)
        if not self.password_checker(payload["password"], user["password_hash"]):
            raise SecurityError(400, "Your current password is incorrect.")
        nonce, expires = secrets.token_urlsafe(24), int(time.time()) + ENROLLMENT_SECONDS
        with self.server.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self.fresh_security_user(connection, user)
            self.guard_mfa_budget(connection, current)
            if current["mfa_enabled"]:
                raise SecurityError(409, "Two-factor sign-in is already enabled.")
            connection.execute("UPDATE users SET mfa_pending_nonce=?,mfa_pending_expires_at=? WHERE id=?", (nonce, expires, user["id"]))
            self.audit("mfa_setup", user=current, detail="Authenticator setup started.", connection=connection)
        secret = self.server.mfa_secret(user["id"], nonce)
        uri = "otpauth://totp/" + quote("Velora:" + user["email"], safe="") + "?" + urlencode({"secret": secret, "issuer": "Velora", "algorithm": "SHA1", "digits": 6, "period": 30})
        self.send_json(200, {"secret": secret, "otpauthUri": uri, "expiresAt": iso_time(expires)})

    def mfa_enable(self, user, payload):
        if set(payload) != {"code"}:
            raise SecurityError(400, "Enter a fresh authenticator code to finish setup.")
        self.check_mfa_failures(user)
        error = None
        with self.server.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self.fresh_security_user(connection, user)
            self.guard_mfa_budget(connection, current)
            if current["mfa_enabled"]:
                raise SecurityError(409, "Two-factor sign-in is already enabled.")
            if not current["mfa_pending_nonce"] or current["mfa_pending_expires_at"] <= int(time.time()):
                raise SecurityError(400, "Authenticator setup has expired. Start setup again.")
            counter = matching_counter(self.server.mfa_secret(user["id"], current["mfa_pending_nonce"]), payload["code"])
            if counter is None:
                self.server.add_login_failure(current["email"], self.client_address[0], user=current, mfa=True, connection=connection)
                error = SecurityError(400, "The authenticator code is invalid or expired. Try a fresh code.")
            else:
                version = current["auth_version"] + 1
                connection.execute("""UPDATE users SET mfa_enabled=1,mfa_nonce=mfa_pending_nonce,mfa_pending_nonce=NULL,
                    mfa_pending_expires_at=0,mfa_last_counter=?,auth_version=? WHERE id=?""", (counter, version, user["id"]))
                codes = self.server.new_recovery_codes(connection, user["id"])
                cookie, csrf = self.rotate_security_session(connection, current, version)
                self.audit("mfa_enabled", user=current, detail="Authenticator two-factor sign-in enabled; other sessions signed out.", connection=connection)
        if error:
            raise error
        self.send_json(200, {"mfaEnabled": True, "recoveryCodes": codes, "csrfToken": csrf}, cookie=cookie)

    def mfa_manage(self, user, payload, disable=False):
        if set(payload) != {"password", "code"}:
            raise SecurityError(400, "Enter your current password and a fresh authenticator or recovery code.")
        self.server.rate_limit(("security-reauth", user["id"]), 10, 900)
        if not self.password_checker(payload["password"], user["password_hash"]):
            raise SecurityError(400, "Your current password is incorrect.")
        self.check_mfa_failures(user)
        error = None
        with self.server.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self.fresh_security_user(connection, user)
            self.guard_mfa_budget(connection, current)
            if not current["mfa_enabled"]:
                raise SecurityError(409, "Two-factor sign-in is not enabled.")
            if not self.verify_mfa_factor(connection, current, payload["code"]):
                self.server.add_login_failure(current["email"], self.client_address[0], user=current, mfa=True, connection=connection)
                error = SecurityError(400, "The verification code is invalid, expired, or already used. Try a fresh code.")
            else:
                version = current["auth_version"] + 1
                connection.execute("UPDATE users SET auth_version=? WHERE id=?", (version, user["id"]))
                if disable:
                    connection.execute("UPDATE users SET mfa_enabled=0,mfa_nonce=NULL,mfa_pending_nonce=NULL,mfa_pending_expires_at=0,mfa_last_counter=-1 WHERE id=?", (user["id"],))
                    connection.execute("DELETE FROM mfa_recovery_codes WHERE user_id=?", (user["id"],))
                else:
                    codes = self.server.new_recovery_codes(connection, user["id"])
                cookie, csrf = self.rotate_security_session(connection, current, version)
                self.audit("mfa_disabled" if disable else "mfa_recovery_regenerated", user=current,
                    detail="Two-factor sign-in disabled; other sessions signed out." if disable else "Recovery codes replaced; other sessions signed out.", severity="warning", connection=connection)
        if error:
            raise error
        self.send_json(200, {"mfaEnabled": False, "csrfToken": csrf} if disable else {"recoveryCodes": codes, "csrfToken": csrf}, cookie=cookie)

    def admin_security(self, user):
        stamp = int(time.time())
        with self.server.connect() as connection:
            counts = connection.execute("""SELECT
                COALESCE(SUM(event_type IN ('login_failed','mfa_failed')),0) AS failures,
                COALESCE(SUM(event_type IN ('login_blocked','mfa_blocked','csrf_rejected','permission_denied')),0) AS blocked
                FROM security_events WHERE occurred_at>?""", (stamp - 86400,)).fetchone()
            admins = connection.execute("SELECT COUNT(*) AS total,COALESCE(SUM(mfa_enabled),0) AS enabled FROM users WHERE role='admin'").fetchone()
            active = connection.execute("""SELECT COUNT(*) FROM sessions s JOIN users u ON s.user_id=u.id
                WHERE u.role='admin' AND s.auth_version=u.auth_version AND s.expires_at>? AND s.last_seen>? AND s.created_at>?""", (stamp, stamp - ADMIN_IDLE_SECONDS, stamp - ADMIN_ABSOLUTE_SECONDS)).fetchone()[0]
            events = connection.execute("SELECT id,event_type,severity,actor_name,email_hint,ip,detail,created_at FROM security_events ORDER BY id DESC LIMIT 100").fetchall()
        self.send_json(200, {"summary": {"failedLogins24h": counts["failures"], "blockedAttempts24h": counts["blocked"], "activeAdminSessions": active,
            "mfaEnabledAdmins": admins["enabled"], "totalAdmins": admins["total"]}, "events": [dict(event) for event in events]})

    def handle_security_api(self, path, method):
        reading = method in {"GET", "HEAD"}
        if reading and path == "/api/admin/security":
            self.admin_security(self.require_user(admin=True))
            return True
        if reading and path in {"/api/security/status", "/api/security/sessions"}:
            user = self.require_user()
            (self.security_status if path.endswith("/status") else self.security_sessions)(user)
            return True
        if method == "POST" and path == "/api/auth/verify":
            self.finish_mfa_login(self.read_json())
            return True
        operations = {
            "/api/security/mfa/setup": self.mfa_setup, "/api/security/mfa/enable": self.mfa_enable,
            "/api/security/mfa/disable": lambda user, payload: self.mfa_manage(user, payload, True),
            "/api/security/mfa/recovery-codes": self.mfa_manage,
            "/api/security/sessions/revoke-others": self.revoke_security_sessions,
        }
        if method == "POST" and path in operations:
            user = self.require_user(csrf=True)
            operations[path](user, self.read_json())
            return True
        match = re.fullmatch(r"/api/security/sessions/([A-Za-z0-9_-]{20,64})", path)
        if method == "DELETE" and match:
            user = self.require_user(csrf=True)
            self.revoke_security_sessions(user, self.read_json(), match[1])
            return True
        known = {"/api/admin/security", "/api/security/status", "/api/security/sessions", "/api/auth/verify", *operations}
        if path in known:
            raise SecurityError(405, "This method is not supported.")
        return False
