"""Department membership and private shared files, separate from public media."""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import hashlib
import io
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
from urllib.parse import quote
import zipfile

import commerce
from security_core import SecurityError


class FolderError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


DEPARTMENTS = (
    {"id": "company", "name": "Company library", "description": "Website images, product information and shared company resources.", "sensitive": False},
    {"id": "leadership", "name": "Leadership", "description": "Planning, company direction and leadership resources.", "sensitive": False},
    {"id": "creative", "name": "Creative studio", "description": "Campaign imagery, creative briefs and visual direction.", "sensitive": False},
    {"id": "design", "name": "Design", "description": "Design references, collections and technical documents.", "sensitive": False},
    {"id": "production", "name": "Production", "description": "Production schedules, specifications and quality records.", "sensitive": False},
    {"id": "brand", "name": "Brand & marketing", "description": "Brand guidelines, communications and marketing plans.", "sensitive": False},
    {"id": "community", "name": "Community", "description": "Community projects, partnerships and support resources.", "sensitive": False},
    {"id": "commerce", "name": "Digital commerce", "description": "Storefront operations and digital commerce resources.", "sensitive": False},
    {"id": "finance", "name": "Finance", "description": "Restricted financial documents. Finance grants or explicit Full control required.", "sensitive": True},
    {"id": "people", "name": "Human Resources", "description": "Restricted people records. HR grants or explicit Full control required.", "sensitive": True},
)
FOLDERS = {item["id"]: item for item in DEPARTMENTS}
MAX_FILE = 8 * 1024 * 1024
RASTER = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif"}
OFFICE = {".docx": ("word/document.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
          ".xlsx": ("xl/workbook.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
          ".pptx": ("ppt/presentation.xml", "application/vnd.openxmlformats-officedocument.presentationml.presentation")}


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def initialize(server):
    server.shared_folder_root = server.database.parent / "shared-folders"
    if server.shared_folder_root.is_symlink():
        raise ValueError("Shared-file storage must be a real directory.")
    server.shared_folder_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    server.shared_folder_root = server.shared_folder_root.resolve()
    with server.connect() as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS staff_profiles (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                active INTEGER NOT NULL CHECK(active IN (0,1)),
                department TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS folder_grants (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                folder TEXT NOT NULL,
                access TEXT NOT NULL CHECK(access IN ('read','write')),
                PRIMARY KEY(user_id,folder)
            );
            CREATE TABLE IF NOT EXISTS shared_files (
                id TEXT PRIMARY KEY,
                folder TEXT NOT NULL,
                name TEXT NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN ('image','document','note')),
                mime TEXT NOT NULL,
                size INTEGER NOT NULL,
                storage_name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS shared_files_folder ON shared_files(folder,created_at);
        """)
        if "full_control" not in {row["name"] for row in connection.execute("PRAGMA table_info(staff_profiles)")}:
            connection.execute("ALTER TABLE staff_profiles ADD COLUMN full_control INTEGER NOT NULL DEFAULT 0 CHECK(full_control IN (0,1))")


def profile(connection, user):
    from colleagues import is_velora
    row = connection.execute("SELECT active,department,full_control FROM staff_profiles WHERE user_id=?", (user["id"],)).fetchone()
    return {"active": bool(row and row["active"] and user["account_enabled"] and is_velora(user)), "department": row["department"] if row else None,
            "fullControl": bool(row and row["full_control"])}


def full_control(connection, user):
    staff = profile(connection, user)
    return bool(staff["active"] and staff["fullControl"] and user["role"] == "admin" and commerce.role(connection, user) == "owner")


def can_open_intranet(server, user):
    if user is None:
        return False
    with server.connect() as connection:
        return user["role"] == "admin" or profile(connection, user)["active"]


def permission(connection, user, folder):
    """Only an explicitly provisioned Full control account bypasses department grants."""
    staff = profile(connection, user)
    if folder in FOLDERS and full_control(connection, user):
        return "write"
    if folder == "company" and (staff["active"] or user["role"] == "admin"):
        row = connection.execute("SELECT access FROM folder_grants WHERE user_id=? AND folder=?", (user["id"], folder)).fetchone()
        return "write" if staff["active"] and row and row["access"] == "write" else "read"
    if not staff["active"] or folder not in FOLDERS:
        return None
    if FOLDERS[folder]["sensitive"] and staff["department"] != folder:
        return None
    row = connection.execute("SELECT access FROM folder_grants WHERE user_id=? AND folder=?", (user["id"], folder)).fetchone()
    return row["access"] if row else None


def require_folder(connection, user, folder, write=False):
    if folder not in FOLDERS:
        raise FolderError(404, "This folder was not found.")
    access = permission(connection, user, folder)
    if not access or (write and access != "write"):
        raise FolderError(403, "You do not have permission to manage this folder." if write else "You do not have access to this folder.")
    return access


def require_staff(connection, user):
    staff = profile(connection, user)
    if not staff["active"] and user["role"] != "admin":
        raise FolderError(403, "Your colleague workspace access is not enabled. Contact your administrator.")
    return staff


def require_owner(handler, connection, user):
    handler.fresh_security_user(connection, user, admin=True)
    if commerce.role(connection, user) != "owner":
        raise FolderError(403, "Only the store owner can manage colleague folder access.")


def colleague(connection, row):
    return {"id": row["id"], "name": row["name"], "email": row["email"], **profile(connection, row),
            "grants": [dict(item) for item in connection.execute("SELECT folder,access FROM folder_grants WHERE user_id=? ORDER BY folder", (row["id"],))]}


def update_access(handler, user, user_id):
    payload = handler.read_json()
    if set(payload) != {"active", "department", "grants"} or type(payload.get("active")) is not bool:
        raise FolderError(400, "Send workspace access, a primary department and folder permissions.")
    department, active, grants = payload["department"], payload["active"], payload["grants"]
    if department is not None and (not isinstance(department, str) or department not in FOLDERS or department == "company"):
        raise FolderError(400, "Choose a valid primary department.")
    if active and department is None:
        raise FolderError(400, "An active colleague needs a primary department.")
    if not isinstance(grants, list) or len(grants) > len(FOLDERS):
        raise FolderError(400, "Choose valid folder permissions.")
    normalized, seen = [], set()
    for grant in grants:
        if not isinstance(grant, dict) or set(grant) != {"folder", "access"}:
            raise FolderError(400, "Choose valid folder permissions.")
        folder, access = grant["folder"], grant["access"]
        if not isinstance(folder, str) or folder not in FOLDERS or folder in seen or access not in ("read", "write"):
            raise FolderError(400, "Choose valid, unique folder permissions.")
        if FOLDERS[folder]["sensitive"] and department != folder:
            raise FolderError(400, "Finance and HR permissions require matching primary department membership.")
        seen.add(folder)
        normalized.append((folder, access))
    with handler.server.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        require_owner(handler, connection, user)
        target = connection.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if target is None:
            raise FolderError(404, "This colleague account was not found.")
        from colleagues import is_velora
        if not is_velora(target):
            raise FolderError(404, "Only Velora colleague accounts belong in folder access.")
        previous = colleague(connection, target)
        connection.execute("INSERT INTO staff_profiles(user_id,active,department,updated_at) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET active=excluded.active,department=excluded.department,updated_at=excluded.updated_at", (user_id, int(active), department, stamp()))
        connection.execute("DELETE FROM folder_grants WHERE user_id=?", (user_id,))
        if active:
            connection.executemany("INSERT INTO folder_grants(user_id,folder,access) VALUES(?,?,?)", [(user_id, folder, access) for folder, access in normalized])
        result = colleague(connection, target)
        handler.audit("folder_access_changed", user=user, detail=f"Colleague {user_id}: active {previous['active']} to {active}; department {previous['department']} to {department}; grants {json.dumps(result['grants'], separators=(',', ':'))}", connection=connection)
    handler.send_json(200, {"colleague": result})


def public_library(server, product_serializer):
    """References to already-public originals, never private storage or responsive copies."""
    entries = {}
    assets = server.root / "assets"
    if assets.is_dir() and assets.resolve().is_relative_to(server.root):
        for directory, directories, filenames in os.walk(assets, followlinks=False):
            directory = Path(directory)
            directories[:] = [name for name in directories if name not in {"responsive", "vendor"} and not name.startswith(".") and not (directory / name).is_symlink()
                               and not (directory / name).resolve().is_relative_to(server.shared_folder_root)]
            for filename in sorted(filenames):
                path = directory / filename
                if path.is_symlink() or path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".svg", ".ico"}:
                    continue
                path = path.resolve()
                if not path.is_relative_to(assets.resolve()) or path in server.private_files or path.is_relative_to(server.shared_folder_root):
                    continue
                relative = path.relative_to(server.root).as_posix()
                file_id = "website-" + hashlib.sha256(relative.encode()).hexdigest()[:32]
                stat = path.stat()
                entries[file_id] = {"id": file_id, "folder": "company", "name": relative.removeprefix("assets/"), "kind": "image",
                                    "size": stat.st_size, "mime": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                                    "created_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
                                    "path": path, "source": "website"}
    with server.connect() as connection:
        products = [product_serializer(row) for row in connection.execute("SELECT * FROM products WHERE published=1 AND deleted_at IS NULL ORDER BY rowid")]
    catalog = json.dumps({"products": products}, ensure_ascii=False, indent=2).encode("utf-8")
    entries["website-catalog"] = {"id": "website-catalog", "folder": "company", "name": "Published product catalog.json", "kind": "document", "mime": "application/json",
                                   "size": len(catalog), "created_at": None, "source": "website", "data": catalog}
    return entries


def file_payload(row, can_write):
    source = row.get("source", "private")
    result = {"id": row["id"], "name": row["name"], "kind": row["kind"], "size": row["size"], "mime": row["mime"],
              "createdAt": row["created_at"], "source": source, "canDelete": can_write and source == "private",
              "downloadUrl": f"/api/intranet/files/{row['id']}/download"}
    if row["mime"] in RASTER.values():
        result["previewUrl"] = f"/api/intranet/files/{row['id']}/preview"
    return result


def folder_payload(connection, user, folder, library_count=0):
    access = permission(connection, user, folder["id"])
    count = connection.execute("SELECT COUNT(*) FROM shared_files WHERE folder=?", (folder["id"],)).fetchone()[0] if access else None
    if count is not None and folder["id"] == "company":
        count += library_count
    return {**folder, "canRead": bool(access), "canWrite": access == "write", "fileCount": count}


def filename(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 180:
        raise FolderError(400, "Use a file name between 1 and 180 characters.")
    value = value.strip()
    if value in {".", ".."} or re.search(r'[\\/:*?"<>|\x00-\x1f\x7f]', value) or value.endswith("."):
        raise FolderError(400, "Use a file name without path separators or special characters.")
    return value


def raster_extension(data, image_validator):
    extension = image_validator(data)
    if extension:
        return extension
    if data[:6] in {b"GIF87a", b"GIF89a"} and len(data) >= 14 and data[-1:] == b";":
        width, height = int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")
        if 1 <= width <= 16000 and 1 <= height <= 16000 and width * height <= 40_000_000:
            return "gif"
    return None


def upload_content(payload, image_validator):
    name = filename(payload.get("name"))
    if payload.get("kind") == "note":
        if set(payload) != {"name", "kind", "text"}:
            raise FolderError(400, "Send a note title and text.")
        text = payload["text"]
        if not isinstance(text, str) or not text.strip() or len(text) > 20_000 or any(ord(char) < 32 and char not in "\n\r\t" for char in text):
            raise FolderError(400, "Use note text between 1 and 20,000 characters.")
        return name, "note", "text/plain; charset=utf-8", text.encode("utf-8")
    if set(payload) != {"name", "data"} or not isinstance(payload["data"], str):
        raise FolderError(400, "Choose an image or document to upload.")
    match = re.fullmatch(r"data:[A-Za-z0-9.+/-]+;base64,([A-Za-z0-9+/=]+)", payload["data"])
    if not match:
        raise FolderError(400, "Choose a valid base64 file upload.")
    try:
        data = base64.b64decode(match[1], validate=True)
    except (ValueError, binascii.Error):
        raise FolderError(400, "The file encoding is invalid.")
    if not 0 < len(data) <= MAX_FILE:
        raise FolderError(413, "Choose a file no larger than 8 MB.")
    suffix = Path(name).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        extension = raster_extension(data, image_validator)
        if extension and (suffix == ".jpeg" and extension == "jpg" or suffix == "." + extension):
            return name, "image", RASTER[extension], data
        raise FolderError(400, "The image format or dimensions could not be verified.")
    if suffix in {".txt", ".csv"}:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise FolderError(400, "Text and CSV documents must use UTF-8 encoding.")
        if any(ord(char) < 32 and char not in "\n\r\t" for char in text):
            raise FolderError(400, "This text document contains unsupported data.")
        return name, "document", "text/csv; charset=utf-8" if suffix == ".csv" else "text/plain; charset=utf-8", data
    if suffix == ".pdf" and data.startswith(b"%PDF-") and b"%%EOF" in data[-1024:]:
        return name, "document", "application/pdf", data
    if suffix in OFFICE:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                info = archive.infolist()
                names = {item.filename for item in info}
                if len(info) > 2000 or sum(item.file_size for item in info) > 64 * 1024 * 1024 or any(item.flag_bits & 1 for item in info):
                    raise ValueError()
                if "[Content_Types].xml" not in names or OFFICE[suffix][0] not in names or any("vbaproject" in item.casefold() for item in names):
                    raise ValueError()
            return name, "document", OFFICE[suffix][1], data
        except (ValueError, zipfile.BadZipFile):
            raise FolderError(400, "Choose a valid, macro-free Office document.")
    raise FolderError(415, "Supported files: JPG, PNG, WebP, GIF, PDF, UTF-8 TXT/CSV, DOCX, XLSX and PPTX.")


def private_path(server, row):
    # Stored names are generated by the server, never derived from uploaded titles.
    name = row["storage_name"]
    if not re.fullmatch(r"[0-9a-f]{48}\.bin", name):
        raise FolderError(404, "This file is unavailable.")
    path = server.shared_folder_root / name
    if path.is_symlink() or not path.resolve().is_relative_to(server.shared_folder_root) or not path.is_file():
        raise FolderError(404, "This file is unavailable.")
    return path


def upload(handler, user, folder, image_validator):
    # Reject unauthorized uploads before reading their contents; recheck in the write transaction.
    with handler.server.connect() as connection:
        require_folder(connection, user, folder, write=True)
    payload = handler.read_json(maximum=12 * 1024 * 1024)
    name, kind, mime, data = upload_content(payload, image_validator)
    file_id, storage_name = secrets.token_hex(24), secrets.token_hex(24) + ".bin"
    path = handler.server.shared_folder_root / storage_name
    written = False
    try:
        with handler.server.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            handler.fresh_security_user(connection, user)
            require_folder(connection, user, folder, write=True)
            with path.open("xb") as stream:
                written = True
                stream.write(data)
            try:
                path.chmod(0o600)
            except OSError:
                pass
            connection.execute("INSERT INTO shared_files VALUES(?,?,?,?,?,?,?,?,?)", (file_id, folder, name, kind, mime, len(data), storage_name, stamp(), user["id"]))
            result = dict(connection.execute("SELECT * FROM shared_files WHERE id=?", (file_id,)).fetchone())
            handler.audit("folder_file_uploaded", user=user, detail=f"Added {kind} {file_id} to {folder}.", connection=connection)
    except Exception:
        if written:
            path.unlink(missing_ok=True)
        raise
    handler.send_json(201, {"file": file_payload(result, True)})


def resolve_file(handler, connection, user, file_id, product_serializer, write=False):
    if file_id.startswith("website-"):
        require_folder(connection, user, "company", write=write)
        if write:
            raise FolderError(403, "Website originals are read-only in the shared library.")
        row = public_library(handler.server, product_serializer).get(file_id)
    else:
        record = connection.execute("SELECT * FROM shared_files WHERE id=?", (file_id,)).fetchone()
        row = dict(record) if record else None
        if row:
            require_folder(connection, user, row["folder"], write=write)
    if row is None:
        raise FolderError(404, "This file was not found.")
    return row


def send_file(handler, user, file_id, preview, image_validator, product_serializer):
    with handler.server.connect() as connection:
        handler.fresh_security_user(connection, user)
        require_staff(connection, user)
        row = resolve_file(handler, connection, user, file_id, product_serializer)
        if preview and row["mime"] not in RASTER.values():
            raise FolderError(415, "Only verified raster images can be previewed.")
        path = row.get("path") if row.get("source") == "website" else private_path(handler.server, row)
        if row.get("data") is not None:
            data = row["data"]
        elif path:
            if path.stat().st_size > 32 * 1024 * 1024:
                raise FolderError(413, "This file is too large to open here.")
            data = path.read_bytes()
        else:
            raise FolderError(404, "This file is unavailable.")
        if preview and not raster_extension(data, image_validator):
            raise FolderError(415, "The image could not be verified for preview.")
    name = row["name"].rsplit("/", 1)[-1]
    if row["kind"] == "note" and not name.lower().endswith(".txt"):
        name += ".txt"
    handler.send_response(200)
    handler.send_header("Content-Type", row["mime"])
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-store, private")
    handler.send_header("Content-Disposition", ("inline" if preview else "attachment") + "; filename*=UTF-8''" + quote(name, safe=""))
    handler.common_headers()
    handler.end_headers()
    if handler.command != "HEAD":
        handler.wfile.write(data)


def handle(handler, method, path, image_validator, product_serializer):
    if not (path == "/api/intranet" or path.startswith("/api/intranet/") or path == "/api/admin/folder-access" or path.startswith("/api/admin/folder-access/")):
        return False
    user = None
    try:
        reading = method in {"GET", "HEAD"}
        admin_route = path.startswith("/api/admin/")
        user = handler.require_user(admin=admin_route, csrf=not reading)
        if admin_route:
            with handler.server.connect() as connection:
                require_owner(handler, connection, user)
                if reading and path == "/api/admin/folder-access":
                    from colleagues import list_payload
                    result = list_payload(connection)
                    handler.send_json(200, result)
                    return True
            match = re.fullmatch(r"/api/admin/folder-access/([1-9][0-9]{0,14})", path)
            if method == "PATCH" and match:
                update_access(handler, user, int(match[1]))
                return True
            raise FolderError(405 if path == "/api/admin/folder-access" or match else 404, "This action is not supported.")
        with handler.server.connect() as connection:
            handler.fresh_security_user(connection, user)
            staff = profile(connection, user)
            if reading and path == "/api/intranet/access":
                handler.send_json(200, {"allowed": staff["active"] or user["role"] == "admin", "profile": staff, "isAdmin": user["role"] == "admin"})
                return True
            require_staff(connection, user)
            if reading and path == "/api/intranet/folders":
                library_count = len(public_library(handler.server, product_serializer))
                handler.send_json(200, {"folders": [folder_payload(connection, user, folder, library_count) for folder in DEPARTMENTS], "profile": staff, "isAdmin": user["role"] == "admin"})
                return True
            match = re.fullmatch(r"/api/intranet/folders/([a-z]+)/files", path)
            if match:
                folder = match[1]
                access = require_folder(connection, user, folder, write=not reading)
                if reading:
                    library = public_library(handler.server, product_serializer) if folder == "company" else {}
                    rows = [dict(row) for row in connection.execute("SELECT * FROM shared_files WHERE folder=? ORDER BY created_at DESC,id", (folder,))]
                    files = [file_payload(row, access == "write") for row in rows] + [file_payload(row, False) for row in sorted(library.values(), key=lambda item: item["name"].casefold())]
                    handler.send_json(200, {"folder": folder_payload(connection, user, FOLDERS[folder], len(library)), "files": files})
                    return True
        if match and method == "POST":
            upload(handler, user, match[1], image_validator)
            return True
        file_match = re.fullmatch(r"/api/intranet/files/([a-z0-9-]{1,80})(?:/(download|preview))?", path)
        if file_match:
            file_id, action = file_match.groups()
            if reading and action:
                send_file(handler, user, file_id, action == "preview", image_validator, product_serializer)
                return True
            if method == "DELETE" and action is None:
                payload = handler.read_json()
                if payload:
                    raise FolderError(400, "This action does not accept additional fields.")
                with handler.server.connect() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    handler.fresh_security_user(connection, user)
                    require_staff(connection, user)
                    row = resolve_file(handler, connection, user, file_id, product_serializer, write=True)
                    path_to_remove = private_path(handler.server, row)
                    connection.execute("DELETE FROM shared_files WHERE id=?", (file_id,))
                    handler.audit("folder_file_deleted", user=user, detail=f"Removed file {file_id} from {row['folder']}.", connection=connection)
                # A failed transaction must never destroy an otherwise accessible file.
                # Once metadata is committed, even a leftover blob has no download route.
                try:
                    path_to_remove.unlink(missing_ok=True)
                except OSError:
                    handler.audit("folder_file_cleanup_pending", user=user, detail=f"Storage cleanup required for deleted file {file_id}.", severity="warning")
                handler.send_json(200, {"deleted": True})
                return True
        raise FolderError(405 if match or file_match else 404, "This action is not supported.")
    except (FolderError, SecurityError) as error:
        if error.status == 403:
            handler.audit("folder_access_denied", user=user, detail="A restricted shared-folder request was rejected.", severity="warning")
        raise
