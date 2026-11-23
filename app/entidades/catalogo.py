"""Grupo Catálogo: clientes y productos."""

from datetime import time
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy import (
    BigInteger, CHAR, CheckConstraint, ForeignKey, SmallInteger, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.db import Base
from app.entidades.enums import CapitalizacionDias, FormaVentaProducto, Moneda, PeriodoDias, TipoTasa
from app.entidades.acceso import Tienda, Usuario
from app.entidades.tipos import ACTIVO, MONTO, TASA, enum_pg


class Cliente(Base):
    """Cliente de una tienda con sus condiciones de crédito pactadas."""

    __tablename__ = "clientes"
    __table_args__ = (
        UniqueConstraint("tienda_id", "dni"),
        CheckConstraint("dia_corte BETWEEN 1 AND 30", name="ck_clientes_dia_corte"),
        CheckConstraint("dia_pago BETWEEN 1 AND 30", name="ck_clientes_dia_pago"),
        CheckConstraint("dia_pago <> dia_corte", name="ck_clientes_pago_distinto_corte"),
        CheckConstraint("tasa_compensatoria > 0", name="ck_clientes_tasa_comp"),
        CheckConstraint("tasa_moratoria >= 0", name="ck_clientes_tasa_mora"),
    )

    cliente_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tienda_id: Mapped[int] = mapped_column(ForeignKey("tiendas.tienda_id"))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.usuario_id"), unique=True)
    dni: Mapped[str] = mapped_column(CHAR(8))
    nombres_apellidos: Mapped[str] = mapped_column(String(80))
    telefono: Mapped[str] = mapped_column(CHAR(9))
    direccion: Mapped[str] = mapped_column(String(100))
    moneda: Mapped[Moneda] = mapped_column(enum_pg(Moneda, "moneda_enum"), default=Moneda.PEN, server_default=text("'PEN'"))
    limite_credito: Mapped[Decimal] = mapped_column(MONTO)
    plazo_max_meses: Mapped[int] = mapped_column(SmallInteger)

    # Ciclo de corte
    dia_corte: Mapped[int] = mapped_column(SmallInteger)
    hora_corte: Mapped[time] = mapped_column(default=time(23, 59), server_default=text("'23:59'"))
    dia_pago: Mapped[int] = mapped_column(SmallInteger)

    # Tasa compensatoria (valor en %)
    tipo_tasa_comp: Mapped[TipoTasa] = mapped_column(enum_pg(TipoTasa, "tipo_tasa_enum"), default=TipoTasa.EFECTIVA, server_default=text("'EFECTIVA'"))
    tasa_compensatoria: Mapped[Decimal] = mapped_column(TASA)
    periodo_tasa_comp: Mapped[PeriodoDias] = mapped_column(enum_pg(PeriodoDias, "periodo_dias_enum"), default=PeriodoDias.ANUAL, server_default=text("'ANUAL'"))
    capitalizacion_comp: Mapped[CapitalizacionDias | None] = mapped_column(enum_pg(CapitalizacionDias, "capitalizacion_dias_enum"))

    # Tasa moratoria (valor en %)
    tipo_tasa_mora: Mapped[TipoTasa] = mapped_column(enum_pg(TipoTasa, "tipo_tasa_enum"), default=TipoTasa.EFECTIVA, server_default=text("'EFECTIVA'"))
    tasa_moratoria: Mapped[Decimal] = mapped_column(TASA)
    periodo_tasa_mora: Mapped[PeriodoDias] = mapped_column(enum_pg(PeriodoDias, "periodo_dias_enum"), default=PeriodoDias.ANUAL, server_default=text("'ANUAL'"))
    capitalizacion_mora: Mapped[CapitalizacionDias | None] = mapped_column(enum_pg(CapitalizacionDias, "capitalizacion_dias_enum"))

    estado: Mapped[int] = mapped_column(SmallInteger, default=ACTIVO, server_default=text("1"))

    tienda: Mapped[Tienda] = relationship()
    usuario: Mapped[Usuario | None] = relationship(back_populates="cliente")


class Producto(Base):
    """Producto o servicio que la tienda vende al crédito."""

    __tablename__ = "productos"

    producto_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tienda_id: Mapped[int] = mapped_column(ForeignKey("tiendas.tienda_id"))
    nombre: Mapped[str] = mapped_column(String(80))  # campo "Descripción" del formulario (Fig. 8)
    descripcion: Mapped[str | None] = mapped_column(Text)
    marca: Mapped[str | None] = mapped_column(String(40))
    categoria: Mapped[str | None] = mapped_column(String(40))
    proveedor: Mapped[str | None] = mapped_column(String(60))
    unidad_medida: Mapped[str] = mapped_column(String(15), default="Unidad", server_default=text("'Unidad'"))
    moneda: Mapped[Moneda] = mapped_column(enum_pg(Moneda, "moneda_enum"), default=Moneda.PEN, server_default=text("'PEN'"))
    precio_contado: Mapped[Decimal] = mapped_column(MONTO)
    precio_lista: Mapped[Decimal] = mapped_column(MONTO)
    forma_venta_credito: Mapped[FormaVentaProducto] = mapped_column(
        enum_pg(FormaVentaProducto, "forma_venta_producto_enum"), default=FormaVentaProducto.FIN_DE_MES, server_default=text("'FIN_DE_MES'")
    )
    imagen_url: Mapped[str | None] = mapped_column(String(255))
    estado: Mapped[int] = mapped_column(SmallInteger, default=ACTIVO, server_default=text("1"))
