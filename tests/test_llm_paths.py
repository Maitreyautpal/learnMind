"""Groq code paths with the HTTP call faked (no real key or network needed).

This checks our request/response handling against the OpenAI-compatible chat
format that Groq documents. It does not prove a live Groq call works: that
needs your own key (see README, step 5).
"""
import json

import pytest

from backend import llm
from tests.test_api import NOTES


class FakeResp:
    def __init__(self, status, content):
        self.status_code, self._content, self.text = status, content, str(content)

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def _mcq_json(i):
    return json.dumps({"concept": "Calvin cycle", "question": f"Where is carbon fixed? ({i})",
                       "options": ["A) Calvin cycle", "B) Glycolysis", "C) Krebs cycle", "D) Fermentation"],
                       "correct_index": 0, "explanation": "Carbon dioxide is fixed in the Calvin cycle.",
                       "difficulty": "hard"})


@pytest.fixture
def groq(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers})
        if json.get("response_format"):                       # MCQ request
            return FakeResp(200, _mcq_json(len(calls)))
        return FakeResp(200, "The Calvin cycle fixes CO2 into glucose [1].")

    monkeypatch.setattr(llm.requests, "post", fake_post)
    return calls


def _material(client, name):
    uid = client.post("/users", json={"name": name}).json()["id"]
    mid = client.post("/materials/notes", json={"user_id": uid, "title": "Bio", "text": NOTES}).json()["material_id"]
    return uid, mid


def test_rag_prompt_has_instruction_context_and_question(client, groq):
    uid, _ = _material(client, "Groq tutor user")
    res = client.post("/tutor/ask", json={"user_id": uid, "question": "How is carbon dioxide fixed?"}).json()
    assert res["mode"].startswith("groq:") and "[1]" in res["answer"]
    sent = groq[-1]
    assert sent["headers"]["Authorization"] == "Bearer test-key"
    system, user = sent["json"]["messages"]
    assert "ONLY the context" in system["content"]
    assert user["content"].startswith("Context:\n[1]") and "Student question: How is carbon" in user["content"]


def test_mcq_generation_through_llm(client, groq):
    uid, mid = _material(client, "Groq mcq user")
    res = client.post("/practice/generate", json={"user_id": uid, "material_id": mid, "n": 3}).json()
    assert res["mode"] == "groq" and res["created"] == 3
    assert res["concepts"] == ["Calvin cycle"]
    from backend import db
    q = db.unattempted_questions(uid)[0]
    assert q["options"][0] == "Calvin cycle"          # "A) " prefix stripped
    assert q["difficulty_est"] == 0.75                # "hard"


def test_groq_failure_falls_back_to_offline(client, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: FakeResp(500, "boom"))
    uid, mid = _material(client, "Groq failure user")
    ans = client.post("/tutor/ask", json={"user_id": uid, "question": "What is a stomata?"}).json()
    assert ans["mode"] == "offline-fallback" and "LLM unavailable" in ans["answer"]
    gen = client.post("/practice/generate", json={"user_id": uid, "material_id": mid, "n": 3}).json()
    assert gen["mode"] == "offline-fallback" and gen["created"] >= 1 and "500" in gen["note"]
