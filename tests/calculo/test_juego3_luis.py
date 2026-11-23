"""Juego 3 - Luis Ramos: dólares, pago al mes siguiente del corte y mes de 31 días.

PENDIENTE: depende de que el profesor confirme que los días entre fechas son
días calendario reales. Todavía NO está en el informe. Si el profesor decide
otra cosa, este juego se corrige o se elimina (buscar la etiqueta
`pendiente_profesor`). Para correr las pruebas sin él:
    pytest -m "not pendiente_profesor"

Condiciones: US$, límite 300.00, 2 % efectiva mensual, moratoria 5 % efectiva
anual, corte 25 (23:59), pago 10. Compra el 20/10/2026; paga el 13/11/2026.
"""

from datetime import date, datetime, time
from decimal import Decimal as D

import pytest

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

pytestmark = pytest.mark.pendiente_profesor

TEA = normalizar_tea(TipoTasa.EFECTIVA, D("2"), PeriodoDias.MENSUAL)
TEA_MORA = normalizar_tea(TipoTasa.EFECTIVA, D("5"), PeriodoDias.ANUAL)
LIMITE = D("300.00")
COMPRA = datetime(2026, 10, 20, 12, 0)
CICLO = fecha_pago_del_ciclo(COMPRA, dia_corte=25, hora_corte=time(23, 59), dia_pago=10)


def test_tasas():
    assert a_porcentaje(TEA) == D("26.8241795")
    assert a_porcentaje(TEA_MORA) == D("5.0000000")
    assert a_porcentaje(tep(TEA, 30)) == D("2.0000000")


def test_pago_cae_al_mes_siguiente_del_corte():
    # día de pago (10) <= día de corte (25): el pago es en el mes siguiente
    assert CICLO.corte == datetime(2026, 10, 25, 23, 59)
    assert CICLO.fecha_pago == date(2026, 11, 10)
    assert CICLO.posterior_al_corte is False


def test_dias_reales_pasan_por_el_31_de_octubre():
    d = dias_entre(COMPRA.date(), CICLO.fecha_pago)
    assert d == 21  # con meses de 30 días habrían sido 20
    assert a_porcentaje(tep(TEA, d)) == D("1.3958360")


def test_compra_fin_de_mes():
    r = compra_fin_de_mes(D("80.00"), TEA, 21)
    assert (r.S, r.I) == (D("81.12"), D("1.12"))


def test_cronograma_plancha_2_cuotas():
    cr = generar_cronograma(D("120.00"), TEA, 21, 2, CICLO.fecha_pago, 10)
    assert cr.C_prima == D("121.68")
    assert cr.frc == D("0.5150495")
    assert cr.R == D("62.67")

    esperado = [
        # vence, saldo inicial, interés, amortización, cuota, saldo final
        (date(2026, 12, 10), "121.68", "2.43", "60.24", "62.67", "61.44"),
        (date(2027, 1, 10), "61.44", "1.23", "61.44", "62.67", "0.00"),
    ]
    for cuota, (venc, si, i, a, r, sf) in zip(cr.cuotas, esperado):
        assert cuota.vencimiento == venc
        assert cuota.saldo_inicial == D(si)
        assert cuota.interes == D(i)
        assert cuota.amortizacion == D(a)
        assert cuota.cuota == D(r)
        assert cuota.saldo_final == D(sf)

    assert cr.total == D("125.34")
    assert sum(c.interes for c in cr.cuotas) == D("3.66")


def test_listado_25_octubre_pagado_con_3_dias_de_atraso():
    P = D("81.12")  # solo la compra a fin de mes: la primera cuota vence el 10/12
    atraso = calcular_atraso(P, TEA, TEA_MORA, date(2026, 11, 10), date(2026, 11, 13))
    assert atraso.dm == 3
    assert a_porcentaje(tep(TEA, 3)) == D("0.1982225")
    assert a_porcentaje(tep(TEA_MORA, 3)) == D("0.0406667")
    assert (atraso.I_C, atraso.M) == (D("0.16"), D("0.03"))
    assert P + atraso.I_C + atraso.M == D("81.31")

    imp = imputar_pago([D("1.12")], [D("80.00")], atraso)
    assert (imp.mora, imp.interes, imp.capital) == (D("0.03"), D("1.28"), D("80.00"))
    assert imp.total == D("81.31")


def test_credito_disponible():
    plancha = CompraEnMesesPendiente(
        C=D("120.00"), C_prima=D("121.68"),
        fecha_pago=date(2026, 11, 10), amortizaciones_pagadas=[],
    )
    # 20/10, después de la venta: 300 - 200
    assert LIMITE - saldo_deudor([D("80.00")], [plancha], date(2026, 10, 20)) == D("100.00")
    # 10/11: se capitaliza la gracia de la plancha (+1.68)
    assert LIMITE - saldo_deudor([D("80.00")], [plancha], date(2026, 11, 10)) == D("98.32")
    # 13/11: pagó el listado (capital 80.00)
    assert LIMITE - saldo_deudor([], [plancha], date(2026, 11, 13)) == D("178.32")
