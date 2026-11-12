"""Check safe launch/reuse without opening a database or browser."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import URLError

spec = importlib.util.spec_from_file_location("velora_launcher", ROOT / "py/launch/start-velora.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def test_old_or_unknown_runtime_does_not_open_database(self):
        for version in ((3,14,8),(3,15,1),(3,13,20)):
            with self.subTest(version=version), patch.object(launcher,"sys",SimpleNamespace(version_info=version)), patch.object(launcher,"make_server") as create, patch.object(launcher,"urlopen") as fetch, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(launcher.main(),1)
                create.assert_not_called()
                fetch.assert_not_called()

    def test_old_server_on_port_does_not_initialize_or_migrate_database(self):
        with patch.object(launcher,"sys",SimpleNamespace(version_info=(3,15,2))), patch.object(launcher,"urlopen",side_effect=URLError("old service")), patch.object(launcher.socket,"create_connection") as connection, patch.object(launcher,"make_server") as create, patch.object(launcher.webbrowser,"open") as open_browser, contextlib.redirect_stdout(io.StringIO()):
            connection.return_value.__enter__.return_value = object()
            self.assertEqual(launcher.main(),1)
            create.assert_not_called()
            open_browser.assert_not_called()

    def test_current_security_revision_reuses_server(self):
        payload=json.dumps({"service":"velora","securityRevision":launcher.SECURITY_REVISION}).encode()
        response=io.BytesIO(payload)
        response.status=200
        with patch.object(launcher,"sys",SimpleNamespace(version_info=(3,15,2))), patch.object(launcher,"urlopen",return_value=response), patch.object(launcher,"make_server") as create, patch.object(launcher.webbrowser,"open") as open_browser, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(launcher.main(),0)
            create.assert_not_called()
            open_browser.assert_called_once_with("http://127.0.0.1:8000/login.html")


if __name__ == "__main__":
    unittest.main()
