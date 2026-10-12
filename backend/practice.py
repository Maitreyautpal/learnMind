"""Practice test: adaptive question selection and the answer -> BKT update step."""
from typing import Optional

from . import adaptive, bkt, config, db, mcq, recommend


def generate(
    user_id: int,
    material_id: int,
    n: int,
    language: str = "hinglish",
    difficulty: str = "medium",
) -> dict:
    material = db.get_material(material_id)
    if material is None or material["user_id"] != user_id:
        raise LookupError("material not found")

    return mcq.generate_for_material(
        user_id,
        material_id,
        n,
        language=language,
        difficulty=difficulty,
    )


def _pick_concept(user_id: int, available: dict) -> str:
    """Weakest concept that still has unattempted questions.

    A concept the student has never practised is treated like a fresh concept
    (mastery = P(L0), no recent answers, no forgetting), so new topics and weak
    topics are mixed in a sensible order.
    """
    tracked = {s["concept"]: s["weakness_score"] for s in recommend.learner_state(user_id)}
    fresh_score = bkt.weakness_score(config.BKT_P_L0, None, 0.0)
    return max(available, key=lambda c: (tracked.get(c, fresh_score), len(available[c])))


def next_question(user_id: int, concept: Optional[str] = None,
                  material_id: Optional[int] = None) -> Optional[dict]:
    pool = db.unattempted_questions(user_id, concept=concept, material_id=material_id)
    if not pool:
        return None
    by_concept: dict = {}
    for q in pool:
        by_concept.setdefault(q["concept"], []).append(q)
    chosen = concept if concept in by_concept else _pick_concept(user_id, by_concept)

    state = {s["concept"]: s for s in recommend.learner_state(user_id)}
    mastery = state[chosen]["effective_mastery"] if chosen in state else config.BKT_P_L0

    with db.connect() as c:
        last = c.execute("SELECT correct FROM responses WHERE user_id=? AND concept=? "
                         "ORDER BY id DESC LIMIT 1", (user_id, chosen)).fetchone()
    previous_correct = None if last is None else last["correct"]

    target = adaptive.difficulty_target(mastery, previous_correct)
    cands = [{**q, "difficulty": adaptive.effective_difficulty(
        q["difficulty_est"], q["attempts"], q["correct_count"])} for q in by_concept[chosen]]
    q = adaptive.pick_question(cands, target)
    material = db.get_material(q["material_id"])
    return {
        "question_id": q["id"],
        "concept": q["concept"],
        "question": q["question"],
        "options": q["options"],          # correct_idx is NOT sent to the browser
        "difficulty": round(q["difficulty"], 3),
        "target_difficulty": round(target, 3),
        "current_mastery": round(mastery, 4),
        "material_title": material["title"] if material else "",
        "remaining": len(pool),
    }


def submit_answer(user_id: int, question_id: int, selected_idx: int) -> dict:
    """Check the answer, run the BKT update and store everything in one transaction."""
    with db.connect() as c:
        q = c.execute("SELECT * FROM questions WHERE id=? AND user_id=?",
                      (question_id, user_id)).fetchone()
        if q is None:
            raise LookupError("question not found")
        if c.execute("SELECT 1 FROM responses WHERE user_id=? AND question_id=?",
                     (user_id, question_id)).fetchone():
            raise ValueError("question already answered")

        correct = int(selected_idx == q["correct_idx"])
        n = c.execute("SELECT COUNT(*) FROM responses WHERE user_id=?", (user_id,)).fetchone()[0] + 1
        m = c.execute("SELECT * FROM mastery WHERE user_id=? AND concept=?",
                      (user_id, q["concept"])).fetchone()
        before = m["p_know"] if m else config.BKT_P_L0
        after = bkt.bkt_update(before, correct)

        c.execute("""INSERT INTO mastery(user_id,concept,p_know,attempts,correct_count,
                        last_interaction_no,updated_at) VALUES (?,?,?,?,?,?,?)
                     ON CONFLICT(user_id,concept) DO UPDATE SET
                        p_know=excluded.p_know,
                        attempts=attempts+1,
                        correct_count=correct_count+excluded.correct_count,
                        last_interaction_no=excluded.last_interaction_no,
                        updated_at=excluded.updated_at""",
                  (user_id, q["concept"], after, 1, correct, n, db.now()))
        c.execute("""INSERT INTO responses(user_id,question_id,concept,selected_idx,correct,
                        interaction_no,mastery_before,mastery_after,created_at)
                     VALUES (?,?,?,?,?,?,?,?,?)""",
                  (user_id, question_id, q["concept"], selected_idx, correct, n,
                   before, after, db.now()))
        c.execute("UPDATE questions SET attempts=attempts+1, correct_count=correct_count+? WHERE id=?",
                  (correct, question_id))
        db.log_event(c, user_id, "answer",
                     f"{q['concept']}: {'correct' if correct else 'wrong'} "
                     f"({before:.2f} -> {after:.2f})")

    return {
        "correct": bool(correct),
        "correct_idx": q["correct_idx"],
        "explanation": q["explanation"] or "",
        "concept": q["concept"],
        "mastery_before": round(before, 4),
        "mastery_after": round(after, 4),
        "level": bkt.mastery_level(after),
    }
