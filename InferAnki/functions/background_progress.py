"""Small wrappers around Anki's native background progress UI."""

from typing import Any, Callable


def run_with_progress(
    mw: Any,
    task: Callable[[], Any],
    on_done: Callable[[Any], None],
    label: str,
    parent: Any = None,
) -> None:
    """Run network work behind an immediate application-modal Anki dialog."""
    mw.taskman.with_progress(
        task,
        on_done,
        parent=parent,
        label=label,
        immediate=True,
        uses_collection=False,
    )


def run_with_optional_progress(
    mw: Any,
    task: Callable[[], Any],
    on_done: Callable[[Any], None],
    label: str,
    show_progress: bool,
    parent: Any = None,
) -> None:
    """Run background work with an immediate modal only when requested."""
    if show_progress:
        run_with_progress(
            mw,
            task,
            on_done,
            label,
            parent=parent,
        )
        return
    mw.taskman.run_in_background(task, on_done, uses_collection=False)
