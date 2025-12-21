from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

# Создаем движок базы данных
engine = create_engine(
    settings.DATABASE_URL, connect_args={"check_same_thread": False}
)

# Создаем базовый класс для моделей
Base = declarative_base()

# Создаем фабрику сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Функция для получения сессии базы данных
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()