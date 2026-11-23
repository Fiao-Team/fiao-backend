"""Grupo Configuración: parametros_sistema y tasas_maximas_bcrp."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, SmallInteger, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.dominio.enums import Moneda
from app.modelos.tipos import TASA, enum_pg


class ParametrosSistema(Base):
    """Configuración general (una sola fila). Guarda la fecha simulada."""

    __tablename__ = "parametros_sistema"

    parametro_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    # Si tiene valor, reemplaza al "hoy" en toda la app (pruebas y exposición).
    fecha_simulada: Mapped[date | None]
    actualizado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.usuario_id"))
    fecha_actualizacion: Mapped[datetime] = mapped_column(server_default=func.now())


class TasaMaximaBcrp(Base):
    """Tasas máximas del BCRP por moneda y período (TEA en %)."""

    __tablename__ = "tasas_maximas_bcrp"
    __table_args__ = (UniqueConstraint("moneda", "vigente_desde"),)

    tasa_maxima_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    moneda: Mapped[Moneda] = mapped_column(enum_pg(Moneda, "moneda_enum"))
    vigente_desde: Mapped[date]
    vigente_hasta: Mapped[date]
    tasa_max_compensatoria: Mapped[Decimal] = mapped_column(TASA)
    tasa_max_moratoria: Mapped[Decimal] = mapped_column(TASA)  # 15 % de la compensatoria
