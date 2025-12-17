from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os
import uuid
from typing import List
import uvicorn

from config import settings
from models import Channel
from utils.parser import parse_m3u
from utils.generator import generate_m3u

app = FastAPI(title="IPTV Playlist Manager")

# Создаем папку для плейлистов
os.makedirs(settings.playlists_dir, exist_ok=True)

# Подключаем шаблоны и статику
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Хранилище плейлистов в памяти (можно заменить на БД)
playlists_db = {}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/upload", response_class=JSONResponse)
async def upload_playlist(file: UploadFile = File(...)):
    if not file.filename.endswith((".m3u", ".m3u8")):
        raise HTTPException(status_code=400, detail="Файл должен быть .m3u или .m3u8")

    content = await file.read()
    try:
        channels = parse_m3u(content.decode("utf-8", errors="ignore"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка парсинга: {str(e)}")

    playlist_id = str(uuid.uuid4())
    playlists_db[playlist_id] = {
        "filename": file.filename,
        "channels": [ch.model_dump() for ch in channels]
    }

    return {"playlist_id": playlist_id, "channels": channels}


@app.post("/save/{playlist_id}", response_class=JSONResponse)
async def save_playlist(playlist_id: str, updated_channels: List[Channel]):
    if playlist_id not in playlists_db:
        raise HTTPException(status_code=404, detail="Плейлист не найден")

    playlists_db[playlist_id]["channels"] = [ch.model_dump() for ch in updated_channels]

    # Генерируем обновлённый M3U
    m3u_content = generate_m3u(updated_channels)

    # Сохраняем файл
    file_path = os.path.join(settings.playlists_dir, f"{playlist_id}.m3u")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(m3u_content)

    # Формируем публичную ссылку
    playlist_url = f"/playlists/{playlist_id}.m3u"

    return {"message": "Сохранено", "url": playlist_url}


@app.get("/playlists/{playlist_id}.m3u")
async def serve_playlist(playlist_id: str):
    file_path = os.path.join(settings.playlists_dir, f"{playlist_id}.m3u")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Плейлист не найден")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    return HTMLResponse(content=content, media_type="audio/mpegurl")


# === Запуск сервера ===
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
        log_level="info"
    )