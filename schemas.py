# Файл: schemas.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ReplayOut(BaseModel):
    id: int
    title: str
    file_url: str
    uploaded_at: datetime
    likes: int
    class Config:
        from_attributes = True


class TournamentCreate(BaseModel):
    name: str
    game: str
    max_participants: int = 16
    admin_token: str


class TournamentOut(BaseModel):
    id: int
    name: str
    game: str
    status: str
    max_participants: int
    created_at: datetime
    class Config:
        from_attributes = True


class ParticipantCreate(BaseModel):
    nickname: str


class ParticipantOut(BaseModel):
    id: int
    nickname: str
    tournament_id: int
    registered_at: datetime
    class Config:
        from_attributes = True


class AdminAction(BaseModel):
    admin_token: str


class MatchResult(BaseModel):
    winner_id: int
    admin_token: str


class TeammateCreate(BaseModel):
    nickname: str
    game: str
    rank: Optional[str] = ""
    description: Optional[str] = ""


class TeammateOut(BaseModel):
    id: int
    nickname: str
    game: str
    rank: Optional[str]
    description: Optional[str]
    created_at: datetime
    steam_id: Optional[str] = None
    class Config:
        from_attributes = True