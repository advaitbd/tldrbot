"""Optional analytics storage."""
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

try:
    from sqlalchemy import create_engine, Column, Integer, BigInteger, String, DateTime, Text
    from sqlalchemy.orm import declarative_base, sessionmaker
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False

_engine = None
_SessionLocal = None
_Base = None


def init_database(database_url: str) -> bool:
    global _engine, _SessionLocal, _Base
    if not SQLALCHEMY_AVAILABLE or not database_url:
        return False
    try:
        _Base = declarative_base()
        _engine = create_engine(database_url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
        
        # Define the UserEvent model
        class UserEvent(_Base):
            __tablename__ = "user_events"
            
            id = Column(Integer, primary_key=True, autoincrement=True)
            user_id = Column(BigInteger, nullable=False)
            username = Column(String(64), nullable=True)
            chat_id = Column(BigInteger, nullable=False)
            event_type = Column(String(64), nullable=False)
            timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
            extra = Column(Text, nullable=True)
        
        globals()['UserEvent'] = UserEvent
        return True
    except Exception as e:
        logger.error(f"Failed to init database: {e}")
        return False


def create_tables() -> None:
    global _Base, _engine
    if _Base and _engine:
        _Base.metadata.create_all(bind=_engine)


def log_event(user_id: int, chat_id: int, event_type: str, username: Optional[str] = None, extra: Optional[str] = None) -> None:
    global _SessionLocal
    if not _SessionLocal:
        return
    UserEvent = globals().get('UserEvent')
    if not UserEvent:
        return
    try:
        session = _SessionLocal()
        session.add(UserEvent(user_id=user_id, chat_id=chat_id, event_type=event_type, username=username, extra=extra))
        session.commit()
        session.close()
    except Exception:
        pass

