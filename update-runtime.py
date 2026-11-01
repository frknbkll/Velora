"""Install Velora's pinned Python runtime locally without changing other projects."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import secrets
import subprocess
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parent
MAX_ARCHIVE_BYTES = 25 * 1024 * 1024


def install():
    if sys.platform != "win32" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise ValueError("This pinned runtime is for 64-bit Windows. Use the supported Python release for your platform.")
    lock = json.loads((ROOT / "runtime-lock.json").read_text(encoding="utf-8"))
    version, expected = lock["version"], lock["sha256"]
    if not re.fullmatch(r"3\.(?:14|15)\.[0-9]+", version) or not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise ValueError("The runtime lock file is invalid.")
    url = urlsplit(lock["url"])
    if url.scheme != "https" or url.netloc != "www.python.org" or url.path != f"/ftp/python/{version}/python-{version}-embed-amd64.zip" or url.query or url.fragment:
        raise ValueError("Only the pinned official Python distribution is supported.")
    base = ROOT / ".runtime"
    if base.is_symlink() or base.is_junction() or not base.resolve().is_relative_to(ROOT):
        raise ValueError("The local runtime directory must stay inside this project.")
    base.mkdir(exist_ok=True)
    target = base / f"python-{version}"
    if target.exists():
        raise ValueError("The pinned runtime already exists. It has not been overwritten.")
    archive = base / f"python-{version}-{secrets.token_hex(6)}.zip.download"
    digest = hashlib.sha256()
    total = 0
    try:
        with urlopen(Request(lock["url"], headers={"User-Agent": "Velora-runtime-updater"}), timeout=30) as response, archive.open("xb") as output:
            if response.geturl() != lock["url"]:
                raise ValueError("The runtime download unexpectedly redirected.")
            while chunk := response.read(65536):
                total += len(chunk)
                if total > MAX_ARCHIVE_BYTES:
                    raise ValueError("The runtime download exceeded its expected size.")
                digest.update(chunk)
                output.write(chunk)
        if not hmac.compare_digest(digest.hexdigest(), expected):
            raise ValueError("Runtime checksum verification failed; nothing was installed.")
        staging = base / f"python-{version}-staging-{secrets.token_hex(6)}"
        staging.mkdir()
        with zipfile.ZipFile(archive) as package:
            files = package.infolist()
            if sum(info.file_size for info in files) > 100 * 1024 * 1024:
                raise ValueError("The runtime archive is unexpectedly large.")
            for info in files:
                name = PurePosixPath(info.filename)
                if name.is_absolute() or ".." in name.parts or "\\" in info.filename or ":" in info.filename:
                    raise ValueError("The runtime archive contains an unsafe path.")
            package.extractall(staging)
        library_name = "python" + "".join(version.split(".")[:2])
        (staging / (library_name + "._pth")).write_text(library_name + ".zip\n.\n..\\..\n# Site packages and environment search paths remain disabled.\n", encoding="utf-8")
        result = subprocess.run([
            str(staging / "python.exe"), "-I", "-c",
            "import hashlib,json,sqlite3,ssl,sys; print(json.dumps({'version':'.'.join(map(str,sys.version_info[:3])),'sqlite':sqlite3.sqlite_version,'isolated':bool(sys.flags.isolated)}))",
        ], check=True, capture_output=True, text=True, timeout=20)
        verified = json.loads(result.stdout)
        if verified["version"] != version or not verified["isolated"]:
            raise ValueError("The installed runtime failed its self-check.")
        (staging / "velora-runtime-source.json").write_text(json.dumps({**lock, "selfCheck": verified}, indent=2) + "\n", encoding="utf-8")
        os.rename(staging, target)
        print(f"Installed Python {version} for Velora only. Start the app with Start-Velora.cmd.")
    finally:
        if archive.exists():
            archive.unlink()


if __name__ == "__main__":
    try:
        install()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, zipfile.BadZipFile):
        print("The runtime was not installed. Check runtime-lock.json, the network connection and whether the target folder already exists.", file=sys.stderr)
        raise SystemExit(1)
