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
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    if not plain_password or not hashed_password:
        return False
    try:
        # Усекаем пароль до 72 байт, как требует bcrypt
        plain_password = plain_password[:72]
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Ошибка проверки пароля: {e}")
        return False

def get_password_hash(password):
    if not password:
        return None
    try:
        # Усекаем пароль до 72 байт перед хэшированием
        password = password[:72]
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
            # Усекаем пароль админа до 72 символов
            admin_password = settings.ADMIN_PASSWORD[:72]
            hashed_password = get_password_hash(admin_password)
            admin_user = User(
                username=settings.ADMIN_USERNAME,
                password=hashed_password,
                is_admin=1
            )
            db.add(admin_user)
            db.commit()
            logger.info(f"Администратор {settings.ADMIN_USERNAME} создан")
    except Exception as e:
        logger.error(f"Ошибка создания администратора: {e}")
        raise
    finally:
        db.close()