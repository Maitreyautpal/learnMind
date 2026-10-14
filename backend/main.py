"""FastAPI backend. Run:  uvicorn backend.main:app --reload --port 8000"""
import threading
from collections import Counter
from contextlib import asynccontextmanager
from statistics import mean
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import config, db, ingest, llm, practice, rag, recommend, vector_store
from .embeddings import get_embedder
from .schemas import (AnswerRequest, AskRequest, GenerateRequest, NotesMaterial,
                      UserCreate, YouTubeMaterial)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    threading.Thread(target=get_embedder, daemon=True).start()   # warm up the embedding model
    yield


app = FastAPI(title="LearnMind API", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _user(user_id: int) -> dict:
    u = db.get_user(user_id)
    if u is None:
        raise HTTPException(404, "user not found")
    return u


def _store(user_id: int, title: str, kind: str, source: str, chunks: list) -> dict:
    if not chunks:
        raise HTTPException(422, "no content could be extracted")
    mid = db.add_material(user_id, title, kind, source, chunks)
    vector_store.add_material_chunks(user_id)
    return {"material_id": mid, "title": title, "kind": kind, "n_chunks": len(chunks)}


# ------------------------------------------------------------------ health
@app.get("/health")
def health():
    cached = get_embedder.cache_info().currsize > 0
    return {"status": "ok",
            "llm": f"groq:{llm.model_name()}" if llm.available() else "offline (no GROQ_API_KEY)",
            "embedder": get_embedder().name if cached else "loading"}


# ------------------------------------------------------------------- users
@app.post("/users")
def create_user(body: UserCreate):
    return db.get_or_create_user(body.name)


@app.get("/users")
def users():
    return db.list_users()


# --------------------------------------------------------------- materials
@app.post("/materials/pdf")
async def add_pdf(user_id: int = Form(...), title: Optional[str] = Form(None),
                  file: UploadFile = File(...)):
    _user(user_id)
    data = await file.read()
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"file larger than {config.MAX_UPLOAD_MB} MB")
    try:
        text = ingest.extract_pdf_text(data)
    except ingest.IngestError as exc:
        raise HTTPException(422, str(exc))
    return _store(user_id, title or file.filename or "PDF", "pdf", file.filename or "",
                  ingest.chunk_text(text))


@app.post("/materials/notes")
def add_notes(body: NotesMaterial):
    _user(body.user_id)
    return _store(body.user_id, body.title, "notes", "pasted notes",
                  ingest.chunk_text(ingest.clean_text(body.text)))


@app.post("/materials/youtube/transcript")
def add_youtube_transcript(body: NotesMaterial):
    """Save a manually pasted YouTube transcript as chunked material."""
    _user(body.user_id)

    text = ingest.clean_text(body.text)
    if len(text.split()) < 20:
        raise HTTPException(
            422,
            "Transcript is too short. Please provide at least 20 words."
        )

    chunks = ingest.chunk_text(text)
    title = body.title.strip() if body.title else "YouTube transcript"

    return _store(
        body.user_id,
        title,
        "youtube",
        "manually pasted YouTube transcript",
        chunks
    )



@app.post("/materials/youtube")
def add_youtube(body: YouTubeMaterial):
    _user(body.user_id)
    vid = ingest.parse_youtube_id(body.url)
    if vid is None:
        raise HTTPException(422, "could not find a YouTube video id in that URL")
    try:
        chunks = ingest.chunk_segments(ingest.fetch_youtube_segments(vid))
    except ingest.IngestError as exc:
        raise HTTPException(422, str(exc))
    return _store(body.user_id, body.title or f"YouTube {vid}", "youtube",
                  f"https://www.youtube.com/watch?v={vid}", chunks)


@app.get("/materials/{user_id}")
def materials(user_id: int):
    _user(user_id)
    return db.list_materials(user_id)


@app.delete("/materials/{user_id}/{material_id}")
def delete_material(user_id: int, material_id: int):
    if not db.delete_material(user_id, material_id):
        raise HTTPException(404, "material not found")
    vector_store.invalidate(user_id)
    return {"deleted": material_id}


# --------------------------------------------------------------- AI tutor
@app.post("/tutor/ask")
def ask(body: AskRequest):
    _user(body.user_id)
    result = rag.answer(
    body.user_id,
    body.question,
    body.material_ids,
    body.language
)
    with db.connect() as c:
        db.log_event(c, body.user_id, "tutor_question", body.question[:120])
    return result


# ---------------------------------------------------------------- practice

@app.post("/practice/generate")
def generate(body: GenerateRequest):
    _user(body.user_id)

    try:
        return practice.generate(
            body.user_id,
            body.material_id,
            body.n,
            language=body.language,
            difficulty=body.difficulty
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc))


@app.get("/practice/next")
def next_question(user_id: int, concept: Optional[str] = None, material_id: Optional[int] = None):
    _user(user_id)
    q = practice.next_question(user_id, concept, material_id)
    if q is None:
        return {"question": None,
                "message": "No unanswered questions left. Generate more from your material."}
    return {"question": q, "message": ""}


@app.post("/practice/answer")
def answer(body: AnswerRequest):
    _user(body.user_id)
    try:
        return practice.submit_answer(body.user_id, body.question_id, body.selected_idx)
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(409, str(exc))


# ------------------------------------------- mastery, recommendations, home
@app.get("/mastery/{user_id}")
def mastery(user_id: int):
    _user(user_id)
    return recommend.learner_state(user_id)


@app.get("/recommendations/{user_id}")
def recommendations(user_id: int):
    _user(user_id)
    return recommend.recommendations(user_id)


@app.get("/dashboard/{user_id}")
def dashboard(user_id: int):
    user = _user(user_id)
    state = recommend.learner_state(user_id)
    with db.connect() as c:
        answered, right = c.execute(
            "SELECT COUNT(*), COALESCE(SUM(correct),0) FROM responses WHERE user_id=?",
            (user_id,)).fetchone()
        recent = [dict(r) for r in c.execute(
            "SELECT event, detail, created_at FROM history WHERE user_id=? ORDER BY id DESC LIMIT 8",
            (user_id,))]
        n_questions = c.execute("SELECT COUNT(*) FROM questions WHERE user_id=?",
                                (user_id,)).fetchone()[0]
    return {
        "user": user,
        "n_materials": len(db.list_materials(user_id)),
        "n_questions": n_questions,
        "n_answered": answered,
        "accuracy": round(right / answered, 4) if answered else None,
        "n_concepts": len(state),
        "avg_effective_mastery": round(mean(s["effective_mastery"] for s in state), 4) if state else None,
        "levels": dict(Counter(s["level"] for s in state)),
        "weakest": state[:3],
        "recent": recent,
    }
