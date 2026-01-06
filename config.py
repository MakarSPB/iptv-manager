import os
from dotenv import load_dotenv

# Загружаем .env (даже если Docker передает переменные — безопасно)
load_dotenv()

class Settings:
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", 8000))
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-super-secret-jwt-key-change-in-production")
    PLAYLISTS_DIR: str = os.getenv("PLAYLISTS_DIR", "uploads")
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin")
    LOG_DIR: str = os.getenv("LOG_DIR", "data/logs")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE_MAX_SIZE_MB: int = int(os.getenv("LOG_FILE_MAX_SIZE_MB", "10"))
    LOG_FILE_MAX_SIZE: int = LOG_FILE_MAX_SIZE_MB * 1024 * 1024  # Конвертация MB в байты
    LOG_FILE_BACKUP_COUNT: int = int(os.getenv("LOG_FILE_BACKUP_COUNT", "5"))

settings = Settings()