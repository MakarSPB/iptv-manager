import uvicorn
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request, Depends, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import os
import uuid
from datetime import timedelta
from jose import jwt
from passlib.context import CryptContext

from config import settings
from models import Channel
from utils.parser import parse_m3u
from utils.generator import generate_m3u
from database import SessionLocal, User, Playlist, get_db
from auth import authenticate_admin, create_access_token, init_admin_user, get_password_hash, verify_password
from utils.generate_id import generate_short_id

# Создаем контекст для хэширования паролей
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

app = FastAPI(title="IPTV Playlist Manager")

# Инициализация при старте
init_admin_user()

# Создаем необходимые директории
os.makedirs(settings.PLAYLISTS_DIR, exist_ok=True)

# Настройка шаблонов и статики
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# === JWT и авторизация ===
def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        return user
    except Exception:
        return None

# === Страницы ===
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
    # Проверяем администратора
    if authenticate_admin(username, password):
        user = db.query(User).filter(User.username == username).first()
        if not user:
            user = User(username=username, password="", is_admin=1)
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

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login")

    playlists = db.query(Playlist).filter(Playlist.owner_id == user.id).all()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": user,
            "playlists": playlists
        }
    )

@app.get("/playlists", response_class=HTMLResponse)
async def my_playlists(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login")

    playlists = db.query(Playlist).filter(Playlist.owner_id == user.id).all()
    return templates.TemplateResponse(
        "playlists.html",
        {
            "request": request,
            "user": user,
            "playlists": playlists
        }
    )

@app.get("/profile", response_class=HTMLResponse)
async def profile(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login")

    total_playlists = db.query(Playlist).filter(Playlist.owner_id == user.id).count()

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "user": user,
            "total_playlists": total_playlists
        }
    )

@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("upload.html", {"request": request})

# === Загрузка плейлиста ===
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

    return {"channels": channels}

@app.get("/playlists/{playlist_id}/edit")
async def edit_playlist(playlist_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id, Playlist.owner_id == user.id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Плейлист не найден")

    try:
        channels = parse_m3u(playlist.content)
        return {
            "id": playlist.id,
            "name": playlist.name,
            "filename": playlist.filename,
            "channels": channels
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка парсинга плейлиста: {str(e)}")

@app.put("/playlists/{playlist_id}")
async def update_playlist(
        playlist_id: str,
        data: dict,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user)
):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id, Playlist.owner_id == user.id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Плейлист не найден")

    name = data.get("name", "Без названия")
    channels = data.get("channels", [])

    m3u_content = generate_m3u(channels)

    playlist.name = name
    playlist.filename = f"{name}.m3u"
    playlist.content = m3u_content
    db.commit()

    return {"message": "Плейлист обновлён", "url": f"/playlists/{playlist_id}.m3u"}

@app.delete("/playlists/{playlist_id}")
async def delete_playlist(playlist_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id, Playlist.owner_id == user.id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Плейлист не найден")

    db.delete(playlist)
    db.commit()
    return {"message": "Плейлист удалён"}

@app.post("/parse-text", response_class=JSONResponse)
async def parse_text(data: dict):
    content = data.get("content", "")
    if not content.strip():
        raise HTTPException(status_code=400, detail="Пустой контент")
    try:
        channels = parse_m3u(content)
        return {"channels": channels}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка парсинга: {str(e)}")

@app.post("/save", response_class=JSONResponse)
async def save_playlist(
        data: dict,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user)
):
    name = data.get("name", "Без названия")
    channels = data.get("channels", [])

    playlist_id = generate_short_id(5)
    while db.query(Playlist).filter(Playlist.id == playlist_id).first():
        playlist_id = generate_short_id(5)

    m3u_content = generate_m3u(channels)

    playlist = Playlist(
        id=playlist_id,
        name=name,
        filename=f"{name}.m3u",
        content=m3u_content,
        owner_id=user.id
    )
    db.add(playlist)
    db.commit()

    url = f"/{playlist_id}.m3u"  # Изменили: теперь без /playlists/
    return {"message": "Сохранено", "url": url}

@app.get("/new", response_class=HTMLResponse)
async def new_playlist_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login")

    return templates.TemplateResponse(
        "edit.html",
        {
            "request": request,
            "user": user,
            "playlist": None,
            "channels": []
        }
    )

@app.get("/{playlist_id}.m3u")
async def serve_playlist_root(playlist_id: str, db: Session = Depends(get_db)):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Плейлист не найден")
    return HTMLResponse(content=playlist.content, media_type="audio/mpegurl")

@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    users = db.query(User).all()
    return templates.TemplateResponse(
        "users.html",
        {
            "request": request,
            "user": user,
            "users": users
        }
    )

@app.post("/users", response_class=JSONResponse)
async def create_user(
        username: str = Form(...),
        password: str = Form(...),
        is_admin: bool = Form(False),
        db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Пользователь уже существует")

    hashed_password = get_password_hash(password)
    new_user = User(
        username=username,
        password=hashed_password,
        is_admin=bool(is_admin)
    )
    db.add(new_user)
    db.commit()
    return {"message": "Пользователь создан", "id": new_user.id}

@app.delete("/users/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="Нельзя удалить администратора")
    db.delete(user)
    db.commit()
    return {"message": "Пользователь удалён"}


if __name__ == "__main__":
    print("=== Загруженные настройки ===")
    print(f"DEBUG: {settings.DEBUG}")
    print(f"APP_HOST: {settings.APP_HOST}")
    print(f"APP_PORT: {settings.APP_PORT}")
    print(f"ADMIN_USERNAME: {settings.ADMIN_USERNAME}")
    print(f"PLAYLISTS_DIR: {settings.PLAYLISTS_DIR}")
    print("==============================")

    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
        log_level="info"
    )