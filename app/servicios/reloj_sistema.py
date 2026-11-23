"""RelojSistema: la ÚNICA fuente de "hoy" y "ahora" para el negocio.

REGLA DEL PROYECTO: el código de negocio (compras, pagos, listados, corte,
reportes, saldos) pide la fecha a este servicio y NUNCA usa directamente
date.today() ni datetime.now(). Así la fecha simulada funciona en toda la app.

- Sin fecha simulada: fecha y hora reales en la zona del negocio (America/Lima).
- Con fecha simulada (parametros_sistema.fecha_simulada): esa fecha, con la hora
  real del momento. Ej.: simulada 20/09/2026 y son las 15:30 -> 20/09/2026 15:30.

Excepciones (usan la hora real, no este servicio):
- el vencimiento del token de sesión;
- la fecha y hora de la auditoría (registra cuándo pasó algo de verdad).
"""

from collections.abc import Callable
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.configuracion import get_settings
from app.config.db import get_db
from app.entidades.configuracion import ParametrosSistema


def hora_real_utc() -> datetime:
    """Hora real del servidor, en UTC (con zona horaria)."""
    return datetime.now(UTC)


class RelojSistema:
    """Da "hoy" y "ahora" según la fecha simulada o la real."""

    def __init__(self, db: Session, hora_real: Callable[[], datetime] = hora_real_utc):
        # hora_real se puede reemplazar en las pruebas para fijar el momento.
        self._db = db
        self._hora_real = hora_real
        self._zona = ZoneInfo(get_settings().zona_horaria)

    def fecha_simulada(self) -> date | None:
        """Fecha simulada activa, o None si se usa la fecha real."""
        return self._db.scalar(select(ParametrosSistema.fecha_simulada).limit(1))

    def ahora(self) -> datetime:
        """Fecha y hora del negocio, en hora de Lima y sin zona horaria
        (así se guardan los timestamp en la base de datos)."""
        real = self._hora_real().astimezone(self._zona).replace(tzinfo=None)
        simulada = self.fecha_simulada()
        if simulada is None:
            return real
        return datetime.combine(simulada, real.time())

    def hoy(self) -> date:
        """Fecha del negocio (la simulada si está activa)."""
        return self.ahora().date()


def obtener_reloj(db: Session = Depends(get_db)) -> RelojSistema:
    """Para usar en los controladores:  reloj: RelojSistema = Depends(obtener_reloj)"""
    return RelojSistema(db)
