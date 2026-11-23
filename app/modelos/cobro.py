"""Grupo Cobro: listados_pago, detalle_listado_pago y pagos."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.dominio.enums import EstadoListado
from app.modelos.catalogo import Cliente
from app.modelos.tipos import MONTO, TASA, enum_pg


class ListadoPago(Base):
    """Listado generado en cada fecha de corte."""

    __tablename__ = "listados_pago"
    __table_args__ = (UniqueConstraint("cliente_id", "fecha_corte"),)

    listado_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.cliente_id"))
    fecha_corte: Mapped[date]
    fecha_pago_pactada: Mapped[date]
    subtotal: Mapped[Decimal] = mapped_column(MONTO)            # P
    tea_comp_aplicada: Mapped[Decimal] = mapped_column(TASA)
    tea_mora_aplicada: Mapped[Decimal] = mapped_column(TASA)
    dias_mora: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    interes_comp_atraso: Mapped[Decimal] = mapped_column(MONTO, default=Decimal("0.00"), server_default=text("0.00"))
    interes_mora: Mapped[Decimal] = mapped_column(MONTO, default=Decimal("0.00"), server_default=text("0.00"))
    total: Mapped[Decimal] = mapped_column(MONTO)               # P + I_C + M
    estado: Mapped[EstadoListado] = mapped_column(
        enum_pg(EstadoListado, "estado_listado_enum"), default=EstadoListado.PENDIENTE, server_default=text("'PENDIENTE'")
    )

    cliente: Mapped[Cliente] = relationship()
    items: Mapped[list["DetalleListadoPago"]] = relationship(
        back_populates="listado", order_by="DetalleListadoPago.fecha"
    )
    pago: Mapped["Pago | None"] = relationship(back_populates="listado")


class DetalleListadoPago(Base):
    """Cada renglón del listado: una compra a fin de mes o una cuota."""

    __tablename__ = "detalle_listado_pago"
    __table_args__ = (
        # Solo uno de los dos tiene valor (nota del DBML).
        CheckConstraint(
            "(transaccion_id IS NULL) <> (plan_id IS NULL)",
            name="ck_detalle_listado_compra_o_cuota",
        ),
    )

    detalle_listado_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    listado_id: Mapped[int] = mapped_column(ForeignKey("listados_pago.listado_id"))
    transaccion_id: Mapped[int | None] = mapped_column(ForeignKey("transacciones.transaccion_id"))
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plan_pagos.plan_id"))
    fecha: Mapped[date]
    descripcion: Mapped[str] = mapped_column(String(100))
    monto: Mapped[Decimal] = mapped_column(MONTO)
    dias: Mapped[int] = mapped_column(Integer)
    interes: Mapped[Decimal] = mapped_column(MONTO)
    total: Mapped[Decimal] = mapped_column(MONTO)

    listado: Mapped[ListadoPago] = relationship(back_populates="items")


class Pago(Base):
    """Un solo pago por listado (no hay pagos parciales)."""

    __tablename__ = "pagos"

    pago_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    listado_id: Mapped[int] = mapped_column(ForeignKey("listados_pago.listado_id"), unique=True)
    fecha_pago_real: Mapped[datetime]
    monto_pagado: Mapped[Decimal] = mapped_column(MONTO)
    interes_moratorio_pagado: Mapped[Decimal] = mapped_column(MONTO, default=Decimal("0.00"), server_default=text("0.00"))
    interes_comp_pagado: Mapped[Decimal] = mapped_column(MONTO, default=Decimal("0.00"), server_default=text("0.00"))
    capital_pagado: Mapped[Decimal] = mapped_column(MONTO, default=Decimal("0.00"), server_default=text("0.00"))

    listado: Mapped[ListadoPago] = relationship(back_populates="pago")
