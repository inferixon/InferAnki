"""Bounded local runtime-log retention."""

from pathlib import Path


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
