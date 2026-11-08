"""Owner-provisioned Velora colleague identities, separate from public customers."""
import json
import re
import sqlite3

import commerce
import shared_folders

EMAIL_DOMAIN = "velora.com"
ROLES = {"colleague", "manager", "warehouse", "owner"}


class ColleagueError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def work_email(email):
    return isinstance(email, str) and email.count("@") == 1 and email.rsplit("@", 1)[1].lower() == EMAIL_DOMAIN


def initialize(server):
    with server.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        migrated = connection.execute("SELECT 1 FROM security_config WHERE name='velora_colleagues_v1'").fetchone()
        if not migrated:
            # An existing owner-assigned workspace profile is evidence of provisioning;
            # a public registration using a company-looking address is not.
            connection.execute("""UPDATE users SET account_type='velora'
                WHERE lower(substr(email,instr(email,'@')+1))=? AND
                (role='admin' OR EXISTS(SELECT 1 FROM staff_profiles WHERE user_id=users.id AND department IS NOT NULL))""", (EMAIL_DOMAIN,))
            connection.execute("INSERT INTO security_config(name,value) VALUES('velora_colleagues_v1','1')")


def is_velora(user):
    return user["account_type"] == "velora" and work_email(user["email"])


def owner_count(connection):
    return sum(commerce.role(connection, row) == "owner" for row in connection.execute("SELECT * FROM users WHERE role='admin' AND account_enabled=1"))


def serialize(connection, user):
    profile = shared_folders.profile(connection, user)
    return {"id": user["id"], "name": user["name"], "email": user["email"], "accountType": "velora",
            "role": commerce.role(connection, user) if user["role"] == "admin" else "colleague",
            "active": bool(user["account_enabled"] and profile["active"]), "department": profile["department"],
            "fullControl": shared_folders.full_control(connection, user),
            "grants": [dict(row) for row in connection.execute("SELECT folder,access FROM folder_grants WHERE user_id=? ORDER BY folder", (user["id"],))]}


def list_payload(connection):
    rows = connection.execute("SELECT * FROM users WHERE account_type='velora' ORDER BY name COLLATE NOCASE,id").fetchall()
    return {"departments": [dict(item) for item in shared_folders.DEPARTMENTS],
            "colleagues": [serialize(connection, row) for row in rows if work_email(row["email"])], "emailDomain": EMAIL_DOMAIN}


def access_values(payload):
    expected = {"active", "department", "role", "fullControl", "grants"}
    if set(payload) != expected or type(payload.get("active")) is not bool or type(payload.get("fullControl")) is not bool:
        raise ColleagueError(400, "Choose account status, a department, a role and folder permissions.")
    active, department, role, full, grants = (payload[key] for key in ("active", "department", "role", "fullControl", "grants"))
    if not isinstance(role, str) or role not in ROLES or full != (role == "owner"):
        raise ColleagueError(400, "Full control includes the owner role and access to every folder.")
    if department is not None and (not isinstance(department, str) or department not in shared_folders.FOLDERS or department == "company"):
        raise ColleagueError(400, "Choose a valid primary department.")
    if active and department is None:
        raise ColleagueError(400, "An enabled colleague needs a primary department.")
    if not isinstance(grants, list) or len(grants) > len(shared_folders.FOLDERS):
        raise ColleagueError(400, "Choose valid folder permissions.")
    clean, seen = [], set()
    for grant in grants:
        if not isinstance(grant, dict) or set(grant) != {"folder", "access"}:
            raise ColleagueError(400, "Choose valid folder permissions.")
        folder, access = grant["folder"], grant["access"]
        if not isinstance(folder, str) or folder not in shared_folders.FOLDERS or folder in seen or access not in ("read", "write"):
            raise ColleagueError(400, "Choose valid, unique folder permissions.")
        if not full and shared_folders.FOLDERS[folder]["sensitive"] and department != folder:
            raise ColleagueError(400, "Finance and HR grants require a matching department or Full control.")
        seen.add(folder)
        clean.append((folder, access))
    return active, department, role, full, clean


