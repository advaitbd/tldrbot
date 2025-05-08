from datetime import datetime
from typing import Optional

from sqlalchemy import (
    create_engine, Column, Integer, BigInteger, String, DateTime, Text
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from config.settings import DatabaseConfig

DATABASE_URL = DatabaseConfig.DATABASE_URL
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set.")

# SQLAlchemy setup
Base = declarative_base()
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class UserEvent(Base):
    __tablename__ = "user_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    username = Column(String(64), nullable=True)
    first_name = Column(String(128), nullable=True)
    last_name = Column(String(128), nullable=True)
    chat_id = Column(BigInteger, nullable=False)
    event_type = Column(String(64), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    extra = Column(Text, nullable=True)  # For optional JSON or text data
    llm_name = Column(String(64), nullable=True)  # Name of the LLM used

def create_tables():
    Base.metadata.create_all(bind=engine)

def log_user_event(
    user_id: int,
    chat_id: int,
    event_type: str,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    extra: Optional[str] = None,
    llm_name: Optional[str] = None,
    session: Optional[Session] = None
):
    """Log a user event to the database."""
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True
    try:
        event = UserEvent(
            user_id=user_id,
            chat_id=chat_id,
            event_type=event_type,
            username=username,
            first_name=first_name,
            last_name=last_name,
            extra=extra,
            llm_name=llm_name,
        )
        session.add(event)
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        if close_session:
            session.close()
