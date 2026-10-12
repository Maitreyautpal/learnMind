"""Question difficulty and adaptive selection (notebook cells 65, 75, 77)."""
from typing import Iterable, Optional

from . import config


def effective_difficulty(est: float, attempts: int, correct_count: int) -> float:
    """Difficulty = 1 - success_rate once enough answers exist.

    A new question only has the LLM's estimate (easy/medium/hard). As attempts
    grow, the observed failure rate takes over: w = n / (n + 5).
    """
    if attempts <= 0:
        return est
    observed = 1 - (correct_count / attempts)
    w = attempts / (attempts + 5)
    return w * observed + (1 - w) * est


def difficulty_target(mastery: float, previous_correct: Optional[int] = None) -> float:
    """Same rule as adaptive_difficulty_target in the notebook."""
    if previous_correct is None:
        return max(config.DIFF_MIN, mastery - config.DIFF_STEP)
    if previous_correct == 1:
        return min(config.DIFF_MAX, mastery + config.DIFF_STEP)
    return max(config.DIFF_MIN, mastery - config.DIFF_STEP)


def pick_question(candidates: Iterable[dict], target: float) -> Optional[dict]:
    """Candidate whose difficulty is closest to the target."""
    best, best_gap = None, None
    for c in candidates:
        gap = abs(c["difficulty"] - target)
        if best is None or gap < best_gap:
            best, best_gap = c, gap
    if best is not None:
        best = {**best, "difficulty_gap": best_gap}
    return best
