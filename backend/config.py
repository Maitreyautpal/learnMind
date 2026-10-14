"""Central configuration for LearnMind. Every tunable value lives here.

The BKT numbers come from the grid search in notebooks/BKT_code.ipynb
(best log loss 0.5228 on the first 50,000 interactions of skill_builder_data.csv).
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv is optional
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("LEARNMIND_DATA_DIR", BASE_DIR / "data"))
DB_PATH = DATA_DIR / "learnmind.db"

# ---- Bayesian Knowledge Tracing (notebook cell 40-41) -----------------------
BKT_P_L0 = 0.30       # initial knowledge
BKT_P_TRANSIT = 0.20  # learning
BKT_P_GUESS = 0.30    # guess
BKT_P_SLIP = 0.10     # slip

# ---- Forgetting, weakness score and levels (notebook cells 53, 94, 96, 98) --
FORGET_DECAY = 0.01
W_MASTERY, W_RECENT, W_FORGET = 0.55, 0.25, 0.20
RECENT_WINDOW = 5
LEVEL_WEAK = 0.50
LEVEL_DEVELOPING = 0.70

# ---- Adaptive test (notebook cell 75) ---------------------------------------
DIFF_STEP = 0.10
DIFF_MIN, DIFF_MAX = 0.05, 0.95
DIFFICULTY_PRIOR = {"easy": 0.25, "medium": 0.50, "hard": 0.75}

# ---- Content processing and retrieval ---------------------------------------
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDER = os.getenv("EMBEDDER", "auto")  # auto | hash
EMBED_DIM = 384  # used only by the offline hash embedder
CHUNK_WORDS = int(os.getenv("CHUNK_WORDS", "300"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
TOP_K = int(os.getenv("TOP_K", "4"))
MAX_UPLOAD_MB = 200

# ---- LLM (Groq). Key and model are read at call time from the environment ---
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
