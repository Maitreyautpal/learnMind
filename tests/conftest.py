import os
import tempfile

# Must be set BEFORE the backend is imported.
_tmp = tempfile.mkdtemp(prefix="learnmind_test_")
os.environ["LEARNMIND_DATA_DIR"] = _tmp
os.environ["EMBEDDER"] = "hash"          # no model download in tests
os.environ["CHUNK_WORDS"] = "60"
os.environ["CHUNK_OVERLAP"] = "10"
os.environ.pop("GROQ_API_KEY", None)     # tests run in offline mode

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
