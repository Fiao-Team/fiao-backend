"""Datos iniciales: parámetros del sistema, tasas máximas del BCRP y usuario admin.

- parametros_sistema: una sola fila, sin fecha simulada.
- tasas_maximas_bcrp: período mayo–octubre 2026 (informe, 2.1; Circular 0008-2021-BCRP).
  La moratoria es el 15 % de la compensatoria. El período noviembre 2026 – abril 2027
  está PENDIENTE: se agregará en una migración nueva cuando se tengan los valores.
- usuario "admin" (ADMIN_SISTEMA): su contraseña sale de ADMIN_PASSWORD_INICIAL (.env)
  y se guarda solo como hash.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.comun.seguridad import hash_password
from app.config import get_settings

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    clave = get_settings().admin_password_inicial
    if not clave or len(clave) < 8:
        raise RuntimeError(
            "Falta ADMIN_PASSWORD_INICIAL en el archivo .env (mínimo 8 caracteres)."
        )

    op.execute("INSERT INTO parametros_sistema (parametro_id, fecha_simulada) VALUES (1, NULL)")

    op.execute(
        """
        INSERT INTO tasas_maximas_bcrp
            (moneda, vigente_desde, vigente_hasta, tasa_max_compensatoria, tasa_max_moratoria)
        VALUES
            ('PEN', '2026-05-01', '2026-10-31', 114.1300000, 17.1195000),
            ('USD', '2026-05-01', '2026-10-31',  99.8400000, 14.9760000)
        """
    )

    op.get_bind().execute(
        sa.text(
            "INSERT INTO usuarios (username, password_hash, nombres, rol) "
            "VALUES ('admin', :hash, 'Administrador del sistema', 'ADMIN_SISTEMA')"
        ),
        {"hash": hash_password(clave)},
    )


def downgrade() -> None:
    op.execute("DELETE FROM usuarios WHERE username = 'admin'")
    op.execute("DELETE FROM tasas_maximas_bcrp WHERE vigente_desde = '2026-05-01'")
    op.execute("DELETE FROM parametros_sistema WHERE parametro_id = 1")
