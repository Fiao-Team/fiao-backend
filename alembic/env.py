"""Configuración de Alembic (migraciones de la base de datos).

- La conexión sale de DATABASE_URL (.env), igual que la app.
- `target_metadata` son los modelos de app/modelos: con ellos Alembic puede
  comparar el código con la base y generar los scripts (autogenerate).

Comandos útiles (desde fiao-backend):
    .venv\\Scripts\\python.exe -m alembic upgrade head     -> aplica lo que falte
    .venv\\Scripts\\python.exe -m alembic current          -> versión actual de la base
"""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context
from app.config.configuracion import get_settings
from app.config.db import Base
import app.entidades.todas  # noqa: F401  (registra las 13 tablas en Base.metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
DATABASE_URL = get_settings().database_url


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse (alembic upgrade head --sql)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Se conecta a la base y aplica las migraciones."""
    connectable = create_engine(DATABASE_URL, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
