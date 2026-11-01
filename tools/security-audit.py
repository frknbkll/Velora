"""Local, dependency-free inventory and redacted secret scan.

This is a focused source/artefact check, not a vulnerability-scanner certification.
It never opens the private database or the MFA master key and never prints matches.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
MAX_TEXT_BYTES = 2 * 1024 * 1024
EXCLUDED = {".git", ".velora", ".runtime", ".venv", "venv", "node_modules", "__pycache__"}
TEXT_SUFFIXES = {".html", ".js", ".css", ".py", ".md", ".json", ".txt", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".cmd", ".bat", ".ps1", ".xml", ".lock", ".pem", ".key"}
PROJECT_MODULES = {"server", "security_core", "runtime_launcher", "__future__"}
SECRET_NAMES = re.compile(r"(?:SECRET|TOKEN|API_?KEY|PASSWORD|CREDENTIAL)", re.I)
PATTERNS = (
    ("private-key-material", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----")),
    ("openai-style-secret", re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}\b")),
    ("github-secret", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b")),
    ("aws-access-key-id", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("slack-secret", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("stripe-live-secret", re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{20,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("credential-in-url", re.compile(r"\b(?:https?|postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://[^\s/:@]+:[^\s/@]+@[^\s/]+")),
)
ASSIGNMENT = re.compile(r"\b(?:api[_-]?key|secret[_-]?key|client[_-]?secret|access[_-]?token|aws_secret_access_key)\s*[:=]\s*['\"]([A-Za-z0-9_./+=:-]{20,})['\"]", re.I)


def entropy(value):
    return -sum((value.count(character) / len(value)) * math.log2(value.count(character) / len(value)) for character in set(value))


def findings_for_text(text, relative, *, source="working-tree"):
    """Return locations/categories only; no snippets, hashes or secret values."""
    findings = []
    for category, pattern in PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"category": category, "file": relative, "line": text.count("\n", 0, match.start()) + 1, "source": source})
    for match in ASSIGNMENT.finditer(text):
        value = match.group(1)
        if entropy(value) < 3.5 or any(word in value.lower() for word in ("example", "placeholder", "your-api", "your_api", "replace-me", "replace_me")):
            continue
        findings.append({"category": "literal-secret-assignment", "file": relative, "line": text.count("\n", 0, match.start()) + 1, "source": source})
    return findings


def candidate_files(root):
    for directory, folders, files in os.walk(root, followlinks=False):
        path = Path(directory)
        folders[:] = [name for name in folders if name not in EXCLUDED and not (path == root / "tmp")]
        for name in files:
            file = path / name
            relative = file.relative_to(root)
            if name == "security.key" or name.endswith((".sqlite3", ".sqlite3-wal", ".sqlite3-shm")):
                continue
            if file.is_symlink() or not file.resolve().is_relative_to(root):
                continue
            if file.suffix.lower() in TEXT_SUFFIXES or name.startswith(".env") or name in {".gitignore", ".python-version"}:
                yield file, str(relative).replace("\\", "/")


def scan_working_tree(root):
    findings, skipped, count = [], [], 0
    for file, relative in candidate_files(root):
        try:
            if file.stat().st_size > MAX_TEXT_BYTES:
                skipped.append({"file": relative, "reason": "size-limit"})
                continue
            raw = file.read_bytes()
            if b"\0" in raw:
                skipped.append({"file": relative, "reason": "binary"})
                continue
            content = raw.decode("utf-8-sig")
        except (OSError, UnicodeError):
            skipped.append({"file": relative, "reason": "unreadable-or-not-utf8"})
            continue
        count += 1
        findings.extend(findings_for_text(content, relative))
    return {"files_scanned": count, "findings": findings, "skipped": skipped}


def scan_git(root):
    try:
        location = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root, capture_output=True, check=False, timeout=10)
        if location.returncode:
            return {"status": "no-repository", "history_blobs_scanned": 0, "findings": [], "limits": ["This workspace is not in a Git checkout; deleted commits and remote repositories cannot be assessed."]}
        checkout = Path(location.stdout.decode("utf-8").strip()).resolve()
        if checkout != root:
            return {"status": "ancestor-repository-not-scanned", "history_blobs_scanned": 0, "findings": [], "limits": ["The Git checkout is outside this workspace; its unrelated history is not scanned by this command."]}
        listed = subprocess.run(["git", "-c", "core.quotepath=false", "rev-list", "--objects", "--all"], cwd=root, capture_output=True, check=False, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "unavailable", "history_blobs_scanned": 0, "findings": [], "limits": ["Git history could not be enumerated."]}
    if listed.returncode:
        return {"status": "unavailable", "history_blobs_scanned": 0, "findings": [], "limits": ["Git history could not be enumerated."]}
    count, findings, skipped = 0, [], 0
    for row in listed.stdout.decode("utf-8", errors="replace").splitlines():
        parts = row.split(" ", 1)
        if len(parts) < 2:
            continue
        oid, relative = parts
        path = Path(relative)
        # Record tracked private artefacts without reading their contents.
        if any(part in EXCLUDED - {".git"} for part in path.parts) or path.name == "security.key" or path.suffix.lower() in {".sqlite3", ".pfx", ".p12"}:
            if path.name == "security.key" or ".velora" in path.parts or path.suffix.lower() in {".sqlite3", ".pfx", ".p12"}:
                findings.append({"category": "private-file-in-history", "file": relative, "line": None, "source": "git-history"})
            skipped += 1
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and not path.name.startswith(".env"):
            continue
        try:
            metadata = subprocess.run(["git", "cat-file", "-s", oid], cwd=root, capture_output=True, check=False, timeout=10)
            if metadata.returncode or int(metadata.stdout.strip()) > MAX_TEXT_BYTES:
                skipped += 1
                continue
            blob = subprocess.run(["git", "cat-file", "blob", oid], cwd=root, capture_output=True, check=False, timeout=10)
            if blob.returncode or b"\0" in blob.stdout:
                skipped += 1
                continue
            content = blob.stdout.decode("utf-8-sig")
        except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired):
            skipped += 1
            continue
        count += 1
        findings.extend(findings_for_text(content, relative, source="git-history"))
    return {"status": "scanned", "history_blobs_scanned": count, "history_objects_skipped": skipped, "findings": findings, "limits": ["Only reachable text blobs up to 2 MiB are scanned; private binary files are flagged by path, never opened. Unreachable/deleted Git objects and remote-only history are not scanned."]}


def dependency_inventory(root):
    imports = {}
    local_modules = PROJECT_MODULES | {file.stem for file in root.glob("*.py")}
    for file in root.glob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8-sig"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(item.name.split(".")[0] for item in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".")[0])
        imports[file.name] = sorted(names - set(sys.stdlib_module_names) - local_modules)
    vendor = root / "assets/vendor/qrcodegen.js"
    manifest = root / "assets/vendor/qrcodegen-source.json"
    vendor_state = {"name": "Nayuki QR Code Generator", "version": None, "integrity": "not-present"}
    if vendor.is_file() and manifest.is_file():
        metadata = json.loads(manifest.read_text(encoding="utf-8"))
        vendor_state = {"name": metadata.get("name"), "version": metadata.get("version"), "integrity": "matches-recorded-release" if hashlib.sha256(vendor.read_bytes()).hexdigest() == metadata.get("sha256") else "mismatch"}
    manifests = [file.name for file in root.iterdir() if file.name in {"package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "requirements.txt", "requirements-dev.txt", "pyproject.toml", "poetry.lock", "uv.lock", "Pipfile", "Pipfile.lock"}]
    return {"python_runtime_executing_audit": sys.version.split()[0], "third_party_python_imports_by_entry_file": imports, "package_manifests": manifests, "vendor": vendor_state, "note": "This command does not contact vulnerability databases or update unrelated global packages."}


def environment_inventory(root):
    names = sorted(key for key in os.environ if SECRET_NAMES.search(key))
    debug = {}
    for key in ("DEBUG", "FLASK_DEBUG", "DJANGO_DEBUG", "NODE_ENV", "APP_ENV", "ENVIRONMENT"):
        if key in os.environ:
            value = os.environ[key].strip().lower()
            debug[key] = "disabled-or-production" if value in {"0", "false", "off", "no", "production", "prod", ""} else "enabled-or-development" if value in {"1", "true", "on", "yes", "debug", "development", "dev"} else "set-nonboolean"
    env_files = sorted(relative for _, relative in candidate_files(root) if Path(relative).name.startswith(".env"))
    return {"sensitive_variable_names_present": names, "debug_classification": debug, "environment_files": env_files, "values_are_never_reported": True}


def audit(root):
    root = root.resolve()
    working, git = scan_working_tree(root), scan_git(root)
    ignored = (root / ".gitignore").read_text(encoding="utf-8") if (root / ".gitignore").is_file() else ""
    gaps = [pattern for pattern in (".velora/", ".env", ".env.*", "tmp/", ".runtime/") if pattern not in ignored.splitlines()]
    dependencies = dependency_inventory(root)
    return {
        "scope": "Workspace source, small text build/test artefacts, environment names, reachable Git text history and recorded QR dependency integrity. Private database/master-key contents are never read.",
        "working_tree": working,
        "git": git,
        "environment": environment_inventory(root),
        "dependencies": dependencies,
        "gitignore_patterns_missing": gaps,
        "private_storage": {"database_exists": (root / ".velora/velora.sqlite3").is_file(), "master_key_exists": (root / ".velora/security.key").is_file(), "contents_read": False},
        "limits": ["Pattern scanning cannot prove that every secret is absent; provider-revocation status and external services are outside this local check.", "No host/network penetration test or full dependency vulnerability-database scan is performed by this command.", "Skipped files and absent Git history are reported, not treated as proven clean."],
    }


def self_test():
    # Compose harmless synthetic values at runtime so the scanner source has no embedded keys.
    sample = "sk-" + "proj-" + "A1b2C3d4" * 6
    hits = findings_for_text("value = '" + sample + "'\n", "fixture.py")
    assert hits and hits[0]["line"] == 1
    assert sample not in json.dumps(hits)
    assert not findings_for_text("api_key = 'your_api_key_placeholder'", "example.py")
    with tempfile.TemporaryDirectory(prefix="velora-secret-scan-") as temporary:
        folder = Path(temporary)
        (folder / ".velora").mkdir()
        (folder / ".velora/security.key").write_text(sample)
        (folder / "bundle.js").write_text("const token = '" + sample + "';")
        result = scan_working_tree(folder)
        assert result["files_scanned"] == 1 and len(result["findings"]) == 1
        assert sample not in json.dumps(result)
    print("PASS: scanner detection, redaction, placeholders and private-file exclusions")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit a sanitized machine-readable report.")
    parser.add_argument("--self-test", action="store_true", help="Test detection/redaction against disposable synthetic fixtures.")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    report = audit(ROOT)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        findings = report["working_tree"]["findings"] + report["git"]["findings"]
        print(f"Scanned {report['working_tree']['files_scanned']} workspace text files; secret-pattern findings: {len(findings)}.")
        for item in findings:
            print(json.dumps(item))
        print("Git:", report["git"]["status"])
        print("Python audit runtime:", report["dependencies"]["python_runtime_executing_audit"])
        print("QR dependency integrity:", report["dependencies"]["vendor"]["integrity"])
        print("Missing ignore rules:", ", ".join(report["gitignore_patterns_missing"]) or "none")
        print("Matched values were not printed; database and MFA master-key contents were not read.")
        print("Scope limits are listed in --json output and SECURITY_AUDIT.md.")
    return int(bool(report["working_tree"]["findings"] or report["git"]["findings"] or report["dependencies"]["vendor"]["integrity"] == "mismatch"))


if __name__ == "__main__":
    raise SystemExit(main())
