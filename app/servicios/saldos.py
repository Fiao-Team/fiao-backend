"""SaldoDeudor (pseudocódigo 4.1) leído de la base de datos.

Solo junta los datos de las compras pendientes del cliente; la fórmula está
en app/calculo/cobro.py (saldo_deudor) y no se repite aquí.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculo.cobro import CompraEnMesesPendiente, saldo_deudor
from app.entidades.catalogo import Cliente
from app.entidades.enums import EstadoCuota, EstadoTransaccion, ModalidadPago
from app.entidades.venta import Transaccion


def saldo_deudor_cliente(db: Session, cliente_id: int, fecha: date) -> Decimal:
    """Capital pendiente del cliente a una fecha (sin intereses por devengar)."""
    pendientes = db.scalars(
        select(Transaccion).where(
            Transaccion.cliente_id == cliente_id,
            Transaccion.estado_transaccion == EstadoTransaccion.PENDIENTE,
        )
    ).all()

    fin_de_mes = [t.monto_capital for t in pendientes if t.modalidad_pago == ModalidadPago.FIN_DE_MES]
    en_meses = [
        CompraEnMesesPendiente(
            C=t.monto_capital,
            C_prima=t.deuda_capitalizada,
            fecha_pago=t.fecha_vencimiento,  # fecha de pago de referencia (fin de la gracia)
            amortizaciones_pagadas=[
                c.amortizacion for c in t.cuotas if c.estado_cuota == EstadoCuota.PAGADA
            ],
        )
        for t in pendientes
        if t.modalidad_pago == ModalidadPago.EN_MESES
    ]
    return saldo_deudor(fin_de_mes, en_meses, fecha)


def disponible_cliente(db: Session, cliente: Cliente, fecha: date) -> Decimal:
    """Crédito disponible = límite - saldo deudor."""
    return cliente.limite_credito - saldo_deudor_cliente(db, cliente.cliente_id, fecha)
