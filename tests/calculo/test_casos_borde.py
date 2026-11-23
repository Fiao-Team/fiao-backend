"""Casos de borde: días reales, febrero, hora de corte exacta y validaciones."""

from datetime import date, datetime, time
from decimal import Decimal as D

import pytest

from app.calculo.ciclo import fecha_pago_de_corte, fecha_pago_del_ciclo
from app.calculo.cobro import estado_listado
from app.calculo.compras import generar_cronograma
from app.calculo.fechas import dias_entre, fecha_con_dia, sumar_meses
from app.calculo.tasas import normalizar_tea
from app.dominio.enums import CapitalizacionDias, EstadoListado, PeriodoDias, TipoTasa


# --- Días calendario reales (tabla del capítulo 4) ---
@pytest.mark.parametrize("desde, hasta, dias", [
    (date(2026, 10, 20), date(2026, 11, 5), 16),
    (date(2027, 1, 26), date(2027, 2, 26), 31),
    (date(2027, 2, 26), date(2027, 3, 26), 28),
    (date(2028, 2, 28), date(2028, 3, 1), 2),   # 2028 es bisiesto
])
def test_dias_entre_usa_dias_reales(desde, hasta, dias):
    assert dias_entre(desde, hasta) == dias


# --- Día 30 en febrero: se usa el último día del mes ---
def test_fecha_con_dia_en_febrero():
    assert fecha_con_dia(2027, 2, 30) == date(2027, 2, 28)
    assert fecha_con_dia(2028, 2, 30) == date(2028, 2, 29)


def test_sumar_meses_mantiene_el_dia_pactado():
    # de 28/02 (porque el 30 no existe) se vuelve al 30 en marzo
    assert sumar_meses(date(2027, 2, 28), 1, 30) == date(2027, 3, 30)
    # cruza de año
    assert sumar_meses(date(2026, 12, 26), 1, 26) == date(2027, 1, 26)


def test_corte_30_en_febrero():
    c = fecha_pago_del_ciclo(datetime(2027, 2, 15, 9, 0), dia_corte=30,
                             hora_corte=time(23, 59), dia_pago=10)
    assert c.corte == datetime(2027, 2, 28, 23, 59)
    # pago 10 <= corte 30: el pago cae en el mes siguiente al corte
    assert c.fecha_pago == date(2027, 3, 10)


def test_pago_30_en_febrero():
    assert fecha_pago_de_corte(date(2027, 2, 20), dia_corte=20, dia_pago=30) == date(2027, 2, 28)


def test_cuotas_con_dia_30_pasan_por_febrero():
    cr = generar_cronograma(D("300.00"), D("0.30"), 10, 3, date(2026, 12, 30), 30)
    assert [c.vencimiento for c in cr.cuotas] == [
        date(2027, 1, 30), date(2027, 2, 28), date(2027, 3, 30)]
    assert cr.cuotas[-1].saldo_final == D("0.00")


# --- Compra justo a la hora de corte ---
def test_compra_justo_a_la_hora_de_corte_entra_en_ese_corte():
    c = fecha_pago_del_ciclo(datetime(2026, 9, 20, 23, 59), 20, time(23, 59), 26)
    assert c.posterior_al_corte is False
    assert c.fecha_pago == date(2026, 9, 26)


def test_compra_un_minuto_despues_pasa_al_siguiente_corte():
    c = fecha_pago_del_ciclo(datetime(2026, 9, 21, 0, 0), 20, time(23, 59), 26)
    assert c.posterior_al_corte is True
    assert c.fecha_pago == date(2026, 10, 26)


def test_segundos_no_cuentan_la_hora_es_al_minuto():
    c = fecha_pago_del_ciclo(datetime(2026, 9, 20, 23, 59, 45), 20, time(23, 59), 26)
    assert c.posterior_al_corte is False


# --- Estado del listado ---
def test_estado_listado():
    pactada = date(2026, 9, 26)
    assert estado_listado(False, pactada, date(2026, 9, 26)) == EstadoListado.PENDIENTE
    assert estado_listado(False, pactada, date(2026, 9, 27)) == EstadoListado.VENCIDO
    assert estado_listado(True, pactada, date(2026, 10, 4)) == EstadoListado.PAGADO


# --- Validaciones del cálculo ---
def test_tasa_nominal_sin_capitalizacion_falla():
    with pytest.raises(ValueError):
        normalizar_tea(TipoTasa.NOMINAL, D("30"), PeriodoDias.ANUAL)


def test_tasa_efectiva_mensual_a_tea():
    # 2.5 % efectiva mensual -> (1.025)^12 - 1
    assert normalizar_tea(TipoTasa.EFECTIVA, D("2.5"), PeriodoDias.MENSUAL) == D("0.344888824")


def test_moratoria_cero_da_tea_cero():
    assert normalizar_tea(TipoTasa.EFECTIVA, D("0"), PeriodoDias.ANUAL) == D("0E-9")


def test_nominal_con_capitalizacion_diaria():
    # 30 % nominal anual, capitalización diaria: (1 + 0.30/360)^360 - 1
    tea = normalizar_tea(TipoTasa.NOMINAL, D("30"), PeriodoDias.ANUAL, CapitalizacionDias.DIARIA)
    assert tea == D("0.349690179")
