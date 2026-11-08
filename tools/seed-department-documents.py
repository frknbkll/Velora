"""Add country starter briefs to private department folders without changing access."""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
import secrets
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import shared_folders

COUNTRIES = {
    "NL": ("Netherlands", "Rotterdam"),
    "FR": ("France", "Paris"),
    "GB": ("United Kingdom", "London"),
    "DE": ("Germany", "Frankfurt"),
    "AE": ("United Arab Emirates", "Dubai"),
    "TR": ("Türkiye", "Country presence; no city specified"),
}
VERSION = "country-starters-v1"


def line(value, maximum=600):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or any(ord(char) < 32 for char in value):
        raise ValueError("Starter brief fields must contain bounded, single-line text.")
    return value.strip()


def load_templates(directory):
    departments = {}
    for path in sorted(Path(directory).glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict) or payload.get("version") != 1 or not isinstance(payload.get("departments"), list):
            raise ValueError(f"Invalid starter brief package: {path.name}")
        for department in payload["departments"]:
            key = department.get("id")
            if key not in shared_folders.FOLDERS or key == "company" or key in departments:
                raise ValueError("Each of the nine departments must occur once.")
            if department.get("name") != shared_folders.FOLDERS[key]["name"]:
                raise ValueError(f"Unexpected department label: {key}")
            briefs = department.get("briefs")
            if not isinstance(briefs, list) or len(briefs) != len(COUNTRIES):
                raise ValueError(f"Six country briefs are required for {key}.")
            seen = set()
            for brief in briefs:
                country = brief.get("countryCode")
                if country not in COUNTRIES or country in seen or brief.get("country") != COUNTRIES[country][0]:
                    raise ValueError(f"Invalid or duplicate country in {key}.")
                seen.add(country)
                for field in ("title", "purpose", "nextAction"):
                    line(brief.get(field))
                for field, expected in (("workItems", 4), ("deliverables", 3)):
                    if not isinstance(brief.get(field), list) or len(brief[field]) != expected:
                        raise ValueError(f"Invalid {field} in {key}/{country}.")
                    for item in brief[field]:
                        line(item)
            departments[key] = department
    if set(departments) != set(shared_folders.FOLDERS) - {"company"}:
        raise ValueError("Starter documents must cover all nine department folders.")
    return departments


def build_documents(templates):
    documents = []
    for folder in shared_folders.FOLDERS:
        if folder == "company":
            continue
        department = templates[folder]
        name = department["name"]
        tracker_name = f"Sample - {name} - Country work tracker.csv"
        ordered = sorted(department["briefs"], key=lambda brief: list(COUNTRIES).index(brief["countryCode"]))
        tracker = io.StringIO(newline="")
        writer = csv.writer(tracker, lineterminator="\r\n")
        writer.writerow(["Country", "Department", "Country brief", "Workstream", "Owner", "Next action", "Approval status", "Target date", "Notes"])
        for brief in ordered:
            code, country = brief["countryCode"], brief["country"]
            document_name = f"Sample - {name} - {country} brief.txt"
            access = (f"Restricted: {name} department membership and an explicit folder grant." if shared_folders.FOLDERS[folder]["sensitive"]
                      else "Private department resource. Current folder permissions apply.")
            text = "\n".join([
                "VELORA | DEPARTMENT WORKSPACE", "DRAFT EXAMPLE - starter working document; review before use.", "",
                line(brief["title"]), f"Department: {name}", f"Country: {country}",
                f"Workspace location reference: {COUNTRIES[code][1]}", f"Access: {access}", "",
                "PURPOSE", line(brief["purpose"]), "", "WORK ITEMS",
                *[f"[ ] {line(item)}" for item in brief["workItems"]], "", "EXPECTED OUTPUTS",
                *[f"- {line(item)}" for item in brief["deliverables"]], "", "REVIEW AND HANDOVER",
                "Workstream owner: Unassigned", "Country reviewer: Unassigned", "Target date: To be agreed",
                "Approval status: Draft example - not approved", "", "SUGGESTED NEXT ACTION", line(brief["nextAction"]), "",
                f"Track ownership and review status in: {tracker_name}", "",
                "This sample contains no live employee records, confirmed commitments or approved financial figures.",
                "Replace placeholders with reviewed information before using it for company operations.", "",
            ])
            # Reuse the same title/text validation as an authenticated note upload.
            _, _, _, data = shared_folders.upload_content({"name": document_name, "kind": "note", "text": text}, lambda _: None)
            documents.append({"key": f"{VERSION}:{folder}:{code}", "folder": folder, "name": document_name,
                              "kind": "note", "mime": "text/plain; charset=utf-8", "data": data})
            writer.writerow([country, name, document_name, brief["title"], "Unassigned", brief["nextAction"], "Draft example - not approved", "", "Sample planning row; no live records or confirmed figures."])
        documents.append({"key": f"{VERSION}:{folder}:tracker", "folder": folder, "name": tracker_name,
                          "kind": "document", "mime": "text/csv; charset=utf-8", "data": tracker.getvalue().encode("utf-8-sig")})
    return documents


