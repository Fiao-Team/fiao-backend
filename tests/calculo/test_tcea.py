"""TCEA (app/calculo/tcea.py) con los montos de los juegos de datos.

La TCEA sale un poco distinta de la TEA porque S y las cuotas se redondean
a centavos: mide el costo real que paga el cliente.
"""

from decimal import Decimal as D

import pytest

from app.calculo.redondeo import a_porcentaje
from app.calculo.tcea import tcea_en_meses, tcea_fin_de_mes, valor_presente


# --- Juego 1: Rosa Díaz (TEA 30 %) ---
def test_juego1_fin_de_mes():
    assert a_porcentaje(tcea_fin_de_mes(D("45.00"), D("45.36"), 11)) == D("29.7937494")


def test_juego1_licuadora_3_cuotas():
    cuotas = [D("73.71"), D("73.71"), D("73.69")]
    assert a_porcentaje(tcea_en_meses(D("210.00"), 11, cuotas)) == D("29.9801205")


# --- Juego 2: Carlos Mendoza (TEA 34.4888824 %) ---
def test_juego2_licuadora_2_cuotas():
    cuotas = [D("110.40"), D("110.39")]
    assert a_porcentaje(tcea_en_meses(D("210.00"), 16, cuotas)) == D("34.4673515")


def test_juego2_fin_de_mes_5_setiembre():
    assert a_porcentaje(tcea_fin_de_mes(D("180.00"), D("183.14"), 21)) == D("34.5101133")


def test_juego2_fin_de_mes_22_setiembre():
    assert a_porcentaje(tcea_fin_de_mes(D("60.00"), D("61.70"), 34)) == D("34.4239747")


# --- Juego 3: Luis Ramos (TEA 26.8241795 %) — pendiente de confirmar con el profesor ---
@pytest.mark.pendiente_profesor
def test_juego3_fin_de_mes():
    assert a_porcentaje(tcea_fin_de_mes(D("80.00"), D("81.12"), 21)) == D("26.9134938")


@pytest.mark.pendiente_profesor
def test_juego3_plancha_2_cuotas():
    cuotas = [D("62.67"), D("62.67")]
    assert a_porcentaje(tcea_en_meses(D("120.00"), 21, cuotas)) == D("26.8391141")


# --- Propiedades ---
def test_la_tcea_devuelve_el_monto_de_la_compra():
    """Con la TCEA encontrada, el valor presente de las cuotas vuelve a ser C."""
    cuotas = [D("73.71"), D("73.71"), D("73.69")]
    tcea = tcea_en_meses(D("210.00"), 11, cuotas)
    assert abs(valor_presente(cuotas, 11, tcea) - D("210.00")) < D("0.000001")


def test_sin_interes_la_tcea_es_cero():
    assert tcea_fin_de_mes(D("100.00"), D("100.00"), 30) == D("0E-9")
    assert tcea_en_meses(D("100.00"), 0, [D("50.00"), D("50.00")]) == D("0E-9")


def test_datos_invalidos():
    with pytest.raises(ValueError):
        tcea_fin_de_mes(D("0"), D("10"), 10)
    with pytest.raises(ValueError):
        tcea_en_meses(D("100"), 10, [])
