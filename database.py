from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

# Создаем директорию для базы данных
os.makedirs("data", exist_ok=True)

# Создаем движок базы данных
engine = create_engine("sqlite:///data/users.db", connect_args={"check_same_thread": False})

# Создаем базовый класс для моделей
Base = declarative_base()

# Модель пользователя
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    is_admin = Column(Integer, default=0, server_default="0")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связь с плейлистами
    playlists = relationship("Playlist", back_populates="owner", foreign_keys="[Playlist.owner_id]")

# Модель плейлиста
class Playlist(Base):
    __tablename__ = "playlists"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    filename = Column(String)
    content = Column(Text)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_shared = Column(Boolean, default=False)  # Новое поле: общий доступ

    # Связь с пользователем
    owner = relationship("User", back_populates="playlists")

# Создаем фабрику сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Функция для получения сессии базы данных
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Создаем таблицы при запуске
Base.metadata.create_all(bind=engine)