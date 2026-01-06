import os
import logging
from logging.handlers import RotatingFileHandler
from config import settings

# Создаем директорию для логов, если она не существует
os.makedirs(settings.LOG_DIR, exist_ok=True)

# Формат логов
log_format = '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
date_format = '%Y-%m-%d %H:%M:%S'

# Создаем базовый логгер приложения
logger = logging.getLogger('iptv_manager')
logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))

# Создаем обработчик для записи в файл с ротацией
file_handler = RotatingFileHandler(
    os.path.join(settings.LOG_DIR, 'application.log'),
    maxBytes=settings.LOG_FILE_MAX_SIZE,
    backupCount=settings.LOG_FILE_BACKUP_COUNT
)
file_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))

# Создаем форматтер и добавляем его к обработчику
formatter = logging.Formatter(log_format, datefmt=date_format)
file_handler.setFormatter(formatter)

# Добавляем обработчик к логгеру
logger.addHandler(file_handler)

# Добавляем обработчик для вывода в консоль при DEBUG
if settings.DEBUG:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

def get_logger(name: str) -> logging.Logger:
    """Возвращает логгер с указанным именем"""
    return logging.getLogger(f'iptv_manager.{name}')