# Файл: main.py
# Главный файл FastAPI-приложения — точка входа для uvicorn

import os
import uuid
import json
import random
import httpx
from datetime import datetime, timezone
from typing import Optional, List
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import (
    FastAPI, Request, Depends, HTTPException,
    File, UploadFile, Form, WebSocket, WebSocketDisconnect
)
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# Подключаем наши модули
from database import engine, Base, get_db
import models
import schemas

# ────────────────────────────────────────────────
# Конфигурация из переменных окружения (.env)
# ────────────────────────────────────────────────
SECRET_KEY  = os.getenv("SECRET_KEY",  "super-secret-key-change-me")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "admin-token-change-me")

# Папки для хранения загруженных видео
UPLOAD_DIR = Path("static/uploads/videos")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ────────────────────────────────────────────────
# Lifespan: создаём таблицы БД при старте
# ────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)   # создаёт таблицы если их нет
    yield                                    # здесь работает приложение

app = FastAPI(title="GamePortal", lifespan=lifespan)

# Подключаем папку static/ для отдачи CSS/JS/видео
app.mount("/static", StaticFiles(directory="static"), name="static")

# Jinja2 шаблоны из папки templates/
templates = Jinja2Templates(directory="templates")

# ────────────────────────────────────────────────
# WebSocket-менеджер для мини-чата
# ────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        """Рассылаем сообщение всем подключённым клиентам"""
        dead = []
        for conn in self.active_connections:
            try:
                await conn.send_text(message)
            except Exception:
                dead.append(conn)
        for d in dead:
            self.disconnect(d)

manager = ConnectionManager()

# ────────────────────────────────────────────────
# Простой счётчик онлайна (по сессиям + времени)
# ────────────────────────────────────────────────
online_sessions: dict = {}   # session_id -> datetime последнего запроса

def get_session_id(request: Request) -> str:
    return request.cookies.get("session_id", str(uuid.uuid4()))

def update_online(session_id: str):
    online_sessions[session_id] = datetime.now(timezone.utc)

def count_online() -> int:
    """Считаем активных за последние 5 минут"""
    now = datetime.now(timezone.utc)
    return sum(
        1 for t in online_sessions.values()
        if (now - t).total_seconds() < 300
    )

# ────────────────────────────────────────────────
# Хелпер: проверка ADMIN_TOKEN
# ────────────────────────────────────────────────
def require_admin(token: str):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden: invalid admin token")


# ════════════════════════════════════════════════
#  HTML СТРАНИЦЫ
# ════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Главная страница"""
    sid = get_session_id(request)
    update_online(sid)
    resp = templates.TemplateResponse("index.html", {
        "request": request, "online": count_online()
    })
    resp.set_cookie("session_id", sid, max_age=86400)
    return resp


@app.get("/replays", response_class=HTMLResponse)
async def replays_page(request: Request, db: Session = Depends(get_db)):
    """Список всех реплеев"""
    sid = get_session_id(request)
    update_online(sid)
    replays = db.query(models.Replay).order_by(models.Replay.uploaded_at.desc()).all()
    resp = templates.TemplateResponse("replays.html", {
        "request": request, "replays": replays, "online": count_online()
    })
    resp.set_cookie("session_id", sid, max_age=86400)
    return resp


@app.get("/replay/{replay_id}", response_class=HTMLResponse)
async def replay_detail(replay_id: int, request: Request, db: Session = Depends(get_db)):
    """Страница просмотра реплея"""
    replay = db.query(models.Replay).filter(models.Replay.id == replay_id).first()
    if not replay:
        raise HTTPException(status_code=404, detail="Replay not found")
    likes = db.query(models.Like).filter(models.Like.replay_id == replay_id).count()
    return templates.TemplateResponse("replay_detail.html", {
        "request": request, "replay": replay, "likes": likes, "online": count_online()
    })


@app.get("/tournaments", response_class=HTMLResponse)
async def tournaments_page(request: Request, db: Session = Depends(get_db)):
    """Список турниров"""
    tournaments = db.query(models.Tournament).order_by(models.Tournament.created_at.desc()).all()
    return templates.TemplateResponse("tournaments.html", {
        "request": request, "tournaments": tournaments, "online": count_online()
    })


