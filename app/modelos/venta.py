"""Grupo Venta: transacciones, detalle_transaccion y plan_pagos."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.dominio.enums import EstadoCuota, EstadoTransaccion, ModalidadPago
from app.modelos.catalogo import Cliente, Producto
from app.modelos.tipos import MONTO, TASA, enum_pg


class Transaccion(Base):
    """Cada compra. Una venta puede generar dos: una a fin de mes y otra en meses."""

    __tablename__ = "transacciones"

    transaccion_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.cliente_id"))
    fecha_hora_compra: Mapped[datetime]
    modalidad_pago: Mapped[ModalidadPago] = mapped_column(enum_pg(ModalidadPago, "modalidad_pago_enum"))
    num_cuotas: Mapped[int | None] = mapped_column(SmallInteger)       # solo EN_MESES
    monto_capital: Mapped[Decimal] = mapped_column(MONTO)              # C

    tea_aplicada: Mapped[Decimal] = mapped_column(TASA)                # en %
    tem_aplicada: Mapped[Decimal | None] = mapped_column(TASA)         # solo EN_MESES
    dias_financiamiento_gracia: Mapped[int] = mapped_column(Integer)   # d o dg
    deuda_capitalizada: Mapped[Decimal | None] = mapped_column(MONTO)  # C', solo EN_MESES
    monto_total: Mapped[Decimal] = mapped_column(MONTO)                # S o suma de cuotas
    tcea: Mapped[Decimal | None] = mapped_column(TASA)

    fecha_corte_aplicada: Mapped[date]
    fecha_vencimiento: Mapped[date]  # fecha de pago (fin de mes) o de referencia (en meses)
    estado_transaccion: Mapped[EstadoTransaccion] = mapped_column(
        enum_pg(EstadoTransaccion, "estado_transaccion_enum"), default=EstadoTransaccion.PENDIENTE, server_default=text("'PENDIENTE'")
    )

    cliente: Mapped[Cliente] = relationship()
    detalles: Mapped[list["DetalleTransaccion"]] = relationship(back_populates="transaccion")
    cuotas: Mapped[list["PlanPago"]] = relationship(
        back_populates="transaccion", order_by="PlanPago.numero_cuota"
    )


class DetalleTransaccion(Base):
    """Productos de cada compra."""

    __tablename__ = "detalle_transaccion"

    detalle_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    transaccion_id: Mapped[int] = mapped_column(ForeignKey("transacciones.transaccion_id"))
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.producto_id"))
    cantidad: Mapped[Decimal] = mapped_column(Numeric(8, 3))
    precio_unitario: Mapped[Decimal] = mapped_column(MONTO)
    subtotal: Mapped[Decimal] = mapped_column(MONTO)

    transaccion: Mapped[Transaccion] = relationship(back_populates="detalles")
    producto: Mapped[Producto] = relationship()


class PlanPago(Base):
    """Cronograma del método francés: una fila por cuota."""

    __tablename__ = "plan_pagos"
    __table_args__ = (UniqueConstraint("transaccion_id", "numero_cuota"),)

    plan_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    transaccion_id: Mapped[int] = mapped_column(ForeignKey("transacciones.transaccion_id"))
    numero_cuota: Mapped[int] = mapped_column(SmallInteger)
    fecha_vencimiento: Mapped[date]
    saldo_inicial: Mapped[Decimal] = mapped_column(MONTO)
    interes_compensatorio: Mapped[Decimal] = mapped_column(MONTO)  # Ik
    amortizacion: Mapped[Decimal] = mapped_column(MONTO)           # Ak
    monto_cuota: Mapped[Decimal] = mapped_column(MONTO)            # Rk
    saldo_final: Mapped[Decimal] = mapped_column(MONTO)
    estado_cuota: Mapped[EstadoCuota] = mapped_column(
        enum_pg(EstadoCuota, "estado_cuota_enum"), default=EstadoCuota.PENDIENTE, server_default=text("'PENDIENTE'")
    )

    transaccion: Mapped[Transaccion] = relationship(back_populates="cuotas")
