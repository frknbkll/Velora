"""Audit tooling must inventory private files without opening their contents."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
from unittest import mock

AUDIT = runpy.run_path(str(ROOT / "py/tools/security-audit.py"))


class AuditToolTests(unittest.TestCase):
    def test_private_configuration_and_keys_are_never_opened(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            names = {".env", ".env.local", "deployment.pem", "secret.key"}
            for name in names:
                (root / name).write_text("private fixture", encoding="utf-8")
            (root / "bundle.js").write_text("/* public source */", encoding="utf-8")
            original = Path.read_bytes

            def checked(path):
                self.assertNotIn(path.name, names, "The scanner opened private configuration")
                return original(path)

            with mock.patch.object(Path, "read_bytes", checked):
                result = AUDIT["scan_working_tree"](root)
            self.assertEqual(result["files_scanned"], 1)
            self.assertEqual({item["file"] for item in result["skipped"]}, names)
            self.assertFalse(result["findings"])
            environment = AUDIT["environment_inventory"](root)
            self.assertEqual(environment["environment_files"], [".env", ".env.local"])

    def test_git_private_paths_are_flagged_without_reading_blobs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            calls = []

            def command(arguments, **kwargs):
                calls.append(arguments)
                if "rev-parse" in arguments:
                    return subprocess.CompletedProcess(arguments, 0, (str(root) + "\n").encode(), b"")
                if "rev-list" in arguments:
                    return subprocess.CompletedProcess(arguments, 0, b"abc .env.local\ndef private.pem\n", b"")
                self.fail("A private Git blob was opened")

            with mock.patch.object(AUDIT["subprocess"], "run", side_effect=command):
                report = AUDIT["scan_git"](root)
            self.assertEqual(len(calls), 2)
            self.assertEqual(report["history_blobs_scanned"], 0)
            self.assertEqual({f["file"] for f in report["findings"]}, {".env.local", "private.pem"})

    def test_three_integrity_catches_modified_and_missing_modules(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            vendor = root / "js/vendor/three"
            paths = ["three.module.js", "three.core.js", "addons/controls/OrbitControls.js", "addons/exporters/GLTFExporter.js"]
            files = {}
            for relative in paths:
                target = vendor / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                content = ("/* " + relative + " */").encode()
                target.write_bytes(content)
                files[relative] = {"sha256": hashlib.sha256(content).hexdigest()}
            metadata = root / "json/vendor/three-source.json"
            metadata.parent.mkdir(parents=True)
            metadata.write_text(json.dumps({"version": "fixture", "files": files}), encoding="utf-8")
            self.assertEqual(AUDIT["three_integrity"](root)["integrity"], "matches-recorded-release")
            (vendor / paths[0]).write_bytes(b"modified")
            self.assertEqual(AUDIT["three_integrity"](root)["integrity"], "mismatch")
            (vendor / paths[1]).unlink()
            report = AUDIT["three_integrity"](root)
            self.assertEqual(report["integrity"], "mismatch")
            self.assertEqual(sum(f["integrity"] == "mismatch" for f in report["files"]), 2)

    def test_symlinked_source_is_not_followed(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as external:
            root, outside = Path(folder), Path(external)
            (outside / "outside.js").write_text("private fixture", encoding="utf-8")
            try:
                (root / "linked.js").symlink_to(outside / "outside.js")
                (root / "linked-folder").symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("Symbolic links unavailable in this test environment")
            self.assertEqual(AUDIT["scan_working_tree"](root)["files_scanned"], 0)


if __name__ == "__main__":
    unittest.main()
