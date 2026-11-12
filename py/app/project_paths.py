"""Resolve Velora's readable source folders without changing public page URLs.

The fallback supports deliberately flat, disposable test sites and old imported
fixtures. The real checkout keeps its source files in the typed directories.
"""
from pathlib import Path


def project_root(module_file):
    module = Path(module_file).resolve()
    if module.parent.parent.name == "py" and module.parent.name in {"app", "launch", "tools", "tests"}:
        return module.parents[2]
    return module.parent


def source_file(root, folder, name):
    root = Path(root)
    organized = root / folder / name
    legacy = root / name
    return organized if organized.is_file() or not legacy.is_file() else legacy