def seed_documents(database, source_directory=ROOT / "data/department-documents"):
    database = Path(database).resolve()
    if not database.is_file():
        raise ValueError("The account database was not found. Start Velora once before adding starter documents.")
    documents = build_documents(load_templates(source_directory))
    storage = database.parent / "shared-folders"
    if storage.is_symlink():
        raise ValueError("Private shared-file storage must be a real directory.")
    storage.mkdir(exist_ok=True, mode=0o700)
    storage = storage.resolve()
    connection = sqlite3.connect(database, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA trusted_schema=OFF")
    created = []
    counts = {key: 0 for key in shared_folders.FOLDERS if key != "company"}
    existing = removed = 0
    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='shared_files'").fetchone():
                raise ValueError("Shared folders have not been initialized. Start the latest Velora server first.")
            connection.execute("""CREATE TABLE IF NOT EXISTS shared_document_seeds (
                seed_key TEXT PRIMARY KEY,
                file_id TEXT UNIQUE REFERENCES shared_files(id) ON DELETE SET NULL,
                imported_at TEXT NOT NULL
            )""")
            for document in documents:
                previous = connection.execute("SELECT file_id FROM shared_document_seeds WHERE seed_key=?", (document["key"],)).fetchone()
                if previous is not None:
                    if previous["file_id"] is None:
                        removed += 1
                    else:
                        existing += 1
                    continue
                file_id, storage_name = secrets.token_hex(24), secrets.token_hex(24) + ".bin"
                path = storage / storage_name
                with path.open("xb") as stream:
                    created.append(path)
                    stream.write(document["data"])
                try:
                    path.chmod(0o600)
                except OSError:
                    pass
                now = shared_folders.stamp()
                connection.execute("""INSERT INTO shared_files
                    (id,folder,name,kind,mime,size,storage_name,created_at,created_by) VALUES(?,?,?,?,?,?,?,?,NULL)""",
                    (file_id, document["folder"], document["name"], document["kind"], document["mime"], len(document["data"]), storage_name, now))
                connection.execute("INSERT INTO shared_document_seeds VALUES(?,?,?)", (document["key"], file_id, now))
                counts[document["folder"]] += 1
            if created:
                connection.execute("""INSERT INTO security_events
                    (event_type,severity,actor_name,email_hint,ip,detail,created_at,occurred_at,actor_id)
                    VALUES('folder_library_seeded','info','','','',?,?,?,NULL)""",
                    (f"Added {len(created)} draft example country documents across nine department folders. Access permissions were retained.", shared_folders.stamp(), int(time.time())))
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    finally:
        connection.close()
    return {"added": sum(counts.values()), "alreadyPresent": existing, "previouslyRemoved": removed, "departments": counts,
            "countries": [country for country, _ in COUNTRIES.values()]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / ".velora/velora.sqlite3")
    args = parser.parse_args()
    try:
        result = seed_documents(args.database)
    except (ValueError, OSError, sqlite3.Error, shared_folders.FolderError) as error:
        parser.exit(1, f"Unable to add starter documents: {error}\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
