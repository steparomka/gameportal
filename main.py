# Файл: main.py
import os
import uuid
import json
import random
import httpx
import time
import re as _re
import datetime
from datetime import datetime as dt, timezone
from typing import Optional, List
from pathlib import Path
from contextlib import asynccontextmanager
from urllib.parse import unquote

from fastapi import (
    FastAPI, Request, Depends, HTTPException,
    File, UploadFile, Form, WebSocket, WebSocketDisconnect
)
from fastapi.responses import HTMLResponse, Response as FastAPIResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import engine, Base, get_db
import models
import schemas
from auth_steam import get_steam_login_url, verify_steam_login, get_steam_user

SECRET_KEY  = os.getenv("SECRET_KEY",  "super-secret-key-change-me")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "admin-token-change-me")
PANDASCORE_TOKEN = os.getenv("PANDASCORE_TOKEN", "vxRoG5-UQ2bQrKyeCaTSPGLwfXtyuSn5tq0k92jRsoVVgBOHLgU")
PANDASCORE_BASE  = "https://api.pandascore.co"

UPLOAD_DIR = Path("static/uploads/videos")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE teammate_profiles ADD COLUMN steam_id VARCHAR(50)"))
            conn.commit()
    except Exception:
        pass
    yield

app = FastAPI(title="GamePortal", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ── WebSocket менеджер ──
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)
    def disconnect(self, ws: WebSocket):
        if ws in self.active_connections:
            self.active_connections.remove(ws)
    async def broadcast(self, msg: str):
        dead = []
        for c in self.active_connections:
            try: await c.send_text(msg)
            except: dead.append(c)
        for d in dead: self.disconnect(d)

manager = ConnectionManager()

# ── Кеш ──
_cache = {}
def cache_get(key):
    if key in _cache:
        data, exp = _cache[key]
        if time.time() < exp: return data
    return None
def cache_set(key, data, ttl=600):
    _cache[key] = (data, time.time() + ttl)

# ── Онлайн ──
online_sessions: dict = {}
def get_session_id(r: Request) -> str:
    return r.cookies.get("session_id", str(uuid.uuid4()))
def update_online(sid: str):
    online_sessions[sid] = dt.now(timezone.utc)
def count_online() -> int:
    now = dt.now(timezone.utc)
    return sum(1 for t in online_sessions.values() if (now - t).total_seconds() < 300)

def require_admin(token: str):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")

# ── PandaScore ──
async def pandascore_get(path: str, params: dict = None) -> list:
    cache_key = f"ps:{path}:{str(params)}"
    cached = cache_get(cache_key)
    if cached: return cached
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{PANDASCORE_BASE}{path}",
                params=params or {},
                headers={"Authorization": f"Bearer {PANDASCORE_TOKEN}"},
                timeout=10.0
            )
        data = resp.json()
        cache_set(cache_key, data, ttl=300)
        return data
    except:
        return []

# ════════════════════════════════════════════════
#  HTML СТРАНИЦЫ
# ════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    sid = get_session_id(request)
    update_online(sid)
    resp = templates.TemplateResponse("index.html", {"request": request, "online": count_online()})
    resp.set_cookie("session_id", sid, max_age=86400)
    return resp

@app.get("/replays", response_class=HTMLResponse)
async def replays_page(request: Request, db: Session = Depends(get_db)):
    sid = get_session_id(request)
    update_online(sid)
    replays = db.query(models.Replay).order_by(models.Replay.uploaded_at.desc()).all()
    resp = templates.TemplateResponse("replays.html", {"request": request, "replays": replays, "online": count_online()})
    resp.set_cookie("session_id", sid, max_age=86400)
    return resp

@app.get("/replay/{replay_id}", response_class=HTMLResponse)
async def replay_detail(replay_id: int, request: Request, db: Session = Depends(get_db)):
    replay = db.query(models.Replay).filter(models.Replay.id == replay_id).first()
    if not replay: raise HTTPException(status_code=404, detail="Replay not found")
    likes = db.query(models.Like).filter(models.Like.replay_id == replay_id).count()
    return templates.TemplateResponse("replay_detail.html", {"request": request, "replay": replay, "likes": likes, "online": count_online()})

