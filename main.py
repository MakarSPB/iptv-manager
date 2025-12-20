from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request, Depends, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import os
import uuid
import jwt
from datetime import timedelta
from typing import List

from config import settings
from models import Channel
from utils.parser import parse_m3u
from utils.generator import generate_m3u
from database import SessionLocal, User, Playlist
from auth import authenticate_admin, create_access_token, get_db, init_admin_user

app = FastAPI(title="IPTV Playlist Manager")

# Инициализируем админа при старте
init_admin_user()

# Создаём директорию
os.makedirs(settings.playlists_dir, exist_ok=True)

# Шаблоны
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# === JWT utility ===
def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            return None
        user = db.query(User).filter(User.username == username).first()
        return user
    except:
        return None


# === Страница входа ===
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse("/")
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(
        response: Response,
        username: str = Form(...),
        password: str = Form(...),
        db: Session = Depends(get_db)
):
    # Проверяем админа
    if authenticate_admin(username, password):
        user = db.query(User).filter(User.username == username).first()
        if not user:
            user = User(
                username=username,
                password="",
                is_admin=True
            )
            db.add(user)
            db.commit()
    else:
        # Проверяем обычного пользователя
        user = db.query(User).filter(User.username == username).first()
        if not user or not pwd_context.verify(password, user.password):
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "Неверный логин или пароль"}
            )

    token = create_access_token(data={"sub": user.username})
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(key="access_token", value=token, httponly=True)
    return resp


@app.get("/logout")
async def logout():
    resp = RedirectResponse("/login")
    resp.delete_cookie("access_token")
    return resp


# === Главная страница ===
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


# === Остальные эндпоинты остаются, но добавим защиту и БД ===
@app.post("/upload", response_class=JSONResponse)
async def upload_playlist(
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user)
):
    if not file.filename.endswith((".m3u", ".m3u8")):
        raise HTTPException(status_code=400, detail="Файл должен быть .m3u или .m3u8")

    content = await file.read()
    try:
        channels = parse_m3u(content.decode("utf-8", errors="ignore"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка парсинга: {str(e)}")

    playlist_id = str(uuid.uuid4())
    playlist = Playlist(
        id=playlist_id,
        filename=file.filename,
        content=content.decode("utf-8"),
        owner_id=user.id
    )
    db.add(playlist)
    db.commit()

    return {"playlist_id": playlist_id, "channels": channels}


@app.get("/playlists/{playlist_id}.m3u")
async def serve_playlist(playlist_id: str, db: Session = Depends(get_db)):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Плейлист не найден")

    channels = parse_m3u(playlist.content)
    m3u_content = generate_m3u(channels)
    return HTMLResponse(content=m3u_content, media_type="audio/mpegurl")


# === Запуск сервера ===
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
        log_level="info"
    )