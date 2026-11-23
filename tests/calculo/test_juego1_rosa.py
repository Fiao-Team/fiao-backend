"""Juego 1 - Rosa Díaz (informe 3.4.2): tasa efectiva y paga a tiempo.

Condiciones: 30 % efectiva anual, moratoria 5 % efectiva anual,
corte 20 a las 23:59, pago 26, límite S/ 500.00. Compra el 15/09/2026.
"""

from datetime import date, datetime, time
from decimal import Decimal as D

from app.calculo.ciclo import fecha_pago_del_ciclo
from app.calculo.cobro import (
    CompraEnMesesPendiente,
    calcular_atraso,
    imputar_pago,
    saldo_deudor,
)
from app.calculo.compras import compra_fin_de_mes, generar_cronograma
from app.calculo.fechas import dias_entre
from app.calculo.redondeo import a_porcentaje
from app.calculo.tasas import normalizar_tea, tep
from app.entidades.enums import PeriodoDias, TipoTasa

TEA = normalizar_tea(TipoTasa.EFECTIVA, D("30"), PeriodoDias.ANUAL)
TEA_MORA = normalizar_tea(TipoTasa.EFECTIVA, D("5"), PeriodoDias.ANUAL)
COMPRA = datetime(2026, 9, 15, 10, 0)
CICLO = fecha_pago_del_ciclo(COMPRA, dia_corte=20, hora_corte=time(23, 59), dia_pago=26)


def test_tasas():
    assert a_porcentaje(TEA) == D("30.0000000")
    assert a_porcentaje(TEA_MORA) == D("5.0000000")
    assert a_porcentaje(tep(TEA, 11)) == D("0.8048906")
    assert a_porcentaje(tep(TEA, 30)) == D("2.2104451")


def test_ciclo_antes_del_corte():
    assert CICLO.corte == datetime(2026, 9, 20, 23, 59)
    assert CICLO.fecha_pago == date(2026, 9, 26)
    assert CICLO.posterior_al_corte is False
    assert dias_entre(COMPRA.date(), CICLO.fecha_pago) == 11


def test_compra_fin_de_mes():
    r = compra_fin_de_mes(D("45.00"), TEA, 11)
    assert r.S == D("45.36")
    assert r.I == D("0.36")


def test_cronograma_licuadora_3_cuotas():
    cr = generar_cronograma(D("210.00"), TEA, 11, 3, CICLO.fecha_pago, 26)
    assert cr.C_prima == D("211.69")
    assert cr.frc == D("0.3481770")
    assert cr.R == D("73.71")

    esperado = [
        # vence, saldo inicial, interés, amortización, cuota, saldo final
        (date(2026, 10, 26), "211.69", "4.68", "69.03", "73.71", "142.66"),
        (date(2026, 11, 26), "142.66", "3.15", "70.56", "73.71", "72.10"),
        (date(2026, 12, 26), "72.10", "1.59", "72.10", "73.69", "0.00"),
    ]
    for cuota, (venc, si, i, a, r, sf) in zip(cr.cuotas, esperado):
        assert cuota.vencimiento == venc
        assert cuota.saldo_inicial == D(si)
        assert cuota.interes == D(i)
        assert cuota.amortizacion == D(a)
        assert cuota.cuota == D(r)
        assert cuota.saldo_final == D(sf)

    assert cr.total == D("221.11")


def test_pago_sin_atraso():
    P = D("45.36")
    atraso = calcular_atraso(P, TEA, TEA_MORA, date(2026, 9, 26), date(2026, 9, 26))
    assert (atraso.dm, atraso.I_C, atraso.M) == (0, D("0.00"), D("0.00"))
    imp = imputar_pago([D("0.36")], [D("45.00")], atraso)
    assert (imp.mora, imp.interes, imp.capital) == (D("0.00"), D("0.36"), D("45.00"))
    assert imp.total == D("45.36")


def test_credito_disponible():
    limite = D("500.00")
    licuadora = CompraEnMesesPendiente(
        C=D("210.00"), C_prima=D("211.69"),
        fecha_pago=date(2026, 9, 26), amortizaciones_pagadas=[],
    )
    # 15/09, después de la venta: 500 - 255
    assert limite - saldo_deudor([D("45.00")], [licuadora], date(2026, 9, 15)) == D("245.00")
    # 26/09: se capitaliza la gracia de la licuadora y se paga el fin de mes
    assert limite - saldo_deudor([], [licuadora], date(2026, 9, 26)) == D("288.31")