@app.get("/tournaments", response_class=HTMLResponse)
async def tournaments_page(request: Request, db: Session = Depends(get_db)):
    tournaments = db.query(models.Tournament).order_by(models.Tournament.created_at.desc()).all()
    return templates.TemplateResponse("tournaments.html", {"request": request, "tournaments": tournaments, "online": count_online()})

@app.get("/tournaments/{tournament_id}", response_class=HTMLResponse)
async def tournament_detail(tournament_id: int, request: Request, db: Session = Depends(get_db)):
    t = db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
    if not t: raise HTTPException(status_code=404, detail="Tournament not found")
    participants = db.query(models.Participant).filter(models.Participant.tournament_id == tournament_id).all()
    matches = db.query(models.Match).filter(models.Match.tournament_id == tournament_id).order_by(models.Match.round_number, models.Match.match_number).all()
    return templates.TemplateResponse("tournament_detail.html", {"request": request, "tournament": t, "participants": participants, "matches": matches, "online": count_online()})

@app.get("/find-teammates", response_class=HTMLResponse)
async def find_teammates_page(request: Request, game: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.TeammateProfile)
    if game: query = query.filter(models.TeammateProfile.game.ilike(f"%{game}%"))
    profiles = query.order_by(models.TeammateProfile.created_at.desc()).all()
    return templates.TemplateResponse("find_teammates.html", {"request": request, "profiles": profiles, "filter_game": game or "", "online": count_online()})

@app.get("/meta", response_class=HTMLResponse)
async def meta_page(request: Request):
    sid = get_session_id(request)
    update_online(sid)
    resp = templates.TemplateResponse("meta.html", {"request": request, "online": count_online()})
    resp.set_cookie("session_id", sid, max_age=86400)
    return resp

@app.get("/esports", response_class=HTMLResponse)
async def esports_page(request: Request):
    sid = get_session_id(request)
    update_online(sid)
    resp = templates.TemplateResponse("esports.html", {"request": request, "online": count_online()})
    resp.set_cookie("session_id", sid, max_age=86400)
    return resp

@app.get("/cs2", response_class=HTMLResponse)
async def cs2_page(request: Request):
    sid = get_session_id(request)
    update_online(sid)
    resp = templates.TemplateResponse("cs2.html", {"request": request, "online": count_online()})
    resp.set_cookie("session_id", sid, max_age=86400)
    return resp

@app.get("/ai-coach", response_class=HTMLResponse)
async def ai_coach_page(request: Request):
    return templates.TemplateResponse("ai_coach.html", {"request": request, "online": count_online()})

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    target_steam_id = request.query_params.get("steam_id") or request.cookies.get("steam_id")
    if not target_steam_id: return RedirectResponse("/")
    return templates.TemplateResponse("profile.html", {"request": request, "online": count_online(), "target_steam_id": target_steam_id})

# ════════════════════════════════════════════════
#  API: РЕПЛЕИ
# ════════════════════════════════════════════════

