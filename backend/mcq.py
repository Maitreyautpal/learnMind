"""MCQ generation from the student's own material.

With a Groq key the LLM writes each question from one chunk. Without a key (or
if Groq fails) a simple fill-in-the-blank generator is used so the app still
works offline. Every question is tagged with a short concept name; BKT tracks
mastery per concept.
"""
import json
import random
import re
from collections import Counter
from typing import Optional

from . import config, db, llm

_STOP = set("""about above after again against because before being below between both could does doing
during each further have having here itself just more most other over same should such than that their
them then there these they this those through under until very were what when where which while with
would your""".split())


# ------------------------------------------------------------------ helpers
def _norm_concept(raw: str, existing: list) -> str:
    c = " ".join(str(raw).split())[:60] or "General"
    c = c[:1].upper() + c[1:]
    for e in existing:                       # reuse an existing spelling
        if e.lower() == c.lower():
            return e
    return c


def _extract_json(text: str) -> Optional[dict]:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except ValueError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except ValueError:
                return None
    return None


def _validate(obj, existing: list) -> Optional[dict]:
    if not isinstance(obj, dict):
        return None
    q = str(obj.get("question", "")).strip()
    opts = obj.get("options")
    if not q or not isinstance(opts, list) or len(opts) != 4:
        return None
    opts = [re.sub(r"^[A-Da-d][\).:]\s+", "", str(o).strip()) for o in opts]
    if any(not o for o in opts) or len({o.lower() for o in opts}) != 4:
        return None
    try:
        idx = int(obj.get("correct_index"))
    except (TypeError, ValueError):
        return None
    if idx not in range(4):
        return None
    diff = config.DIFFICULTY_PRIOR.get(str(obj.get("difficulty", "medium")).lower(), 0.5)
    return {"question": q, "options": opts, "correct_idx": idx,
            "explanation": str(obj.get("explanation", "")).strip(),
            "concept": _norm_concept(obj.get("concept") or "General", existing),
            "difficulty_est": diff}


# ---------------------------------------------------------------------- LLM
def _llm_mcq(passage: str, concepts: list, avoid: list) -> Optional[dict]:
    prompt = (
        "Create ONE multiple-choice question that tests understanding of the passage below.\n"
        "Return ONLY a JSON object with these keys:\n"
        '  "concept": short topic name, 2-4 words. Prefer one of these existing concepts if it '
        f"fits: {concepts[:30]}\n"
        '  "question": the question text (do not mention "the passage")\n'
        '  "options": array of exactly 4 distinct answer strings\n'
        '  "correct_index": integer 0-3\n'
        '  "explanation": one or two sentences justifying the answer from the passage\n'
        '  "difficulty": "easy" or "medium" or "hard"\n'
        "The question must be answerable from the passage alone."
        + (f"\nDo not repeat these questions: {avoid}" if avoid else "")
        + f'\n\nPassage:\n"""{passage[:2200]}"""'
    )
    for attempt in range(2):
        raw = llm.chat([{"role": "system", "content": "You write exam questions. Reply with JSON only."},
                        {"role": "user", "content": prompt}],
                       temperature=0.4 if attempt == 0 else 0.2, json_mode=True, max_tokens=700)
        item = _validate(_extract_json(raw), concepts)
        if item:
            return item
    return None


# ------------------------------------------------------------------ offline
def _keywords(text: str) -> list:
    return [w for w in re.findall(r"[A-Za-z][A-Za-z-]{4,}", text) if w.lower() not in _STOP]


def _offline_mcq(chunk_text: str, pool: list, pass_no: int, rng: random.Random,
                 existing: list) -> Optional[dict]:
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", chunk_text) if 8 <= len(s.split()) <= 35]
    if not sents:
        return None
    sent = sents[pass_no % len(sents)]
    cands = [w for w in re.findall(r"[A-Za-z][A-Za-z-]{5,}", sent) if w.lower() not in _STOP]
    if not cands:
        return None
    target = max(cands, key=len)
    seen, distractors = {target.lower()}, []
    shuffled = pool[:]
    rng.shuffle(shuffled)
    for w in shuffled:
        if w.lower() not in seen and abs(len(w) - len(target)) <= 4:
            seen.add(w.lower())
            distractors.append(w)
        if len(distractors) == 3:
            break
    if len(distractors) < 3:
        return None
    options = distractors + [target]
    rng.shuffle(options)
    top = Counter(w.lower() for w in _keywords(chunk_text)).most_common(1)
    concept = _norm_concept(top[0][0] if top else "General", existing)
    return {"question": "Fill in the blank: " + re.sub(re.escape(target), "_____", sent, count=1),
            "options": options, "correct_idx": options.index(target),
            "explanation": f"The material says: \"{sent}\"",
            "concept": concept, "difficulty_est": 0.5}


# ---------------------------------------------------------------- main entry
def generate_for_material(
    user_id: int,
    material_id: int,
    n: int,
    language: str = "hinglish",
    difficulty: str = "medium",
) -> dict:
    chunks = db.get_chunks(user_id, material_id)
    if not chunks:
        raise LookupError("material has no content")
    if n < len(chunks):                                  # spread questions over the material
        chunks = [chunks[int(i * len(chunks) / n)] for i in range(n)]

    existing = db.existing_concepts(user_id)
    pool = sorted({w for ch in chunks for w in _keywords(ch["text"])})
    rng = random.Random(material_id)
    use_llm, mode, note = llm.available(), "groq" if llm.available() else "offline", None

    created, calls, pass_no = [], 0, 0
    while len(created) < n and calls < n * 3:
        progressed = False
        for ch in chunks:
            if len(created) >= n or calls >= n * 3:
                break
            calls += 1
            item = None
            if use_llm:
                try:
                    avoid = [c["question"] for c in created if c["chunk_id"] == ch["id"]]
                    item = _llm_mcq(ch["text"], existing + [c["concept"] for c in created], avoid)
                except llm.LLMError as exc:
                    note, use_llm, mode = str(exc), False, "offline-fallback"
            if item is None and not use_llm:
                item = _offline_mcq(ch["text"], pool, pass_no, rng,
                                    existing + [c["concept"] for c in created])
            if item is None:
                continue
            qid = db.add_question(user_id, material_id, ch["id"], item["concept"], item["question"],
                                  item["options"], item["correct_idx"], item["explanation"],
                                  item["difficulty_est"])
            if qid:
                created.append({**item, "id": qid, "chunk_id": ch["id"]})
                progressed = True
        pass_no += 1
        if not progressed:
            break

    with db.connect() as c:
        db.log_event(c, user_id, "questions_generated", f"{len(created)} ({mode})")
    return {"created": len(created), "mode": mode, "note": note,
            "concepts": sorted({c["concept"] for c in created})}
