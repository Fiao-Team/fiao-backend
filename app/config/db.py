"""Conexión a PostgreSQL con SQLAlchemy.

`create_engine` no se conecta todavía: la conexión real se abre recién
cuando una consulta la necesita.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config.configuracion import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Clase base de todas las tablas (modelos)."""


def get_db() -> Iterator[Session]:
    """Abre una sesión de base de datos por cada petición y la cierra al final."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
