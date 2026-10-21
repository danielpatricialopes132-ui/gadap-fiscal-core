"""Gerenciador de Conexão com o Supabase (PostgreSQL via SQLAlchemy e Storage oficial).

Otimizado para o Transaction Pooler do Supabase (porta 6543):
- pool_pre_ping=True
- pool_size=10
- max_overflow=20
"""

from typing import Generator, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from supabase import create_client, Client

from app.core.config import settings

Base = declarative_base()

_engine = None
_SessionLocal = None
_supabase_client: Optional[Client] = None


def get_database_url() -> str:
    """Retorna a string de conexão ajustada para psycopg2."""
    raw_url = settings.DATABASE_URL or "sqlite:///./gadap_fiscal_local.db"
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql://", 1)
    return raw_url


def get_engine():
    """Inicializa ou retorna o engine SQLAlchemy singleton."""
    global _engine, _SessionLocal
    if _engine is None:
        db_url = get_database_url()
        is_sqlite = db_url.startswith("sqlite")
        
        engine_args = {}
        if not is_sqlite:
            engine_args = {
                "pool_pre_ping": True,
                "pool_size": 10,
                "max_overflow": 20,
                "pool_recycle": 300,
            }

        _engine = create_engine(db_url, **engine_args)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_db_session() -> Generator[Session, None, None]:
    """Dependency injection para sessões SQLAlchemy nos endpoints FastAPI."""
    get_engine()
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_supabase_client() -> Optional[Client]:
    """Retorna a instância do cliente oficial do Supabase inicializado com service_role."""
    global _supabase_client
    if _supabase_client is None and settings.SUPABASE_URL and settings.SUPABASE_KEY:
        try:
            _supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        except Exception:
            _supabase_client = None
    return _supabase_client
