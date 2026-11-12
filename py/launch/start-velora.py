"""Open the account-enabled Velora site, reusing a running local server."""

import json
from pathlib import Path
import socket
import sys
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser

MODULE = Path(__file__).resolve()
ROOT = MODULE.parents[2] if MODULE.parent.name == "launch" and MODULE.parent.parent.name == "py" else MODULE.parent
APP = ROOT / "py" / "app"
sys.path.insert(0, str(APP if APP.is_dir() else ROOT))
SECURITY_REVISION = "2026-11-01.2"

from server import make_server


def main():
    minimum = {(3, 14): (3, 14, 10), (3, 15): (3, 15, 2)}.get(sys.version_info[:2])
    if minimum is None or sys.version_info[:3] < minimum:
        print("Velora needs a supported, security-patched Python runtime. Run Update-VeloraRuntime.cmd, then start Velora again.")
        return 1
    origin = "http://127.0.0.1:8000"
    try:
        with urlopen(origin + "/api/health", timeout=2) as response:
            payload = json.load(response)
            running = response.status == 200 and payload == {"service": "velora", "securityRevision": SECURITY_REVISION}
    except (OSError, URLError, ValueError, TypeError):
        running = False
    if running:
        webbrowser.open(origin + "/login.html")
        print("Opened the running Velora account server.")
        return 0

    # Refuse to initialize/migrate data when another server owns this port.
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=1):
            occupied = True
    except OSError:
        occupied = False
    if occupied:
        print("Port 8000 is used by an older Velora server or another application. Close that server window, then run Start-Velora.cmd again.")
        return 1

    try:
        app = make_server(root=ROOT)
    except (OSError, ValueError) as error:
        print(f"Could not start Velora: {error}")
        print("If an older Velora server is running, close its server window and run Start-Velora.cmd again. Port 8000 must be available.")
        return 1
    print(f"Velora is running at {origin}", flush=True)
    print("Keep this window open while using accounts. Press Ctrl+C to stop.", flush=True)
    try:
        webbrowser.open(origin + "/login.html")
        app.serve_forever()
    except KeyboardInterrupt:
        print("\nVelora stopped.")
    finally:
        app.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
