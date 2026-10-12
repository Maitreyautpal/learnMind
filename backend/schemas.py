"""Request bodies. Pydantic rejects wrong data before any handler runs."""
from typing import List, Optional

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class NotesMaterial(BaseModel):
    user_id: int
    title: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=50)


class YouTubeMaterial(BaseModel):
    user_id: int
    url: str = Field(min_length=11)
    title: Optional[str] = Field(default=None, max_length=120)



class AskRequest(BaseModel):
    user_id: int
    question: str = Field(min_length=3, max_length=1000)
    material_ids: Optional[List[int]] = None
    language: str = Field(
        default="auto",
        pattern="^(auto|hinglish|english)$"
    )


class GenerateRequest(BaseModel):
    user_id: int
    material_id: int
    n: int = Field(default=10, ge=1, le=20)
    language: str = Field(
        default="hinglish",
        pattern="^(hinglish|english|hindi)$",
    )
    difficulty: str = Field(
        default="medium",
        pattern="^(easy|medium|hard)$",
    )


class AnswerRequest(BaseModel):
    user_id: int
    question_id: int
    selected_idx: int = Field(ge=0, le=3)
