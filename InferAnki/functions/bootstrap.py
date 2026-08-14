"""Import-safe InferAnki bootstrap helpers."""

import json
from pathlib import Path
from typing import Callable


def load_addon_version(
    meta_path: str,
    fallback: str = "0.5.1",
    on_error: Callable[[str], None] = print,
) -> str:
    """Read the add-on version without depending on loaded configuration."""
    try:
        path = Path(meta_path)
        if path.exists():
            meta = json.loads(path.read_text(encoding="utf-8"))
            return str(meta.get("dev_version", meta.get("human_version", fallback)))
    except (OSError, TypeError, ValueError) as error:
        on_error(f"Error loading version from meta.json: {str(error)}")
    return fallback
