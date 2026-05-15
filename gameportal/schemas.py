# Файл: schemas.py
# Pydantic-схемы для валидации данных запросов/ответов

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ── Реплеи ──────────────────────────────────────

class ReplayOut(BaseModel):
    """Схема ответа: данные реплея"""
    id: int
    title: str
    file_url: str
    uploaded_at: datetime
    likes: int

    class Config:
        from_attributes = True   # позволяет создавать из ORM-объектов


# ── Турниры ─────────────────────────────────────

class TournamentCreate(BaseModel):
    """Схема создания турнира"""
    name: str
    game: str
    max_participants: int = 16
    admin_token: str            # токен администратора


class TournamentOut(BaseModel):
    """Схема ответа: данные турнира"""
    id: int
    name: str
    game: str
    status: str
    max_participants: int
    created_at: datetime

    class Config:
        from_attributes = True


class ParticipantCreate(BaseModel):
    """Схема регистрации участника"""
    nickname: str


class ParticipantOut(BaseModel):
    """Схема ответа: участник"""
    id: int
    nickname: str
    tournament_id: int
    registered_at: datetime

    class Config:
        from_attributes = True


class AdminAction(BaseModel):
    """Общая схема для admin-действий"""
    admin_token: str


class MatchResult(BaseModel):
    """Схема записи результата матча"""
    winner_id: int
    admin_token: str


# ── Тиммейты ─────────────────────────────────────

class TeammateCreate(BaseModel):
    """Схема создания анкеты"""
    nickname: str
    game: str
    rank: Optional[str] = ""
    description: Optional[str] = ""


class TeammateOut(BaseModel):
    """Схема ответа: анкета тиммейта"""
    id: int
    nickname: str
    game: str
    rank: Optional[str]
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
