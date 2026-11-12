"""Restore logs for images copied successfully just before an interrupted batch.

Only existing project images are recorded. Original generation files are read
for exact SHA256 matching and are never moved or changed.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "py/app"), str(ROOT / "py/tests")]
from project_paths import source_file

import hashlib
import json
from pathlib import Path

ORIGINAL_OUTPUTS = Path("C:/Users/Furkan/.codex/generated_images/01a1aa93-c4dc-7bf2-a8eb-e2529f2b3d6e")


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    jobs = json.loads((ROOT / "json/reports/outfit-items-manifest.json").read_text(encoding="utf-8"))["jobs"]
    candidates = list(ORIGINAL_OUTPUTS.glob("*.png")) if ORIGINAL_OUTPUTS.is_dir() else []
    by_size = {}
    for candidate in candidates:
        by_size.setdefault(candidate.stat().st_size, []).append(candidate)
    recovered = []
    for job in jobs:
        asset, record = ROOT / job["output"], ROOT / ("json/reports/image-generation-" + job["id"] + ".json")
        # Current workers may be writing new garment records. Old interrupted
        # accessory jobs are the only records this recovery step repairs.
        if not job["id"].startswith("item-") or not asset.is_file() or record.is_file():
            continue
        digest = sha(asset)
        original = next((path for path in by_size.get(asset.stat().st_size, []) if sha(path) == digest), None)
        values = {"id": job["id"], "output": job["output"], "source": str(original) if original else None,
                  "reference": job["reference"], "mode": "built-in", "prompt": job["prompt"],
                  "recovered_after_interruption": True, "sha256": digest,
                  "source_match": "exact bytes" if original else "original output path unavailable"}
        try:
            with record.open("x", encoding="utf-8") as stream:
                json.dump(values, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            recovered.append(job["id"])
        except FileExistsError:
            pass
    print(json.dumps({"recovered": recovered}, indent=2))


if __name__ == "__main__":
    main()
