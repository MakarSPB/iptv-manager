from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from typing import Optional

from config import settings
from database import SessionLocal, User

# Настройка
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBasic()

# JWT
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 неделя


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if plain_password is None or hashed_password is None:
        return False
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    if password is None:
        raise ValueError("Пароль не может быть None")
    return pwd_context.hash(password[:72])  # Обрезаем до 72 байт


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def authenticate_admin(username: str, password: str) -> bool:
    if not username or not password:
        return False
    if username == settings.admin_username and password == settings.admin_password:
        return True
    return False


def init_admin_user():
    db = SessionLocal()
    try:
        print("🔧 Запуск инициализации администратора...")

        # Проверка настроек
        print(f"  ➤ ADMIN_USERNAME: {settings.admin_username}")
        print(f"  ➤ ADMIN_PASSWORD длина: {len(settings.admin_password)}")
        print(f"  ➤ ADMIN_PASSWORD repr: {repr(settings.admin_password)}")

        # Проверка, существует ли уже админ
        admin = db.query(User).filter(User.username == settings.admin_username).first()
        if admin:
            print(f"✅ Администратор '{settings.admin_username}' уже существует.")
            return

        print("🔐 Администратор не найден — создаём нового...")

        # Обрезаем пароль до 72 символов (ограничение bcrypt)
        safe_password = settings.admin_password[:72]
        print(f"  ➤ Используем пароль (72 символа): {repr(safe_password)}")

        # Хешируем
        hashed_password = get_password_hash(safe_password)
        if not hashed_password:
            print("❌ Ошибка: не удалось хэшировать пароль!")
            return

        print(f"  ➤ Хэш пароля успешно создан: {hashed_password[:30]}...")

        # Создаём пользователя
        admin = User(
            username=settings.admin_username,
            password=hashed_password,
            is_admin=True
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        print(f"✅ Администратор '{admin.username}' успешно создан в БД!")
    except Exception as e:
        print(f"❌ Ошибка при создании администратора: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()