from passlib.context import CryptContext
from database import SessionLocal, User
from config import settings
from jose import jwt
from datetime import datetime, timedelta

# Создаем контекст для хэширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

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
            admin_user = User(username=settings.ADMIN_USERNAME, password=hashed_password, is_admin=True)
            db.add(admin_user)
            db.commit()
    finally:
        db.close()

# Функция для получения сессии базы данных
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()