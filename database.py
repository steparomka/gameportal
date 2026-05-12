# Файл: database.py
# Настройка подключения к SQLite через SQLAlchemy

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# URL базы данных SQLite (файл game_portal.db в корне проекта)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./game_portal.db")

# create_engine — создаёт движок БД
# check_same_thread=False нужно для SQLite + FastAPI (многопоточность)
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# SessionLocal — фабрика сессий БД
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base — базовый класс для всех моделей SQLAlchemy
Base = declarative_base()


def get_db():
    """
    Dependency для FastAPI: открывает сессию БД,
    передаёт её в эндпоинт и закрывает после завершения запроса.
    Использование: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
