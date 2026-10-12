"""Pure BKT, forgetting and weakness maths, ported from notebooks/BKT_code.ipynb.

No database or web code here, so everything can be unit-tested on its own.
"""
import math
from typing import Optional

from . import config


def bkt_predict(p_know: float,
                p_guess: float = config.BKT_P_GUESS,
                p_slip: float = config.BKT_P_SLIP) -> float:
    """Probability that the next answer is correct (notebook: p_correct)."""
    return p_know * (1 - p_slip) + (1 - p_know) * p_guess


def bkt_update(p_know: float, correct: int,
               p_transit: float = config.BKT_P_TRANSIT,
               p_guess: float = config.BKT_P_GUESS,
               p_slip: float = config.BKT_P_SLIP) -> float:
    """Bayes update on the observed answer, then the learning transition."""
    if correct:
        p_obs = p_know * (1 - p_slip) + (1 - p_know) * p_guess
        posterior = p_know * (1 - p_slip) / p_obs if p_obs > 0 else p_know
    else:
        p_obs = p_know * p_slip + (1 - p_know) * (1 - p_guess)
        posterior = p_know * p_slip / p_obs if p_obs > 0 else p_know
    return posterior + (1 - posterior) * p_transit


def forgetting_score(gap: Optional[float], decay: float = config.FORGET_DECAY) -> float:
    """1 - exp(-decay * gap). gap = interactions since this concept was last practised."""
    if gap is None or gap <= 0:
        return 0.0
    return 1 - math.exp(-decay * gap)


def effective_mastery(p_know: float, forgetting: float) -> float:
    return p_know * (1 - forgetting)


def mastery_level(x: float) -> str:
    if x < config.LEVEL_WEAK:
        return "Weak"
    if x < config.LEVEL_DEVELOPING:
        return "Developing"
    return "Strong"


def weakness_score(effective: float, recent_accuracy: Optional[float],
                   forgetting: float) -> float:
    """0.55*(1-effective) + 0.25*(1-recent accuracy) + 0.20*forgetting."""
    recent = 0.5 if recent_accuracy is None else recent_accuracy
    return (config.W_MASTERY * (1 - effective)
            + config.W_RECENT * (1 - recent)
            + config.W_FORGET * forgetting)


def priority_and_action(effective: float, recent_accuracy: Optional[float]):
    recent = 0.5 if recent_accuracy is None else recent_accuracy
    if effective < 0.25 and recent <= 0.20:
        return "Critical", "Relearn concept from basics"
    if effective < 0.50 and recent <= 0.40:
        return "High", "Review concept and practice more"
    if effective < 0.70:
        return "Medium", "Practice targeted questions"
    return "Low", "Continue normal practice"
