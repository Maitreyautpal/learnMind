"""BKT maths must reproduce the numbers in notebooks/BKT_code.ipynb and the synopsis."""
import math

from backend import adaptive, bkt


def test_notebook_sequence_cell_33():
    # Notebook cell 33: p0 = 0.20, defaults transit .10 / guess .20 / slip .10
    p, got = 0.20, []
    for r in [1, 1, 0, 1, 1]:
        p = bkt.bkt_update(p, r, p_transit=0.10, p_guess=0.20, p_slip=0.10)
        got.append(round(p, 4))
    assert got == [0.5765, 0.8737, 0.5173, 0.8454, 0.9649]


def test_synopsis_worked_example():
    # Synopsis section 10.2: L=0.40 S=0.10 G=0.20 T=0.15 -> 0.75 then 0.7875
    L, S, G, T = 0.40, 0.10, 0.20, 0.15
    posterior = L * (1 - S) / (L * (1 - S) + (1 - L) * G)
    assert math.isclose(posterior, 0.75)
    assert math.isclose(bkt.bkt_update(L, 1, p_transit=T, p_guess=G, p_slip=S), 0.7875)


def test_fitted_parameters_first_answers():
    assert math.isclose(bkt.bkt_update(0.30, 1), 0.65, abs_tol=1e-9)
    assert math.isclose(bkt.bkt_update(0.30, 0), 0.2462, abs_tol=1e-4)


def test_forgetting_and_weakness():
    assert bkt.forgetting_score(0) == 0
    assert math.isclose(bkt.forgetting_score(100), 1 - math.exp(-1))
    assert bkt.mastery_level(0.49) == "Weak"
    assert bkt.mastery_level(0.60) == "Developing"
    assert bkt.mastery_level(0.70) == "Strong"
    assert bkt.priority_and_action(0.10, 0.0)[0] == "Critical"
    assert bkt.priority_and_action(0.40, 0.2)[0] == "High"
    assert bkt.priority_and_action(0.60, 0.6)[0] == "Medium"
    assert bkt.priority_and_action(0.90, 1.0)[0] == "Low"
    # notebook cell 96 weights
    assert math.isclose(bkt.weakness_score(0.2, 0.0, 0.5), 0.55 * 0.8 + 0.25 * 1.0 + 0.20 * 0.5)


def test_adaptive_target_and_pick():
    assert math.isclose(adaptive.difficulty_target(0.2333), 0.1333, abs_tol=1e-4)   # cell 76 row 1
    assert math.isclose(adaptive.difficulty_target(0.5818, 1), 0.6818, abs_tol=1e-4)
    assert math.isclose(adaptive.difficulty_target(0.3326, 0), 0.2326, abs_tol=1e-4)
    assert adaptive.difficulty_target(0.98, 1) == 0.95
    assert adaptive.difficulty_target(0.02, 0) == 0.05
    best = adaptive.pick_question([{"id": 1, "difficulty": 0.2}, {"id": 2, "difficulty": 0.6}], 0.55)
    assert best["id"] == 2
    # observed failure rate takes over as attempts grow
    assert adaptive.effective_difficulty(0.5, 0, 0) == 0.5
    assert adaptive.effective_difficulty(0.5, 50, 50) < 0.15
