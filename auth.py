from passlib.context import CryptContext
from database import SessionLocal, User
from config import settings
from jose import jwt
from datetime import datetime, timedelta
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем контекст для хэширования паролей
# Используем argon2 как основную схему, bcrypt — резервная
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    if not plain_password or not hashed_password:
        return False
    try:
        # Argon2 не имеет жесткого ограничения в 72 байта, как bcrypt
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Ошибка проверки пароля: {e}")
        return False

def get_password_hash(password):
    if not password:
        return None
    try:
        # Используем argon2 для хэширования
        return pwd_context.hash(password)
    except Exception as e:
        logger.error(f"Ошибка хэширования пароля: {e}")
        raise

def authenticate_admin(username: str, password: str):
    return username == settings.ADMIN_USERNAME and password == settings.ADMIN_PASSWORD

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

def init_admin_user():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == settings.ADMIN_USERNAME).first()
        if not user:
            hashed_password = get_password_hash(settings.ADMIN_PASSWORD)
            if not hashed_password:
                logger.error("Не удалось хэшировать пароль администратора")
                return
            admin_user = User(
                username=settings.ADMIN_USERNAME,
                password=hashed_password,
                is_admin=1
            )
            db.add(admin_user)
            db.commit()
            logger.info(f"Администратор {settings.ADMIN_USERNAME} успешно создан")
    except Exception as e:
        logger.error(f"Ошибка при инициализации администратора: {e}")
        raise
    finally:
        db.close()