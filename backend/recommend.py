"""Student analysis, recommendations and video guidance (notebook cells 86-101)."""
from statistics import mean
from typing import Optional

from . import bkt, config, db


def learner_state(user_id: int) -> list:
    """One row per tracked concept, sorted from most to least weak.

    interaction gap = answers given since this concept was last practised.
    Effective mastery = BKT mastery x (1 - forgetting).
    """
    with db.connect() as c:
        mrows = [dict(r) for r in c.execute("SELECT * FROM mastery WHERE user_id=?", (user_id,))]
        total = c.execute("SELECT COUNT(*) FROM responses WHERE user_id=?", (user_id,)).fetchone()[0]
        out = []
        for m in mrows:
            recent = [r["correct"] for r in c.execute(
                "SELECT correct FROM responses WHERE user_id=? AND concept=? ORDER BY id DESC LIMIT ?",
                (user_id, m["concept"], config.RECENT_WINDOW))]
            recent_acc = mean(recent) if recent else None
            gap = total - m["last_interaction_no"]
            forgetting = bkt.forgetting_score(gap)
            eff = bkt.effective_mastery(m["p_know"], forgetting)
            priority, action = bkt.priority_and_action(eff, recent_acc)
            out.append({
                "concept": m["concept"],
                "bkt_mastery": round(m["p_know"], 4),
                "effective_mastery": round(eff, 4),
                "forgetting_score": round(forgetting, 4),
                "interaction_gap": gap,
                "recent_accuracy": None if recent_acc is None else round(recent_acc, 4),
                "attempts": m["attempts"],
                "correct": m["correct_count"],
                "level": bkt.mastery_level(eff),
                "weakness_score": round(bkt.weakness_score(eff, recent_acc, forgetting), 4),
                "priority": priority,
                "recommended_action": action,
            })
    out.sort(key=lambda r: r["weakness_score"], reverse=True)
    return out


def _mmss(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 60:02d}:{sec % 60:02d}"


def _youtube_link(url: str, start: float) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}t={int(start)}s"


def video_guidance(user_id: int, concept: str) -> Optional[dict]:
    """Best matching YouTube chunk for the concept, with its timestamp range."""
    from . import vector_store
    hits = vector_store.search(user_id, concept, k=1, kinds=["youtube"])
    if not hits:
        return None
    h = hits[0]
    start, end = h.get("start_sec") or 0, h.get("end_sec") or 0
    return {
        "title": h["material_title"],
        "url": _youtube_link(h["source"], start),
        "start_sec": start,
        "end_sec": end,
        "range": f"{_mmss(start)}-{_mmss(end)}",
        "score": round(h["score"], 3),
    }


def study_material(user_id: int, concept: str) -> Optional[dict]:
    from . import vector_store
    hits = vector_store.search(user_id, concept, k=1, kinds=["pdf", "notes"])
    if not hits:
        hits = vector_store.search(user_id, concept, k=1)
    if not hits:
        return None
    h = hits[0]
    text = h["text"].strip()
    return {"material_title": h["material_title"],
            "snippet": text[:400] + ("..." if len(text) > 400 else "")}


def recommendations(user_id: int, top_n: int = 10) -> list:
    rows = learner_state(user_id)[:top_n]
    for r in rows:
        r["study_material"] = study_material(user_id, r["concept"])
        r["video"] = video_guidance(user_id, r["concept"])
    return rows
