from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import os

from config import settings

# Путь к БД
DATABASE_URL = "sqlite:///./users.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    password = Column(String(128))  # Хэш пароля
    is_admin = Column(Boolean, default=False)

    playlists = relationship("Playlist", back_populates="owner")


class Playlist(Base):
    __tablename__ = "playlists"

    id = Column(String(50), primary_key=True)
    filename = Column(String(100))
    content = Column(Text)  # JSON или M3U-текст
    owner_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="playlists")


# Создаём таблицы
Base.metadata.create_all(bind=engine)