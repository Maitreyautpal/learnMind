# LearnMind: A Personalized AI Learning Assistant

Streamlit frontend + FastAPI backend + RAG (Sentence Transformers, FAISS, Groq) + Bayesian Knowledge
Tracing + SQLite. Everything runs locally on a laptop.

```
LearnMind/
├── backend/                 FastAPI app (all logic lives here)
│   ├── main.py              endpoints
│   ├── schemas.py           Pydantic request models (validation)
│   ├── config.py            every tunable number: BKT parameters, chunk size, k, model names
│   ├── db.py                SQLite schema + queries (transactions)
│   ├── ingest.py            PDF / notes / YouTube -> chunks
│   ├── embeddings.py        Sentence Transformers (hash fallback when offline)
│   ├── vector_store.py      FAISS index + lookup list
│   ├── llm.py               Groq call
│   ├── rag.py               AI Tutor: retrieve -> prompt -> LLM
│   ├── mcq.py               MCQ generation from the student's material
│   ├── bkt.py               BKT, forgetting, weakness score (from the notebook)
│   ├── adaptive.py          difficulty + adaptive question selection (from the notebook)
│   ├── practice.py          next question, answer -> BKT update
│   └── recommend.py         weak concepts, study material, video + timestamp
├── frontend/                Streamlit app, 7 pages
│   ├── app.py               navigation, student selector, Demo-mode badge
│   ├── api_client.py        the only code that talks to FastAPI
│   ├── pages/               dashboard, my_learning, add_material, ai_tutor,
│   │                        practice_test, my_mastery, recommendations
│   ├── components/ui.py     reusable widgets
│   └── utils/               session state, formatting, demo data
├── notebooks/BKT_code.ipynb your research notebook (kept as is)
├── tests/                   16 tests (BKT numbers, API flow, YouTube, Groq paths)
├── requirements.txt  .env.example  pytest.ini
```

## 1. Setup (Python 3.10 or newer)

```bash
cd LearnMind
python -m venv .venv
# Windows:  .venv\Scripts\activate        Mac/Linux:  source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env   then put your GROQ_API_KEY in .env
```

## 2. Run (two terminals, both inside LearnMind/, venv active)

```bash
# Terminal 1: backend
uvicorn backend.main:app --port 8000

# Terminal 2: frontend
streamlit run frontend/app.py
```

Open http://localhost:8501. The first start downloads the embedding model (about 90 MB), so the first
upload can take a minute. API docs are at http://localhost:8000/docs.

If the backend is not running, the sidebar shows an orange **Demo mode** badge and the Dashboard, My Learning,
My Mastery and Recommendations pages show sample data.

Without `GROQ_API_KEY` the app still works in **offline mode**: the tutor shows the best matching sentences
from your material and the test uses fill-in-the-blank questions. Put a key in `.env` for real LLM answers and
MCQs.

## 3. Demo script (viva)

1. Sidebar: create a student.
2. Add Material: upload a PDF or paste notes; add one YouTube link that has captions.
3. AI Tutor: ask a doubt; open "Sources" to show the retrieved chunks (this is the RAG step).
4. Practice Test: generate 8 questions, then answer 5 to 6, getting some wrong on purpose. Show the mastery change
   after each answer (BKT).
5. My Mastery: concept-wise mastery, the Weak / Developing / Strong level, effective mastery after forgetting.
6. Recommendations: priority, the study passage and the video link with the timestamp range.
7. Stop the backend and refresh: Demo mode badge appears.

## 4. How the notebook maps to the app

| Notebook (BKT_code.ipynb) | App |
|---|---|
| `bkt_update` (cell 32) | `backend/bkt.py: bkt_update` |
| best parameters from grid search (cells 40-41) | `backend/config.py` (P(L0) 0.30, P(T) 0.20, P(G) 0.30, P(S) 0.10) |
| `mastery_level` (cell 53) | `bkt.mastery_level` (Weak < 0.50, Developing < 0.70, else Strong) |
| forgetting score, decay 0.01 (cells 90-94) | `bkt.forgetting_score`, `recommend.learner_state` |
| weakness score 0.55 / 0.25 / 0.20 (cell 96) | `bkt.weakness_score` |
| priority rules (cell 98) | `bkt.priority_and_action` |
| question difficulty (cell 65) | `adaptive.effective_difficulty` |
| `adaptive_difficulty_target`, selection (cells 75-77) | `adaptive.difficulty_target`, `adaptive.pick_question`, `practice.next_question` |
| adaptive test loop (cell 80) | Practice Test page: `practice.next_question` then `practice.submit_answer` |
| `get_student_recommendation` (cell 100) | `recommend.recommendations` |

The notebook itself stays your research and evaluation record (ASSISTments data, log loss, AUC). The app uses the
resulting parameters on the student's own concepts.

## 5. Values for your report (the old "[To be confirmed]" items)

| Item | Value in this code |
|---|---|
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional) |
| Chunk size / overlap | 300 words / 50 words (YouTube: about 300 words per chunk, no overlap, timestamps kept) |
| k (chunks retrieved) | 4 |
| FAISS index type | `IndexFlatIP` on L2-normalised vectors (cosine similarity), one index per student |
| LLM | Groq (GroqCloud), default model `llama-3.3-70b-versatile` (set `GROQ_MODEL`; check current names on the Groq console) |
| BKT parameters | P(L0) 0.30, P(T) 0.20, P(G) 0.30, P(S) 0.10 (grid search, notebook) |
| Forgetting | 1 - exp(-0.01 x interaction gap) |
| Endpoints | `GET /health`, `POST/GET /users`, `POST /materials/pdf` `/notes` `/youtube`, `GET /materials/{user_id}`, `DELETE /materials/{user_id}/{material_id}`, `POST /tutor/ask`, `POST /practice/generate`, `GET /practice/next`, `POST /practice/answer`, `GET /mastery/{user_id}`, `GET /recommendations/{user_id}`, `GET /dashboard/{user_id}` |
| SQLite tables | `users`, `materials`, `chunks` (text, timestamps, embedding), `questions`, `responses`, `mastery`, `history` (columns: see `backend/db.py`) |

## 6. Known limitations (say these honestly in the report)

- BKT parameters were fitted on the ASSISTments `skill_builder_data.csv`, not on LearnMind users.
- One global parameter set is used for all concepts.
- Concepts and MCQs come from the LLM, so quality depends on the model and on the retrieved text.
- Each student has their own question bank and each question is asked once, so question difficulty is the LLM's
  estimate (easy 0.25, medium 0.50, hard 0.75). The observed success rate (notebook cell 65) only takes over once
  many answers per question exist, for example with a shared question bank.
- Forgetting uses the number of answers in between, not clock time (the dataset has no timestamps).
- Level (Weak / Developing / Strong) is computed on effective mastery; the notebook computed it on raw BKT mastery.
- No login: students are picked by name. SQLite and Streamlit suit a prototype, not many users.
- The adaptive test in the notebook was simulated; in the app it uses real answers, but it has not been tested on
  real students.

## 7. Tests

```bash
pytest
```

16 tests: BKT numbers equal the notebook and the synopsis example; the API flow (add notes, tutor, generate, answer,
mastery, recommendations, dashboard); YouTube chunking and timestamp guidance; Groq request and fallback handling
with a faked HTTP call.
