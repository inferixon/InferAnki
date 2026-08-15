"""Bounded local runtime-log retention."""

from datetime import datetime
from pathlib import Path
import traceback


def prune_log_files(log_dir: str, pattern: str, max_files: int) -> None:
    """Delete oldest matching logs after a successful newer write."""
    try:
        limit = max(1, int(max_files))
        files = sorted(
            Path(log_dir).glob(pattern),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for stale_path in files[limit:]:
            stale_path.unlink(missing_ok=True)
    except (OSError, TypeError, ValueError):
        pass


def log_runtime_error(log_dir: str, operation: str, error: BaseException) -> str:
    """Append one exception traceback without serializing local variables."""
    destination = Path(log_dir) / "error.log"
    destination.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    traceback_text = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    ).rstrip()
    with destination.open("a", encoding="utf-8") as handle:
        handle.write(
            f"[{timestamp}] {operation}\n{traceback_text}\n\n"
        )
    return str(destination)
