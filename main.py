import uvicorn
import random
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request, Depends, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import os
import uuid
from datetime import datetime, timedelta
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

captcha_store = {}

def generate_captcha():
    num1 = random.randint(1, 10)
    num2 = random.randint(1, 10)
    ops = ["+", "-"]
    op = random.choice(ops)
    if op == "+":
        result = num1 + num2
    else:
        result = abs(num1 - num2)
    question = f"{num1} {op} {num2} = ?"
    return question, result

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    question, answer = generate_captcha()
    # Сохраняем ответ в "сессии" (упрощённо)
    session_id = str(uuid.uuid4())  # Уникальный ID для каждого пользователя
    captcha_store[session_id] = answer
    return templates.TemplateResponse("register.html", {
        "request": request,
        "captcha_question": question,
        "session_id": session_id
    })

@app.post("/register")
async def register_user(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        email: str = Form(...),
        user_answer: str = Form(...),
        session_id: str = Form(...),
        db: Session = Depends(get_db)
):
    # Проверяем капчу
    correct_answer = captcha_store.get(session_id)
    if not correct_answer or str(correct_answer) != user_answer.strip():
        # Пересоздаём капчу при ошибке
        question, new_answer = generate_captcha()
        captcha_store[session_id] = new_answer
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Неверный ответ на капчу",
            "captcha_question": question,
            "session_id": session_id
        })

    # Проверка существования пользователя
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        question, new_answer = generate_captcha()
        captcha_store[session_id] = new_answer
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Пользователь уже существует",
            "captcha_question": question,
            "session_id": session_id
        })

    # Хэшируем пароль
    hashed_password = get_password_hash(password)

    # Создаём пользователя
    new_user = User(
        username=username,
        password=hashed_password,
        email=email,
        is_admin=0
    )
    db.add(new_user)
    db.commit()

    # Автоматически логиним
    token = create_access_token(data={"sub": username})
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(key="access_token", value=token, httponly=True)
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

    # Добавляем количество каналов
    playlists_with_info = []
    for pl in playlists:
        try:
            channels = parse_m3u(pl.content)
            channel_count = len(channels)
        except Exception:
            channel_count = 0
        playlists_with_info.append({
            "playlist": pl,
            "channel_count": channel_count
        })

    return templates.TemplateResponse(
        "playlists.html",
        {
            "request": request,
            "user": user,
            "playlists": playlists_with_info
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
        result = parse_m3u(playlist.content)
        return {
            "id": playlist.id,
            "name": playlist.name,
            "filename": playlist.filename,
            "channels": result['channels'],
            "tvg_url": result['tvg_url']
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

    m3u_content = generate_m3u(channels, tvg_url=data.get('tvg_url'))

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

    m3u_content = generate_m3u(channels, tvg_url=data.get('tvg_url'))

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


@app.get("/{path:path}")
async def catch_all(request: Request, path: str):
    # Список защищенных префиксов
    protected_prefixes = ["admin", "api", "users", "profile", "playlists"]
    
    # Проверяем, начинается ли путь с одного из защищенных префиксов
    # и не является ли он просто "shared"
    if any(path.startswith(prefix) for prefix in protected_prefixes) and path != "shared":
        return templates.TemplateResponse(
            "error.html", 
            {
                "request": request,
                "status_code": "403",
                "title": "Доступ запрещён",
                "message": "У вас нет прав для доступа к этой странице. Эта область защищена и доступна только авторизованным пользователям."
            }, 
            status_code=403
        )
    # Для всех остальных несуществующих путей - 404
    return templates.TemplateResponse(
        "error.html", 
        {
            "request": request,
            "status_code": "404",
            "title": "Страница не найдена",
            "message": "К сожалению, страница, которую вы ищете, не существует. Возможно, она была перемещена или удалена."
        }, 
        status_code=404
    )

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

@app.post("/users", response_class=HTMLResponse)
async def create_user(
        username: str = Form(...),
        password: str = Form(...),
        email: str = Form(...),
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
        email=email,
        is_admin=bool(is_admin)
    )
    db.add(new_user)
    db.commit()

    return RedirectResponse("/users?created=true", status_code=303)

@app.get("/users/{user_id}/edit")
async def get_user_for_edit(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user

@app.post("/users/{user_id}/edit")
async def update_user(
        user_id: int,
        username: str = Form(...),
        password: str = Form(None),  # Может быть None, если поле пустое
        email: str = Form(...),
        db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Проверяем, не существует ли другой пользователь с таким именем
    existing_user = db.query(User).filter(User.username == username, User.id != user_id).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Имя пользователя уже занято")

    # Обновляем данные
    user.username = username
    user.email = email
    if password:  # Если пароль указан, хэшируем и обновляем
        user.password = get_password_hash(password)
    
    db.commit()
    return {"message": "Пользователь успешно обновлён"}

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

@app.post("/users/{user_id}/admin")
async def toggle_admin_status(user_id: int, data: dict, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    # Получаем текущего пользователя из токена
    current_user = get_current_user(request, db)
    if not current_user or not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    # Нельзя лишить себя прав администратора
    if user.id == current_user.id and data.get("is_admin") is False:
        raise HTTPException(status_code=400, detail="Нельзя лишить себя прав администратора")
    user.is_admin = data.get("is_admin", False)
    db.commit()
    return {"message": "Статус администратора обновлён"}

@app.get("/shared", response_class=HTMLResponse)
async def shared_playlists_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login")

    # Получаем все плейлисты, отмеченные как общие
    shared_playlists = (
        db.query(Playlist, User.username.label("owner_username"))
        .join(User, Playlist.owner_id == User.id)
        .filter(Playlist.is_shared == True)
        .all()
    )

    # Добавляем количество каналов
    playlists_with_info = []
    for playlist, owner_username in shared_playlists:
        try:
            channels = parse_m3u(playlist.content)
            channel_count = len(channels)
        except:
            channel_count = 0
        playlists_with_info.append({
            "playlist": playlist,
            "owner_username": owner_username,
            "channel_count": channel_count
        })

    return templates.TemplateResponse(
        "shared.html",
        {
            "request": request,
            "user": user,
            "playlists": playlists_with_info
        }
    )
@app.post("/playlists/{playlist_id}/share")
async def toggle_shared_status(
        playlist_id: str,
        data: dict,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user)
):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id, Playlist.owner_id == user.id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Плейлист не найден")

    playlist.is_shared = data.get("is_shared", False)
    db.commit()

    return {"message": "Статус общего доступа обновлён"}

if __name__ == "__main__":
    # Обработчики ошибок
    @app.exception_handler(400)
    async def bad_request_handler(request: Request, exc):
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "status_code": "400",
                "title": "Некорректный запрос",
                "message": "Запрос содержит ошибки. Проверьте введённые данные и попробуйте снова."
            },
            status_code=400
        )

    @app.exception_handler(401)
    async def unauthorized_handler(request: Request, exc):
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "status_code": "401",
                "title": "Требуется авторизация",
                "message": "Для доступа к этой странице необходимо войти в систему."
            },
            status_code=401
        )

    @app.exception_handler(405)
    async def method_not_allowed_handler(request: Request, exc):
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "status_code": "405",
                "title": "Метод не поддерживается",
                "message": "Метод запроса не поддерживается для этого ресурса."
            },
            status_code=405
        )

    @app.exception_handler(413)
    async def payload_too_large_handler(request: Request, exc):
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "status_code": "413",
                "title": "Файл слишком большой",
                "message": "Размер файла превышает допустимый лимит. Загрузите файл меньшего размера или разделите плейлист на части."
            },
            status_code=413
        )

    @app.exception_handler(429)
    async def too_many_requests_handler(request: Request, exc):
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "status_code": "429",
                "title": "Слишком много запросов",
                "message": "Слишком много запросов. Попробуйте через несколько минут."
            },
            status_code=429
        )

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc):
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "status_code": "500",
                "title": "Внутренняя ошибка",
                "message": "Произошла внутренняя ошибка сервера. Администратор уже уведомлен. Попробуйте обновить страницу или вернуться позже."
            },
            status_code=500
        )

    @app.exception_handler(503)
    async def service_unavailable_handler(request: Request, exc):
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "status_code": "503",
                "title": "Сервис недоступен",
                "message": "Сервис временно недоступен. Ведутся технические работы. Попробуйте позже."
            },
            status_code=503
        )

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