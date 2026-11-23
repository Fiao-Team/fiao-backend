"""Atraso, estado del listado, imputación del pago y saldo deudor
(informe 3.3.5 y 3.3.6; pseudocódigo 4.1 y 4.7)."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.calculo.fechas import dias_entre
from app.calculo.redondeo import red_monto
from app.calculo.tasas import tep
from app.entidades.enums import EstadoListado

CERO = Decimal("0.00")


@dataclass(frozen=True)
class Atraso:
    dm: int         # días de atraso
    I_C: Decimal    # interés compensatorio adicional por los días de atraso
    M: Decimal      # intereses por mora


def calcular_atraso(
    P: Decimal, tea_comp: Decimal, tea_mora: Decimal, fecha_pactada: date, fecha: date
) -> Atraso:
    """CalcularAtraso: sobre P (lo que debía pagarse en la fecha pactada) se
    cobran, por los dm días de atraso, el interés compensatorio adicional
    (con la TEA compensatoria) y la mora (con la TEA moratoria)."""
    dm = dias_entre(fecha_pactada, fecha)
    if dm <= 0:
        return Atraso(dm=0, I_C=CERO, M=CERO)
    return Atraso(
        dm=dm,
        I_C=red_monto(P * tep(tea_comp, dm)),
        M=red_monto(P * tep(tea_mora, dm)),
    )


def estado_listado(pagado: bool, fecha_pactada: date, hoy: date) -> EstadoListado:
    """EstadoListado: PAGADO, VENCIDO (pasó la fecha pactada) o PENDIENTE."""
    if pagado:
        return EstadoListado.PAGADO
    if hoy > fecha_pactada:
        return EstadoListado.VENCIDO
    return EstadoListado.PENDIENTE


@dataclass(frozen=True)
class Imputacion:
    mora: Decimal
    interes: Decimal
    capital: Decimal

    @property
    def total(self) -> Decimal:
        return self.mora + self.interes + self.capital


def imputar_pago(
    intereses_items: list[Decimal], capitales_items: list[Decimal], atraso: Atraso
) -> Imputacion:
    """Imputación del pago: mora -> interés compensatorio -> capital.

    intereses_items: I de cada compra a fin de mes e Ik de cada cuota del listado.
    capitales_items: C de cada compra a fin de mes y Ak de cada cuota del listado.
    """
    return Imputacion(
        mora=atraso.M,
        interes=sum(intereses_items, CERO) + atraso.I_C,
        capital=sum(capitales_items, CERO),
    )


@dataclass(frozen=True)
class CompraEnMesesPendiente:
    """Datos de una compra en meses no pagada que necesita SaldoDeudor."""

    C: Decimal
    C_prima: Decimal
    fecha_pago: date                   # fecha de pago de referencia (fin de la gracia)
    amortizaciones_pagadas: list[Decimal]


def saldo_deudor(
    compras_fin_de_mes_pendientes: list[Decimal],
    compras_en_meses_pendientes: list[CompraEnMesesPendiente],
    hoy: date,
) -> Decimal:
    """SaldoDeudor: capital pendiente, sin intereses por devengar.

    - Compras a fin de mes no pagadas: su C.
    - Compras en meses: su C mientras dura la gracia; desde la fecha de pago
      de referencia, C' menos lo ya amortizado.
    """
    sd = sum(compras_fin_de_mes_pendientes, CERO)
    for compra in compras_en_meses_pendientes:
        if hoy < compra.fecha_pago:
            sd += compra.C
        else:
            sd += compra.C_prima - sum(compra.amortizaciones_pagadas, CERO)
    return sd