def save_access(connection, user_id, values):
    active, department, role, full, grants = values
    now = shared_folders.stamp()
    connection.execute("UPDATE users SET role=?,account_enabled=? WHERE id=?", ("customer" if role == "colleague" else "admin", int(active), user_id))
    connection.execute("""INSERT INTO staff_profiles(user_id,active,department,updated_at,full_control) VALUES(?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET active=excluded.active,department=excluded.department,updated_at=excluded.updated_at,full_control=excluded.full_control""", (user_id, int(active), department, now, int(full)))
    connection.execute("DELETE FROM folder_grants WHERE user_id=?", (user_id,))
    if active and not full:
        connection.executemany("INSERT INTO folder_grants(user_id,folder,access) VALUES(?,?,?)", [(user_id, folder, access) for folder, access in grants])
    state = json.loads(connection.execute("SELECT data FROM commerce_state WHERE id=1").fetchone()[0])
    if role == "colleague":
        state["staff"].pop(str(user_id), None)
    else:
        state["staff"][str(user_id)] = role
    state["revision"] += 1
    connection.execute("UPDATE commerce_state SET data=? WHERE id=1", (json.dumps(state),))


def create(handler, actor, payload, validators):
    if set(payload) != {"firstName", "lastName", "email", "password", "active", "department", "role", "fullControl", "grants"}:
        raise ColleagueError(400, "Enter the colleague's name, work email, password and access settings.")
    validate_name, validate_email, validate_password, hash_password = validators
    first, last = validate_name(payload["firstName"]), validate_name(payload["lastName"])
    email = validate_email(payload["email"])
    if not work_email(email):
        raise ColleagueError(400, "Velora colleagues need an @velora.com work email address.")
    password = validate_password(payload["password"])
    values = access_values({key: payload[key] for key in ("active", "department", "role", "fullControl", "grants")})
    handler.server.rate_limit(("create-colleague", actor["id"]), 30, 3600)
    encoded = hash_password(password)
    try:
        with handler.server.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            shared_folders.require_owner(handler, connection, actor)
            cursor = connection.execute("""INSERT INTO users
                (name,first_name,last_name,email,password_hash,role,created_at,account_type,account_enabled)
                VALUES(?,?,?,?,?,'customer',?,'velora',?)""", (f"{first} {last}", first, last, email, encoded, shared_folders.stamp(), int(values[0])))
            user_id = cursor.lastrowid
            save_access(connection, user_id, values)
            result = serialize(connection, connection.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
            handler.audit("colleague_created", user=actor, detail=f"Created Velora colleague {user_id}; role {values[2]}; Full control {values[3]}.", connection=connection)
    except sqlite3.IntegrityError:
        raise ColleagueError(409, "An account already uses this work email. Choose an unused colleague address.")
    handler.send_json(201, {"colleague": result})


def update(handler, actor, user_id, payload):
    values = access_values(payload)
    active, department, role, full, _ = values
    with handler.server.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        shared_folders.require_owner(handler, connection, actor)
        target = connection.execute("SELECT * FROM users WHERE id=? AND account_type='velora'", (user_id,)).fetchone()
        if target is None or not work_email(target["email"]):
            raise ColleagueError(404, "This Velora colleague was not found.")
        previous_role = commerce.role(connection, target) if target["role"] == "admin" else "colleague"
        if user_id == actor["id"] and (not active or role != "owner"):
            raise ColleagueError(409, "Keep your own owner access enabled. Another owner can change your role.")
        if target["role"] == "admin" and previous_role == "owner" and (not active or role != "owner") and owner_count(connection) <= 1:
            raise ColleagueError(409, "Keep at least one enabled owner account.")
        save_access(connection, user_id, values)
        if previous_role != role or bool(target["account_enabled"]) != active:
            connection.execute("UPDATE users SET auth_version=auth_version+1 WHERE id=?", (user_id,))
            connection.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
            connection.execute("DELETE FROM mfa_challenges WHERE user_id=?", (user_id,))
        result = serialize(connection, connection.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
        handler.audit("colleague_access_changed", user=actor, detail=f"Updated colleague {user_id}; role {previous_role} to {role}; enabled {active}; department {department}; Full control {full}.", connection=connection)
    handler.send_json(200, {"colleague": result})


def handle(handler, method, path, validators):
    if path != "/api/admin/colleagues" and not path.startswith("/api/admin/colleagues/"):
        return False
    actor = handler.require_user(admin=True, csrf=method not in {"GET", "HEAD"})
    with handler.server.connect() as connection:
        shared_folders.require_owner(handler, connection, actor)
        if method in {"GET", "HEAD"} and path == "/api/admin/colleagues":
            handler.send_json(200, list_payload(connection))
            return True
    if method == "POST" and path == "/api/admin/colleagues":
        create(handler, actor, handler.read_json(), validators)
        return True
    match = re.fullmatch(r"/api/admin/colleagues/([1-9][0-9]{0,14})", path)
    if method == "PATCH" and match:
        update(handler, actor, int(match[1]), handler.read_json())
        return True
    raise ColleagueError(405 if path == "/api/admin/colleagues" or match else 404, "This colleague action is not supported.")