@app.post("/upload-replay", response_model=schemas.ReplayOut)
async def upload_replay(title: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    allowed = {".mp4", ".webm"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed: raise HTTPException(status_code=400, detail="Только .mp4 и .webm файлы")
    filename = f"{uuid.uuid4().hex}{ext}"
    with open(UPLOAD_DIR / filename, "wb") as f:
        f.write(await file.read())
    replay = models.Replay(title=title, filename=filename, file_url=f"/static/uploads/videos/{filename}", uploaded_at=dt.now(timezone.utc), likes=0)
    db.add(replay); db.commit(); db.refresh(replay)
    return replay

@app.get("/replays-api", response_model=List[schemas.ReplayOut])
async def list_replays(db: Session = Depends(get_db)):
    return db.query(models.Replay).order_by(models.Replay.uploaded_at.desc()).all()

@app.post("/replays/{replay_id}/like")
async def like_replay(replay_id: int, db: Session = Depends(get_db)):
    replay = db.query(models.Replay).filter(models.Replay.id == replay_id).first()
    if not replay: raise HTTPException(status_code=404)
    db.add(models.Like(replay_id=replay_id, created_at=dt.now(timezone.utc)))
    replay.likes = (replay.likes or 0) + 1
    db.commit()
    return {"likes": replay.likes}

# ════════════════════════════════════════════════
#  API: ТУРНИРЫ (пользовательские)
# ════════════════════════════════════════════════

@app.post("/tournaments", response_model=schemas.TournamentOut)
async def create_tournament(data: schemas.TournamentCreate, db: Session = Depends(get_db)):
    require_admin(data.admin_token)
    t = models.Tournament(name=data.name, game=data.game, status="registration", max_participants=data.max_participants, created_at=dt.now(timezone.utc))
    db.add(t); db.commit(); db.refresh(t)
    return t

@app.post("/tournaments/{tournament_id}/register", response_model=schemas.ParticipantOut)
async def register_participant(tournament_id: int, data: schemas.ParticipantCreate, db: Session = Depends(get_db)):
    t = db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
    if not t: raise HTTPException(status_code=404)
    if t.status != "registration": raise HTTPException(status_code=400, detail="Регистрация закрыта")
    if db.query(models.Participant).filter(models.Participant.tournament_id == tournament_id, models.Participant.nickname == data.nickname).first():
        raise HTTPException(status_code=409, detail="Ник уже занят")
    p = models.Participant(tournament_id=tournament_id, nickname=data.nickname, registered_at=dt.now(timezone.utc))
    db.add(p); db.commit(); db.refresh(p)
    return p

@app.post("/tournaments/{tournament_id}/start")
async def start_tournament(tournament_id: int, data: schemas.AdminAction, db: Session = Depends(get_db)):
    require_admin(data.admin_token)
    t = db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
    if not t: raise HTTPException(status_code=404)
    participants = db.query(models.Participant).filter(models.Participant.tournament_id == tournament_id).all()
    if len(participants) < 2: raise HTTPException(status_code=400, detail="Нужно минимум 2 участника")
    shuffled = participants.copy(); random.shuffle(shuffled)
    match_num = 1
    for i in range(0, len(shuffled), 2):
        p1 = shuffled[i]; p2 = shuffled[i+1] if i+1 < len(shuffled) else None
        db.add(models.Match(tournament_id=tournament_id, round_number=1, match_number=match_num, participant1_id=p1.id, participant2_id=p2.id if p2 else None, status="pending" if p2 else "bye", winner_id=p1.id if not p2 else None))
        match_num += 1
    t.status = "ongoing"; db.commit()
    return {"status": "started", "matches_created": match_num - 1}

@app.get("/tournaments/{tournament_id}/bracket")
async def get_bracket(tournament_id: int, db: Session = Depends(get_db)):
    t = db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
    if not t: raise HTTPException(status_code=404)
    participants = db.query(models.Participant).filter(models.Participant.tournament_id == tournament_id).all()
    matches = db.query(models.Match).filter(models.Match.tournament_id == tournament_id).order_by(models.Match.round_number, models.Match.match_number).all()
    p_map = {p.id: p.nickname for p in participants}
    return {"tournament": {"id": t.id, "name": t.name, "game": t.game, "status": t.status}, "participants": [{"id": p.id, "nickname": p.nickname} for p in participants], "bracket": [{"id": m.id, "round": m.round_number, "match": m.match_number, "participant1": p_map.get(m.participant1_id, "BYE"), "participant2": p_map.get(m.participant2_id, "BYE") if m.participant2_id else "BYE", "winner": p_map.get(m.winner_id) if m.winner_id else None, "status": m.status} for m in matches]}

@app.post("/tournaments/{tournament_id}/matches/{match_id}/result")
async def set_match_result(tournament_id: int, match_id: int, data: schemas.MatchResult, db: Session = Depends(get_db)):
    require_admin(data.admin_token)
    match = db.query(models.Match).filter(models.Match.id == match_id, models.Match.tournament_id == tournament_id).first()
    if not match: raise HTTPException(status_code=404)
    if data.winner_id not in [match.participant1_id, match.participant2_id]: raise HTTPException(status_code=400)
    match.winner_id = data.winner_id; match.status = "completed"; db.commit()
    return {"status": "ok", "winner_id": data.winner_id}

# ════════════════════════════════════════════════
#  API: ТИММЕЙТЫ
# ════════════════════════════════════════════════

@app.post("/teammates", response_model=schemas.TeammateOut)
async def create_teammate(request: Request, data: schemas.TeammateCreate, db: Session = Depends(get_db)):
    profile = models.TeammateProfile(nickname=data.nickname, game=data.game, rank=data.rank, description=data.description, created_at=dt.now(timezone.utc), steam_id=request.cookies.get("steam_id"))
    db.add(profile); db.commit(); db.refresh(profile)
    return profile

@app.delete("/teammates/{profile_id}")
async def delete_teammate(profile_id: int, request: Request, db: Session = Depends(get_db)):
    steam_id = request.cookies.get("steam_id")
    if not steam_id: raise HTTPException(status_code=401)
    profile = db.query(models.TeammateProfile).filter(models.TeammateProfile.id == profile_id).first()
    if not profile: raise HTTPException(status_code=404)
    if profile.steam_id != steam_id: raise HTTPException(status_code=403)
    db.delete(profile); db.commit()
    return {"status": "deleted"}

@app.get("/teammates-api", response_model=List[schemas.TeammateOut])
async def list_teammates(db: Session = Depends(get_db)):
    return db.query(models.TeammateProfile).order_by(models.TeammateProfile.created_at.desc()).all()

# ════════════════════════════════════════════════
#  WebSocket чат
# ════════════════════════════════════════════════

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                nickname = str(data.get("nickname", "Аноним"))[:30]
                text = str(data.get("text", ""))[:500]
                if text.strip():
                    await manager.broadcast(json.dumps({"nickname": nickname, "text": text, "time": dt.now(timezone.utc).strftime("%H:%M")}, ensure_ascii=False))
            except: pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ════════════════════════════════════════════════
#  API: ОНЛАЙН
# ════════════════════════════════════════════════

@app.get("/api/online")
async def get_online(request: Request):
    sid = get_session_id(request)
    update_online(sid)
    return {"online": count_online()}

# ════════════════════════════════════════════════
#  API: КАРТИНКИ ПРОКСИ
# ════════════════════════════════════════════════

@app.get("/api/img")
async def image_proxy(url: str):
    url = unquote(url)
    allowed = ['preview.redd.it','i.redd.it','i.imgur.com','cdn.cloudflare.steamstatic.com','shared.akamai.steamstatic.com','cdn.akamai.steamstatic.com','steamstore-a.akamaihd.net','external-preview.redd.it','b.thumbs.redditmedia.com','a.thumbs.redditmedia.com','styles.redditmedia.com']
    domain = url.split('/')[2] if url.startswith('http') else ''
    if not any(domain.endswith(a) for a in allowed):
        return FastAPIResponse(status_code=403, content=b'Forbidden')
    cache_key = 'img:' + url[:200]
    cached = cache_get(cache_key)
    if cached:
        return FastAPIResponse(content=cached['data'], media_type=cached['ct'], headers={"Cache-Control": "public, max-age=1800"})
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.reddit.com/"}, timeout=8.0, follow_redirects=True)
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "image/jpeg")
            if 'image' in ct:
                cache_set(cache_key, {'data': resp.content, 'ct': ct}, ttl=1800)
                return FastAPIResponse(content=resp.content, media_type=ct, headers={"Cache-Control": "public, max-age=1800"})
    except: pass
    return FastAPIResponse(status_code=404, content=b'Not found')

# ════════════════════════════════════════════════
#  API: НОВОСТИ STEAM
# ════════════════════════════════════════════════

def _parse_steam_news(items, default_url):
    months_ru = ["","Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"]
    news = []
    for item in items:
        title = item.get("title", "")
        contents = item.get("contents", "")
        img = ""
        m = _re.search(r'\{STEAM_CLAN_IMAGE\}/(\S+?)(?:\s|$|\[)', contents)
        if m: img = "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/clans/" + m.group(1)
        if not img:
            m2 = _re.search(r'https://[^\s\]"]+\.(?:jpg|jpeg|png|gif|webp)', contents)
            if m2: img = m2.group(0)
        tl = title.lower()
        if any(w in tl for w in ["patch","7.","gameplay","update","balance"]): tag = "Патч"
        elif any(w in tl for w in ["tournament","international","major","dreamleague","esl","registration"]): tag = "Турнир"
        elif any(w in tl for w in ["plus","arcana","compendium","battle pass","cosmetic","spring","summer","winter","fall"]): tag = "Обновление"
        elif any(w in tl for w in ["guide","tips","hero"]): tag = "Гайд"
        elif any(w in tl for w in ["major"]): tag = "Major"
        elif any(w in tl for w in ["operation"]): tag = "Операция"
        else: tag = "Новость"
        d = datetime.datetime.fromtimestamp(item.get("date", 0))
        desc = _re.sub(r'\[/?[^\]]+\]', '', contents[:300]).strip()
        desc = _re.sub(r'\s+', ' ', desc)[:200]
        news.append({"title": title, "url": item.get("url", default_url), "date": f"{d.day} {months_ru[d.month]} {d.year}", "tag": tag, "img": img, "desc": desc})
    return news

@app.get("/api/dota-news")
async def get_dota_news():
    cached = cache_get("dota_news_v3")
    if cached: return cached
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/", params={"appid":"570","count":"8","maxlength":"600","format":"json","feeds":"steam_community_announcements"}, timeout=10.0)
        items = resp.json().get("appnews", {}).get("newsitems", [])
        result = {"news": _parse_steam_news(items, "https://www.dota2.com/news"), "source": "steam"}
        cache_set("dota_news_v3", result, ttl=3600)
        return result
    except Exception as e:
        return {"news": [], "source": "error", "error": str(e)}

@app.get("/api/cs2-news")
async def get_cs2_news():
    cached = cache_get("cs2_news_v3")
    if cached: return cached
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/", params={"appid":"730","count":"8","maxlength":"600","format":"json","feeds":"steam_community_announcements"}, timeout=10.0)
        items = resp.json().get("appnews", {}).get("newsitems", [])
        result = {"news": _parse_steam_news(items, "https://www.counter-strike.net/news"), "source": "steam"}
        cache_set("cs2_news_v3", result, ttl=3600)
        return result
    except Exception as e:
        return {"news": [], "source": "error", "error": str(e)}

# ════════════════════════════════════════════════
#  API: ПОСТЫ СООБЩЕСТВА
# ════════════════════════════════════════════════

@app.post("/api/posts")
async def create_post(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    title = str(body.get("title","")).strip()[:200]
    text  = str(body.get("text","")).strip()[:3000]
    game  = str(body.get("game","dota")).strip()
    img   = str(body.get("img","")).strip()[:500]
    author= str(body.get("author","Аноним")).strip()[:50]
    tag   = str(body.get("tag","Новость")).strip()[:50]
    if not title or not text: raise HTTPException(status_code=400, detail="Заголовок и текст обязательны")
    if game not in ("dota","cs2"): raise HTTPException(status_code=400, detail="Неверная игра")
    post = models.CommunityPost(game=game, title=title, text=text, img=img or None, author=author or "Аноним", tag=tag, created_at=dt.now(timezone.utc))
    db.add(post); db.commit(); db.refresh(post)
    return {"id": post.id, "status": "ok"}

@app.get("/api/posts")
async def get_posts(game: str = "dota", db: Session = Depends(get_db)):
    posts = db.query(models.CommunityPost).filter(models.CommunityPost.game == game).order_by(models.CommunityPost.created_at.desc()).limit(20).all()
    months_ru = ["","Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"]
    return [{"id": p.id, "title": p.title, "text": p.text, "img": p.img, "author": p.author, "tag": p.tag, "date": f"{p.created_at.day} {months_ru[p.created_at.month]} {p.created_at.year}", "game": p.game} for p in posts]

# ════════════════════════════════════════════════
#  API: PANDASCORE ESPORTS
# ════════════════════════════════════════════════

@app.get("/api/esports/dota/matches")
async def dota_matches():
    running  = await pandascore_get("/dota2/matches/running",  {"page[size]": 10})
    upcoming = await pandascore_get("/dota2/matches/upcoming", {"page[size]": 10, "sort": "begin_at"})
    def fmt(m):
        ops = m.get("opponents",[])
        t1 = ops[0].get("opponent",{}) if ops else {}
        t2 = ops[1].get("opponent",{}) if len(ops)>1 else {}
        res = m.get("results",[])
        return {"id":m.get("id"),"status":m.get("status"),"begin_at":m.get("begin_at"),"tournament_name":(m.get("tournament") or {}).get("name"),"team1":{"id":t1.get("id"),"name":t1.get("name"),"img":t1.get("image_url"),"acronym":t1.get("acronym")},"team2":{"id":t2.get("id"),"name":t2.get("name"),"img":t2.get("image_url"),"acronym":t2.get("acronym")},"score1":res[0].get("score") if res else None,"score2":res[1].get("score") if len(res)>1 else None,"winner_id":m.get("winner_id")}
    return {"running":[fmt(m) for m in (running if isinstance(running,list) else [])],"upcoming":[fmt(m) for m in (upcoming if isinstance(upcoming,list) else [])[:8]]}

@app.get("/api/esports/dota/tournaments")
async def dota_tournaments():
    running  = await pandascore_get("/dota2/tournaments/running",  {"page[size]": 10})
    upcoming = await pandascore_get("/dota2/tournaments/upcoming", {"page[size]": 5, "sort": "begin_at"})
    def fmt(t, status):
        return {"id":t.get("id"),"name":t.get("name"),"status":status,"begin_at":t.get("begin_at"),"end_at":t.get("end_at"),"prize_pool":t.get("prize_pool"),"tier":t.get("tier"),"league":(t.get("league") or {}).get("name"),"league_img":(t.get("league") or {}).get("image_url")}
    return {"running":[fmt(t,"live") for t in (running if isinstance(running,list) else [])],"upcoming":[fmt(t,"upcoming") for t in (upcoming if isinstance(upcoming,list) else [])]}

@app.get("/api/esports/cs2/matches")
async def cs2_matches():
    running  = await pandascore_get("/csgo/matches/running",  {"page[size]": 10})
    upcoming = await pandascore_get("/csgo/matches/upcoming", {"page[size]": 10, "sort": "begin_at"})
    def fmt(m):
        ops = m.get("opponents",[])
        t1 = ops[0].get("opponent",{}) if ops else {}
        t2 = ops[1].get("opponent",{}) if len(ops)>1 else {}
        res = m.get("results",[])
        return {"id":m.get("id"),"status":m.get("status"),"begin_at":m.get("begin_at"),"tournament_name":(m.get("tournament") or {}).get("name"),"team1":{"id":t1.get("id"),"name":t1.get("name"),"img":t1.get("image_url"),"acronym":t1.get("acronym")},"team2":{"id":t2.get("id"),"name":t2.get("name"),"img":t2.get("image_url"),"acronym":t2.get("acronym")},"score1":res[0].get("score") if res else None,"score2":res[1].get("score") if len(res)>1 else None,"winner_id":m.get("winner_id")}
    return {"running":[fmt(m) for m in (running if isinstance(running,list) else [])],"upcoming":[fmt(m) for m in (upcoming if isinstance(upcoming,list) else [])[:8]]}

@app.get("/api/esports/cs2/tournaments")
async def cs2_tournaments():
    running  = await pandascore_get("/csgo/tournaments/running",  {"page[size]": 10})
    upcoming = await pandascore_get("/csgo/tournaments/upcoming", {"page[size]": 5, "sort": "begin_at"})
    def fmt(t, status):
        return {"id":t.get("id"),"name":t.get("name"),"status":status,"begin_at":t.get("begin_at"),"end_at":t.get("end_at"),"prize_pool":t.get("prize_pool"),"tier":t.get("tier"),"league":(t.get("league") or {}).get("name"),"league_img":(t.get("league") or {}).get("image_url")}
    return {"running":[fmt(t,"live") for t in (running if isinstance(running,list) else [])],"upcoming":[fmt(t,"upcoming") for t in (upcoming if isinstance(upcoming,list) else [])]}

@app.get("/api/esports/tournament/{tournament_id}/matches")
async def tournament_matches(tournament_id: int, game: str = "dota2"):
    g = "csgo" if game == "cs2" else "dota2"
    matches = await pandascore_get(f"/{g}/tournaments/{tournament_id}/matches", {"page[size]": 50, "sort": "begin_at"})
    if not isinstance(matches, list): return []
    def fmt(m):
        ops = m.get("opponents",[])
        t1 = ops[0].get("opponent",{}) if ops else {}
        t2 = ops[1].get("opponent",{}) if len(ops)>1 else {}
        res = m.get("results",[])
        return {"id":m.get("id"),"status":m.get("status"),"begin_at":m.get("begin_at"),"stage_name":m.get("tournament_stage_name") or m.get("match_type","Матч").replace("_"," ").title(),"team1":{"id":t1.get("id"),"name":t1.get("name"),"acronym":t1.get("acronym"),"img":t1.get("image_url")},"team2":{"id":t2.get("id"),"name":t2.get("name"),"acronym":t2.get("acronym"),"img":t2.get("image_url")},"score1":res[0].get("score") if res else None,"score2":res[1].get("score") if len(res)>1 else None,"winner_id":m.get("winner_id")}
    return [fmt(m) for m in matches]

# ════════════════════════════════════════════════
#  STEAM АВТОРИЗАЦИЯ
# ════════════════════════════════════════════════

@app.get("/auth/steam")
async def steam_login(request: Request):
    return RedirectResponse(get_steam_login_url(str(request.base_url) + "auth/steam/callback"))

@app.get("/auth/steam/callback")
async def steam_callback(request: Request, db: Session = Depends(get_db)):
    steam_id = await verify_steam_login(dict(request.query_params))
    if not steam_id: return RedirectResponse("/?error=steam_auth_failed")
    user_data = await get_steam_user(steam_id)
    if not user_data: return RedirectResponse("/?error=steam_user_not_found")
    user = db.query(models.SteamUser).filter(models.SteamUser.steam_id == steam_id).first()
    if not user:
        user = models.SteamUser(steam_id=steam_id, nickname=user_data["nickname"], avatar=user_data["avatar"], profile_url=user_data["profile_url"], created_at=dt.now(timezone.utc))
        db.add(user)
    else:
        user.nickname = user_data["nickname"]; user.avatar = user_data["avatar"]
    db.commit()
    response = RedirectResponse("/")
    response.set_cookie("steam_id", steam_id, max_age=86400*30)
    response.set_cookie("steam_nickname", user_data["nickname"], max_age=86400*30)
    response.set_cookie("steam_avatar", user_data["avatar"], max_age=86400*30)
    return response

@app.get("/auth/logout")
async def logout():
    response = RedirectResponse("/")
    response.delete_cookie("steam_id"); response.delete_cookie("steam_nickname"); response.delete_cookie("steam_avatar")
    return response

@app.get("/api/me")
async def get_me(request: Request):
    steam_id = request.cookies.get("steam_id")
    if not steam_id: return {"logged_in": False}
    return {"logged_in": True, "steam_id": steam_id, "nickname": request.cookies.get("steam_nickname"), "avatar": request.cookies.get("steam_avatar")}

@app.get("/api/users/search")
async def search_users(q: str, db: Session = Depends(get_db)):
    if not q or len(q) < 2: return []
    users = db.query(models.SteamUser).filter(models.SteamUser.nickname.ilike(f"%{q}%")).limit(10).all()
    return [{"steam_id": u.steam_id, "nickname": u.nickname, "avatar": u.avatar} for u in users]

# ════════════════════════════════════════════════
#  API: OpenDota прокси
# ════════════════════════════════════════════════

@app.get("/api/opendota/{path:path}")
async def opendota_proxy(path: str, request: Request):
    cache_key = path + str(request.query_params)
    cached = cache_get(cache_key)
    if cached: return cached
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.opendota.com/api/{path}", params=dict(request.query_params), timeout=30.0)
    data = response.json()
    cache_set(cache_key, data)
    return data

# ════════════════════════════════════════════════
#  API: ИИ ТРЕНЕР
# ════════════════════════════════════════════════

@app.post("/api/ai-analyze")
async def ai_analyze(request: Request):
    body = await request.json()
    prompt = body.get("prompt", "")
    api_key = os.getenv("GROQ_API_KEY", "")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "max_tokens": 1000}, timeout=60.0)
        data = response.json()
        if "error" in data: return {"text": f"Ошибка: {data['error'].get('message', str(data['error']))}"}
        return {"text": data["choices"][0]["message"]["content"]}
    except Exception as e:
        return {"text": f"Ошибка запроса: {str(e)}"}