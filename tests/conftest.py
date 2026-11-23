"""Preparación de las pruebas que usan base de datos.

- Usan una base aparte, `fiao_test`, en el mismo PostgreSQL de DATABASE_URL.
  Se crea sola si no existe y las tablas se rehacen en cada corrida.
- Cada prueba corre dentro de una transacción que se deshace al final:
  ninguna prueba deja datos para la siguiente.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

import app.modelos  # noqa: F401  (registra las tablas)
from app.config import get_settings
from app.db import Base, get_db
from app.main import app

URL = make_url(get_settings().database_url)
URL_TEST = URL.set(database="fiao_test")


@pytest.fixture(scope="session")
def engine():
    # Crea la base fiao_test si no existe (conectándose a la base "postgres").
    with create_engine(URL.set(database="postgres"), isolation_level="AUTOCOMMIT").connect() as c:
        existe = c.execute(text("SELECT 1 FROM pg_database WHERE datname = 'fiao_test'")).scalar()
        if not existe:
            c.execute(text("CREATE DATABASE fiao_test"))

    eng = create_engine(URL_TEST)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    """Sesión de base de datos que se deshace al terminar la prueba."""
    conexion = engine.connect()
    transaccion = conexion.begin()
    sesion = Session(bind=conexion, join_transaction_mode="create_savepoint", expire_on_commit=False)
    yield sesion
    sesion.close()
    transaccion.rollback()
    conexion.close()


@pytest.fixture
def client(db):
    """Cliente HTTP de prueba que usa la sesión `db` en vez de la base real."""
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()
