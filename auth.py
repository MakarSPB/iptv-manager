from passlib.context import CryptContext  # Добавляем правильный импорт
from database import SessionLocal, User
from config import settings
from jose import jwt
from datetime import datetime, timedelta

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def authenticate_admin(username: str, password: str):
    return username == settings.admin_username and password == settings.admin_password

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm="HS256")
    return encoded_jwt

def init_admin_user():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == settings.admin_username).first()
        if not user:
            hashed_password = get_password_hash(settings.admin_password)
            admin_user = User(username=settings.admin_username, password=hashed_password, is_admin=True)
            db.add(admin_user)
            db.commit()
    finally:
        db.close()