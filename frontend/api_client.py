"""Thin client for the FastAPI backend. Streamlit never touches FAISS or the LLM directly."""
import os
from typing import Optional

import requests

BASE_URL = os.getenv("LEARNMIND_API", "http://127.0.0.1:8000")


class BackendOffline(Exception):
    """The FastAPI backend could not be reached."""


class ApiError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def _detail(resp: requests.Response) -> str:
    try:
        d = resp.json().get("detail", resp.text)
    except ValueError:
        return resp.text[:200]
    if isinstance(d, list):   # Pydantic validation errors
        return "; ".join(f"{'.'.join(map(str, e.get('loc', [])[1:]))}: {e.get('msg', '')}" for e in d)
    return str(d)


def _call(method: str, path: str, timeout: int = 120, **kwargs):
    try:
        resp = requests.request(method, BASE_URL + path, timeout=timeout, **kwargs)
    except requests.RequestException as exc:
        raise BackendOffline(str(exc))
    if resp.status_code >= 400:
        raise ApiError(resp.status_code, _detail(resp))
    return resp.json()


def online() -> bool:
    try:
        return requests.get(BASE_URL + "/health", timeout=2).status_code == 200
    except requests.RequestException:
        return False


def health() -> dict:
    return _call("GET", "/health", timeout=5)


# users
def list_users() -> list:
    return _call("GET", "/users")


def create_user(name: str) -> dict:
    return _call("POST", "/users", json={"name": name})


# materials
def add_pdf(user_id: int, file_name: str, data: bytes, title: Optional[str] = None) -> dict:
    return _call("POST", "/materials/pdf", timeout=300,
                 data={"user_id": user_id, "title": title or ""},
                 files={"file": (file_name, data, "application/pdf")})


def add_notes(user_id: int, title: str, text: str) -> dict:
    return _call("POST", "/materials/notes", json={"user_id": user_id, "title": title, "text": text})


def add_youtube(user_id: int, url: str, title: Optional[str] = None) -> dict:
    return _call("POST", "/materials/youtube", timeout=300,
                 json={"user_id": user_id, "url": url, "title": title or None})


def materials(user_id: int) -> list:
    return _call("GET", f"/materials/{user_id}")


def delete_material(user_id: int, material_id: int) -> dict:
    return _call("DELETE", f"/materials/{user_id}/{material_id}")


# tutor and practice

def ask(user_id: int, question: str, material_ids: Optional[list] = None,
        language: str = "auto") -> dict:
    return _call("POST", "/tutor/ask", json={
        "user_id": user_id,
        "question": question,
        "material_ids": material_ids or None,
        "language": language,
    })


def generate(
    user_id: int,
    material_id: int,
    n: int,
    language: str = "hinglish",
    difficulty: str = "medium",
) -> dict:
    return _call(
        "POST",
        "/practice/generate",
        timeout=300,
        json={
            "user_id": user_id,
            "material_id": material_id,
            "n": n,
            "language": language,
            "difficulty": difficulty,
        },
    )


def next_question(user_id: int, concept: Optional[str] = None,
                  material_id: Optional[int] = None) -> dict:
    params = {"user_id": user_id}
    if concept:
        params["concept"] = concept
    if material_id:
        params["material_id"] = material_id
    return _call("GET", "/practice/next", params=params)


def answer(user_id: int, question_id: int, selected_idx: int) -> dict:
    return _call("POST", "/practice/answer", json={"user_id": user_id, "question_id": question_id,
                                                   "selected_idx": selected_idx})


# analysis
def mastery(user_id: int) -> list:
    return _call("GET", f"/mastery/{user_id}")


def recommendations(user_id: int) -> list:
    return _call("GET", f"/recommendations/{user_id}")


def dashboard(user_id: int) -> dict:
    return _call("GET", f"/dashboard/{user_id}")
