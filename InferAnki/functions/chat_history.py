"""Pure chat-history helpers for InferAnki."""

from typing import Dict, List


def append_turn(
    history: List[Dict[str, str]],
    user_message: str,
    assistant_message: str,
    max_pairs: int,
) -> List[Dict[str, str]]:
    """Append one complete turn and retain at most ``max_pairs`` pairs."""
    try:
        pair_limit = max(0, int(max_pairs))
    except (TypeError, ValueError):
        pair_limit = 10

    updated = list(history) + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": assistant_message},
    ]
    if pair_limit == 0:
        return []
    return updated[-pair_limit * 2 :]
