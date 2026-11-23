"""Juego 2 - Carlos Mendoza (informe 3.4.3): tasa nominal y paga con mora.

Condiciones: 30 % nominal anual con capitalización mensual, moratoria 5 %
nominal anual con capitalización mensual, límite S/ 700.00, corte 20 (23:59), pago 26.
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
from app.dominio.enums import CapitalizacionDias, PeriodoDias, TipoTasa

TEA = normalizar_tea(TipoTasa.NOMINAL, D("30"), PeriodoDias.ANUAL, CapitalizacionDias.MENSUAL)
TEA_MORA = normalizar_tea(TipoTasa.NOMINAL, D("5"), PeriodoDias.ANUAL, CapitalizacionDias.MENSUAL)
LIMITE = D("700.00")


def ciclo(fecha_hora: datetime):
    return fecha_pago_del_ciclo(fecha_hora, dia_corte=20, hora_corte=time(23, 59), dia_pago=26)


def test_tasas():
    assert a_porcentaje(TEA) == D("34.4888824")
    assert a_porcentaje(TEA_MORA) == D("5.1161898")
    assert a_porcentaje(tep(TEA, 30)) == D("2.5000000")


def test_licuadora_2_cuotas_10_agosto():
    c = ciclo(datetime(2026, 8, 10, 12, 0))
    assert c.fecha_pago == date(2026, 8, 26)
    dg = dias_entre(date(2026, 8, 10), c.fecha_pago)
    assert dg == 16
    assert a_porcentaje(tep(TEA, dg)) == D("1.3256492")

    cr = generar_cronograma(D("210.00"), TEA, dg, 2, c.fecha_pago, 26)
    assert cr.C_prima == D("212.78")
    assert cr.frc == D("0.5188272")
    assert cr.R == D("110.40")

    c1, c2 = cr.cuotas
    assert (c1.vencimiento, c1.interes, c1.amortizacion, c1.cuota, c1.saldo_final) == (
        date(2026, 9, 26), D("5.32"), D("105.08"), D("110.40"), D("107.70"))
    assert (c2.vencimiento, c2.interes, c2.amortizacion, c2.cuota, c2.saldo_final) == (
        date(2026, 10, 26), D("2.69"), D("107.70"), D("110.39"), D("0.00"))
    assert cr.total == D("220.79")


def test_fin_de_mes_5_setiembre():
    c = ciclo(datetime(2026, 9, 5, 12, 0))
    d = dias_entre(date(2026, 9, 5), c.fecha_pago)
    assert (c.fecha_pago, d) == (date(2026, 9, 26), 21)
    assert a_porcentaje(tep(TEA, d)) == D("1.7435076")
    assert compra_fin_de_mes(D("180.00"), TEA, d).S == D("183.14")


def test_compra_rechazada_por_limite_22_setiembre():
    licuadora = CompraEnMesesPendiente(
        C=D("210.00"), C_prima=D("212.78"),
        fecha_pago=date(2026, 8, 26), amortizaciones_pagadas=[],
    )
    disponible = LIMITE - saldo_deudor([D("180.00")], [licuadora], date(2026, 9, 22))
    assert disponible == D("307.22")
    assert D("330.00") - disponible == D("22.78")  # excede por 22.78
    assert D("60.00") <= disponible                # la compra de 60.00 sí pasa


def test_compra_despues_del_corte_22_setiembre():
    c = ciclo(datetime(2026, 9, 22, 12, 0))
    assert c.posterior_al_corte is True
    assert c.corte == datetime(2026, 10, 20, 23, 59)
    d = dias_entre(date(2026, 9, 22), c.fecha_pago)
    assert (c.fecha_pago, d) == (date(2026, 10, 26), 34)
    assert a_porcentaje(tep(TEA, d)) == D("2.8380218")
    r = compra_fin_de_mes(D("60.00"), TEA, d)
    assert (r.S, r.I) == (D("61.70"), D("1.70"))
    # listado de octubre: 61.70 + segunda cuota 110.39
    assert r.S + D("110.39") == D("172.09")


def test_listado_20_setiembre_pagado_con_8_dias_de_atraso():
    P = D("183.14") + D("110.40")
    assert P == D("293.54")

    atraso = calcular_atraso(P, TEA, TEA_MORA, date(2026, 9, 26), date(2026, 10, 4))
    assert atraso.dm == 8
    assert a_porcentaje(tep(TEA, 8)) == D("0.6606423")
    assert a_porcentaje(tep(TEA_MORA, 8)) == D("0.1109418")
    assert atraso.I_C == D("1.94")
    assert atraso.M == D("0.33")
    assert P + atraso.I_C + atraso.M == D("295.81")

    # intereses: 3.14 (fin de mes) + 5.32 (cuota); capital: 180.00 + 105.08
    imp = imputar_pago([D("3.14"), D("5.32")], [D("180.00"), D("105.08")], atraso)
    assert (imp.mora, imp.interes, imp.capital) == (D("0.33"), D("10.40"), D("285.08"))
    assert imp.total == D("295.81")


def test_credito_disponible_despues_del_pago():
    licuadora = CompraEnMesesPendiente(
        C=D("210.00"), C_prima=D("212.78"),
        fecha_pago=date(2026, 8, 26), amortizaciones_pagadas=[D("105.08")],
    )
    # queda: licuadora 212.78 - 105.08 y la compra de 60.00 del 22/09
    assert LIMITE - saldo_deudor([D("60.00")], [licuadora], date(2026, 10, 4)) == D("532.30")
