"""SQLAlchemy engine/session setup. SQLite file lives under DATA_DIR (see
config.py), which is bind-mounted to the host so the database survives
container rebuilds."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import Config

engine = create_engine(
    f"sqlite:///{Config.DB_PATH}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