@app.get("/tournaments/{tournament_id}", response_class=HTMLResponse)
async def tournament_detail(tournament_id: int, request: Request, db: Session = Depends(get_db)):
    """Страница турнира с сеткой"""
    t = db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")
    participants = db.query(models.Participant).filter(
        models.Participant.tournament_id == tournament_id).all()
    matches = db.query(models.Match).filter(
        models.Match.tournament_id == tournament_id
    ).order_by(models.Match.round_number, models.Match.match_number).all()
    return templates.TemplateResponse("tournament_detail.html", {
        "request": request, "tournament": t,
        "participants": participants, "matches": matches, "online": count_online()
    })


@app.get("/find-teammates", response_class=HTMLResponse)
async def find_teammates_page(
    request: Request,
    game: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Страница поиска тиммейтов с фильтром по игре"""
    query = db.query(models.TeammateProfile)
    if game:
        query = query.filter(models.TeammateProfile.game.ilike(f"%{game}%"))
    profiles = query.order_by(models.TeammateProfile.created_at.desc()).all()
    return templates.TemplateResponse("find_teammates.html", {
        "request": request, "profiles": profiles,
        "filter_game": game or "", "online": count_online()
    })


# ════════════════════════════════════════════════
#  API: РЕПЛЕИ
# ════════════════════════════════════════════════

@app.post("/upload-replay", response_model=schemas.ReplayOut)
async def upload_replay(
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """POST /upload-replay — загрузить видео-реплей"""
    # Проверяем расширение файла
    allowed = {".mp4", ".webm"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Только .mp4 и .webm файлы")

    # Уникальное имя файла на диске
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = UPLOAD_DIR / filename

    # Читаем и сохраняем файл
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Создаём запись в БД
    replay = models.Replay(
        title=title,
        filename=filename,
        file_url=f"/static/uploads/videos/{filename}",
        uploaded_at=datetime.now(timezone.utc),
        likes=0,
    )
    db.add(replay)
    db.commit()
    db.refresh(replay)
    return replay


@app.get("/replays-api", response_model=List[schemas.ReplayOut])
async def list_replays(db: Session = Depends(get_db)):
    """GET /replays-api — список всех реплеев (JSON)"""
    return db.query(models.Replay).order_by(models.Replay.uploaded_at.desc()).all()


@app.post("/replays/{replay_id}/like")
async def like_replay(replay_id: int, db: Session = Depends(get_db)):
    """Поставить лайк реплею"""
    replay = db.query(models.Replay).filter(models.Replay.id == replay_id).first()
    if not replay:
        raise HTTPException(status_code=404, detail="Replay not found")
    like = models.Like(replay_id=replay_id, created_at=datetime.now(timezone.utc))
    db.add(like)
    replay.likes = (replay.likes or 0) + 1
    db.commit()
    return {"likes": replay.likes}


# ════════════════════════════════════════════════
#  API: ТУРНИРЫ
# ════════════════════════════════════════════════

@app.post("/tournaments", response_model=schemas.TournamentOut)
async def create_tournament(data: schemas.TournamentCreate, db: Session = Depends(get_db)):
    """POST /tournaments — создать турнир (нужен admin_token)"""
    require_admin(data.admin_token)
    t = models.Tournament(
        name=data.name,
        game=data.game,
        status="registration",
        max_participants=data.max_participants,
        created_at=datetime.now(timezone.utc),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@app.post("/tournaments/{tournament_id}/register", response_model=schemas.ParticipantOut)
async def register_participant(
    tournament_id: int,
    data: schemas.ParticipantCreate,
    db: Session = Depends(get_db)
):
    """POST /tournaments/{id}/register — зарегистрироваться участником"""
    t = db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")
    if t.status != "registration":
        raise HTTPException(status_code=400, detail="Регистрация закрыта")

    # Проверка дублей
    if db.query(models.Participant).filter(
        models.Participant.tournament_id == tournament_id,
        models.Participant.nickname == data.nickname
    ).first():
        raise HTTPException(status_code=409, detail="Ник уже занят")

    p = models.Participant(
        tournament_id=tournament_id,
        nickname=data.nickname,
        registered_at=datetime.now(timezone.utc),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@app.post("/tournaments/{tournament_id}/start")
async def start_tournament(
    tournament_id: int,
    data: schemas.AdminAction,
    db: Session = Depends(get_db)
):
    """Запустить турнир и сгенерировать сетку single elimination"""
    require_admin(data.admin_token)
    t = db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")

    participants = db.query(models.Participant).filter(
        models.Participant.tournament_id == tournament_id).all()
    if len(participants) < 2:
        raise HTTPException(status_code=400, detail="Нужно минимум 2 участника")

    # Перемешиваем участников и создаём пары
    shuffled = participants.copy()
    random.shuffle(shuffled)

    match_num = 1
    for i in range(0, len(shuffled), 2):
        p1 = shuffled[i]
        p2 = shuffled[i + 1] if i + 1 < len(shuffled) else None
        match = models.Match(
            tournament_id=tournament_id,
            round_number=1,
            match_number=match_num,
            participant1_id=p1.id,
            participant2_id=p2.id if p2 else None,
            status="pending" if p2 else "bye",  # bye = автопроход
            winner_id=p1.id if not p2 else None,  # если нет пары — автопобеда
        )
        db.add(match)
        match_num += 1

    t.status = "ongoing"
    db.commit()
    return {"status": "started", "matches_created": match_num - 1}


@app.get("/tournaments/{tournament_id}/bracket")
async def get_bracket(tournament_id: int, db: Session = Depends(get_db)):
    """GET /tournaments/{id}/bracket — данные сетки (для ботов и фронта)"""
    t = db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")

    participants = db.query(models.Participant).filter(
        models.Participant.tournament_id == tournament_id).all()
    matches = db.query(models.Match).filter(
        models.Match.tournament_id == tournament_id
    ).order_by(models.Match.round_number, models.Match.match_number).all()

    p_map = {p.id: p.nickname for p in participants}  # id -> nickname

    bracket = []
    for m in matches:
        bracket.append({
            "id": m.id,
            "round": m.round_number,
            "match": m.match_number,
            "participant1": p_map.get(m.participant1_id, "BYE"),
            "participant2": p_map.get(m.participant2_id, "BYE") if m.participant2_id else "BYE",
            "winner": p_map.get(m.winner_id) if m.winner_id else None,
            "status": m.status,
        })

    return {
        "tournament": {"id": t.id, "name": t.name, "game": t.game, "status": t.status},
        "participants": [{"id": p.id, "nickname": p.nickname} for p in participants],
        "bracket": bracket,
    }


@app.post("/tournaments/{tournament_id}/matches/{match_id}/result")
async def set_match_result(
    tournament_id: int,
    match_id: int,
    data: schemas.MatchResult,
    db: Session = Depends(get_db)
):
    """Записать результат матча (для ботов / администратора)"""
    require_admin(data.admin_token)
    match = db.query(models.Match).filter(
        models.Match.id == match_id,
        models.Match.tournament_id == tournament_id
    ).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if data.winner_id not in [match.participant1_id, match.participant2_id]:
        raise HTTPException(status_code=400, detail="Победитель должен быть участником матча")

    match.winner_id = data.winner_id
    match.status = "completed"
    db.commit()
    return {"status": "ok", "winner_id": data.winner_id}


# ════════════════════════════════════════════════
#  API: ТИММЕЙТЫ
# ════════════════════════════════════════════════

@app.post("/teammates", response_model=schemas.TeammateOut)
async def create_teammate(data: schemas.TeammateCreate, db: Session = Depends(get_db)):
    """Создать анкету тиммейта"""
    profile = models.TeammateProfile(
        nickname=data.nickname,
        game=data.game,
        rank=data.rank,
        description=data.description,
        created_at=datetime.now(timezone.utc),
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@app.get("/teammates-api", response_model=List[schemas.TeammateOut])
async def list_teammates(game: Optional[str] = None, db: Session = Depends(get_db)):
    """Список анкет (JSON) с опциональным фильтром"""
    query = db.query(models.TeammateProfile)
    if game:
        query = query.filter(models.TeammateProfile.game.ilike(f"%{game}%"))
    return query.order_by(models.TeammateProfile.created_at.desc()).all()


# ════════════════════════════════════════════════
#  WebSocket: МИ НИ-ЧАТ
# ════════════════════════════════════════════════

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket эндпоинт мини-чата"""
    await manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                nickname = str(data.get("nickname", "Аноним"))[:30]
                text = str(data.get("text", ""))[:500]
                if text.strip():
                    msg = json.dumps({
                        "nickname": nickname,
                        "text": text,
                        "time": datetime.now(timezone.utc).strftime("%H:%M"),
                    }, ensure_ascii=False)
                    await manager.broadcast(msg)
            except (json.JSONDecodeError, AttributeError):
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ════════════════════════════════════════════════
#  API: ОНЛАЙН
# ════════════════════════════════════════════════

@app.get("/api/online")
async def get_online(request: Request):
    """Вернуть текущее количество онлайн пользователей"""
    sid = get_session_id(request)
    update_online(sid)
    return {"online": count_online()}

# ════════════════════════════════════════════════
#  STEAM АВТОРИЗАЦИЯ
# ════════════════════════════════════════════════

from auth_steam import get_steam_login_url, verify_steam_login, get_steam_user
from fastapi.responses import RedirectResponse

@app.get("/auth/steam")
async def steam_login(request: Request):
    """Редирект на страницу входа Steam"""
    return_url = str(request.base_url) + "auth/steam/callback"
    login_url = get_steam_login_url(return_url)
    return RedirectResponse(login_url)


@app.get("/auth/steam/callback")
async def steam_callback(request: Request, db: Session = Depends(get_db)):
    """Обработка ответа от Steam"""
    params = dict(request.query_params)
    steam_id = await verify_steam_login(params)

    if not steam_id:
        return RedirectResponse("/?error=steam_auth_failed")

    # Получаем данные пользователя из Steam API
    user_data = await get_steam_user(steam_id)
    if not user_data:
        return RedirectResponse("/?error=steam_user_not_found")

    # Сохраняем или обновляем пользователя в БД
    user = db.query(models.SteamUser).filter(
        models.SteamUser.steam_id == steam_id
    ).first()

    if not user:
        user = models.SteamUser(
            steam_id=steam_id,
            nickname=user_data["nickname"],
            avatar=user_data["avatar"],
            profile_url=user_data["profile_url"],
            created_at=datetime.now(timezone.utc),
        )
        db.add(user)
    else:
        user.nickname = user_data["nickname"]
        user.avatar   = user_data["avatar"]

    db.commit()

    # Сохраняем в сессии через cookie
    response = RedirectResponse("/")
    response.set_cookie("steam_id",       steam_id,              max_age=86400*30)
    response.set_cookie("steam_nickname", user_data["nickname"],  max_age=86400*30)
    response.set_cookie("steam_avatar",   user_data["avatar"],    max_age=86400*30)
    return response


@app.get("/auth/logout")
async def logout():
    """Выход из аккаунта"""
    response = RedirectResponse("/")
    response.delete_cookie("steam_id")
    response.delete_cookie("steam_nickname")
    response.delete_cookie("steam_avatar")
    return response


@app.get("/api/me")
async def get_me(request: Request):
    """Получить данные текущего пользователя"""
    steam_id = request.cookies.get("steam_id")
    if not steam_id:
        return {"logged_in": False}
    return {
        "logged_in": True,
        "steam_id":  steam_id,
        "nickname":  request.cookies.get("steam_nickname"),
        "avatar":    request.cookies.get("steam_avatar"),
    }


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    """Страница профиля игрока со статистикой Dota 2"""
    steam_id = request.cookies.get("steam_id")
    if not steam_id:
        return RedirectResponse("/")
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "online": count_online(),
    })
@app.get("/ai-coach", response_class=HTMLResponse)
async def ai_coach_page(request: Request):
    """Страница ИИ-тренера"""
    return templates.TemplateResponse("ai_coach.html", {
        "request": request,
        "online": count_online(),
    })
@app.post("/api/ai-analyze")
async def ai_analyze(request: Request):
    body = await request.json()
    prompt = body.get("prompt", "")
    api_key = os.getenv("GROQ_API_KEY", "")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1000
                },
                timeout=60.0
            )
        data = response.json()
        if "error" in data:
            return {"text": f"Ошибка: {data['error'].get('message', str(data['error']))}"}
        text = data["choices"][0]["message"]["content"]
        return {"text": text}
    except Exception as e:
        return {"text": f"Ошибка запроса: {str(e)}"}
    

   
    
