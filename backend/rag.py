"""AI Tutor: retrieve chunks with FAISS, build the prompt, ask the LLM (RAG)."""
import re
from typing import Optional

from . import config, llm, vector_store


SYSTEM_PROMPT = (
    "You are LearnMind's AI Tutor. Answer the student's question using ONLY the context "
    "passages provided. If the context does not contain the answer, say that the student's "
    "material does not cover it and do not guess. Explain simply, step by step when useful, "
    "and cite the passages you used like [1], [2]. Follow the requested response language "
    "strictly. Never switch to an unrelated language."
)

LANGUAGE_INSTRUCTIONS = {
    "auto": (
        "Detect the language of the student's question and reply in that same language. "
        "If the question is in Hinglish, reply in Hinglish."
    ),
    "hinglish": (
        "Reply in natural, simple Hinglish: Hindi expressed mainly in Roman script, "
        "mixed with common English technical terms. Explain for a beginner. "
        "Do not reply in Spanish or another unrelated language."
    ),
    "english": (
        "Reply only in clear, simple English. Explain technical concepts for a beginner. "
        "Do not reply in Spanish or another unrelated language."
    ),
}

_STOP = set("""a an the is are was were be been of to in on for and or not with as by at from that this
these those it its what which who whom how why when where do does did can could should would will
about into than then so if you your i we they he she them his her their our""".split())


def _words(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", text.lower())) - _STOP


def _offline_answer(question: str, hits: list) -> str:
    """No LLM: show the sentences from the retrieved chunks that best match the question."""
    qw = _words(question)
    scored = []
    for h in hits:
        for s in re.split(r"(?<=[.!?])\s+", h["text"]):
            if len(s.split()) >= 4:
                scored.append((len(qw & _words(s)), s.strip()))
    scored.sort(key=lambda x: -x[0])
    top = [s for sc, s in scored[:3] if sc > 0] or [hits[0]["text"][:300]]
    return " ".join(top)


def answer(user_id: int, question: str, material_ids: Optional[list] = None,
           language: str = "auto") -> dict:
    hits = vector_store.search(user_id, question, k=config.TOP_K, material_ids=material_ids)
    if not hits:
        return {"answer": "I could not find anything in your material yet. "
                          "Add a PDF, notes or a YouTube video first.",
                "sources": [], "mode": "no-material"}

    sources = [{"n": i, "chunk_id": h["chunk_id"], "material_title": h["material_title"],
                "kind": h["kind"], "text": h["text"], "score": round(h["score"], 3),
                "start_sec": h.get("start_sec")} for i, h in enumerate(hits, 1)]

    if llm.available():
        context = "\n\n".join(f"[{s['n']}] ({s['material_title']}) {s['text']}" for s in sources)
        language_instruction = LANGUAGE_INSTRUCTIONS.get(
        language, LANGUAGE_INSTRUCTIONS["auto"])
        user_msg = (
        f"Response language instruction: {language_instruction}\n\n"
        f"Context:\n{context}\n\nStudent question: {question}")
        try:
            text = llm.chat([{"role": "system", "content": SYSTEM_PROMPT},
                             {"role": "user", "content": user_msg}], temperature=0.2)
            return {"answer": text.strip(), "sources": sources, "mode": f"groq:{llm.model_name()}"}
        except llm.LLMError as exc:
            note = f"(LLM unavailable: {exc}. Showing the most relevant passages instead.)\n\n"
            return {"answer": note + _offline_answer(question, hits),
                    "sources": sources, "mode": "offline-fallback"}

    note = "(Offline mode: GROQ_API_KEY is not set, so this is an extract from your material.)\n\n"
    return {"answer": note + _offline_answer(question, hits), "sources": sources, "mode": "offline"}
