"""Project-relative paths; never select an archive by modification time."""
import json
from pathlib import Path


def project_root():
    return Path(__file__).resolve().parents[2]


def load_config(root=None):
    root = Path(root).resolve() if root else project_root()
    return json.loads((root / "config/project.json").read_text(encoding="utf-8"))


def resolve_path(key, root=None):
    root = Path(root).resolve() if root else project_root()
    path = (root / load_config(root)[key]).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"Configured path escapes project: {key}")
    return path
