# Файл: models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base


class Replay(Base):
    __tablename__ = "replays"
    id          = Column(Integer, primary_key=True, index=True)
    title       = Column(String(200), nullable=False)
    filename    = Column(String(300), nullable=False)
    file_url    = Column(String(500), nullable=False)
    uploaded_at = Column(DateTime, nullable=False)
    likes       = Column(Integer, default=0)
    like_records = relationship("Like", back_populates="replay", cascade="all, delete")


class Like(Base):
    __tablename__ = "likes"
    id         = Column(Integer, primary_key=True, index=True)
    replay_id  = Column(Integer, ForeignKey("replays.id"), nullable=False)
    created_at = Column(DateTime, nullable=False)
    replay = relationship("Replay", back_populates="like_records")


class Tournament(Base):
    __tablename__ = "tournaments"
    id               = Column(Integer, primary_key=True, index=True)
    name             = Column(String(200), nullable=False)
    game             = Column(String(100), nullable=False)
    status           = Column(String(50), default="registration")
    max_participants = Column(Integer, default=16)
    created_at       = Column(DateTime, nullable=False)
    participants = relationship("Participant", back_populates="tournament", cascade="all, delete")
    matches      = relationship("Match", back_populates="tournament", cascade="all, delete")


class Participant(Base):
    __tablename__ = "participants"
    id            = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    nickname      = Column(String(100), nullable=False)
    registered_at = Column(DateTime, nullable=False)
    tournament = relationship("Tournament", back_populates="participants")


class Match(Base):
    __tablename__ = "matches"
    id              = Column(Integer, primary_key=True, index=True)
    tournament_id   = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    round_number    = Column(Integer, nullable=False)
    match_number    = Column(Integer, nullable=False)
    participant1_id = Column(Integer, ForeignKey("participants.id"), nullable=True)
    participant2_id = Column(Integer, ForeignKey("participants.id"), nullable=True)
    winner_id       = Column(Integer, ForeignKey("participants.id"), nullable=True)
    status          = Column(String(50), default="pending")
    tournament = relationship("Tournament", back_populates="matches")


class TeammateProfile(Base):
    __tablename__ = "teammate_profiles"
    id           = Column(Integer, primary_key=True, index=True)
    nickname     = Column(String(100), nullable=False)
    game         = Column(String(100), nullable=False)
    rank         = Column(String(100), nullable=True)
    description  = Column(Text, nullable=True)
    created_at   = Column(DateTime, nullable=False)
    steam_id     = Column(String(50), nullable=True)


class SteamUser(Base):
    __tablename__ = "steam_users"
    id          = Column(Integer, primary_key=True, index=True)
    steam_id    = Column(String(50), unique=True, nullable=False, index=True)
    nickname    = Column(String(100), nullable=False)
    avatar      = Column(String(500), nullable=True)
    profile_url = Column(String(500), nullable=True)
    created_at  = Column(DateTime, nullable=False)
    
class CommunityPost(Base):
    __tablename__ = "community_posts"
    id         = Column(Integer, primary_key=True, index=True)
    game       = Column(String(20), nullable=False)
    title      = Column(String(200), nullable=False)
    text       = Column(Text, nullable=False)
    img        = Column(String(500), nullable=True)
    author     = Column(String(50), default="Аноним")
    tag        = Column(String(50), default="Новость")
    created_at = Column(DateTime, nullable=False)