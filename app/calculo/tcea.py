"""TCEA: Tasa de Costo Efectivo Anual (Ley 29571, art. 91-96; informe 2.2).

Es la tasa anual (año de 360 días) que iguala lo que el cliente recibió (C,
en el día 0 = día de la compra) con lo que paga después.

- Fin de mes:  un solo pago S a los d días    ->  TCEA = (S / C)^(360/d) - 1
- En meses:    cuotas Rk en el día dg + 30k   ->  C = Σ Rk / (1 + TCEA)^((dg + 30k) / 360)
               (es la TIR anual de los flujos; se resuelve por bisección)

Se devuelve en fracción con 9 decimales (RedTasa), igual que las demás tasas.
"""

from decimal import Decimal

from app.calculo.redondeo import dividir, potencia, red_tasa

UNO = Decimal(1)
ANIO = Decimal(360)
MES = 30

# Bisección: se parte el intervalo a la mitad hasta que mide menos que esto.
_TOLERANCIA = Decimal("1e-15")
_MAX_ITERACIONES = 300


def tcea_fin_de_mes(C: Decimal, S: Decimal, d: int) -> Decimal:
    """TCEA de una compra a fin de mes: (S / C)^(360/d) - 1."""
    if C <= 0 or d <= 0:
        raise ValueError("C y d deben ser mayores que 0")
    return red_tasa(potencia(dividir(S, C), dividir(ANIO, Decimal(d))) - UNO)


def valor_presente(cuotas: list[Decimal], dg: int, tasa: Decimal) -> Decimal:
    """Σ Rk / (1 + tasa)^((dg + 30k) / 360), con k = 1..N."""
    total = Decimal(0)
    for k, R in enumerate(cuotas, start=1):
        dias = Decimal(dg + MES * k)
        total += dividir(R, potencia(UNO + tasa, dividir(dias, ANIO)))
    return total


def tcea_en_meses(C: Decimal, dg: int, cuotas: list[Decimal]) -> Decimal:
    """TIR anual de una compra en cuotas: C en el día 0 y cada Rk en el día dg + 30k.

    Bisección: el valor presente BAJA cuando la tasa SUBE. Se busca la tasa
    entre un mínimo y un máximo y en cada paso se queda con la mitad donde
    está la respuesta (VP > C -> la tasa debe subir; VP < C -> debe bajar).
    """
    if C <= 0 or not cuotas:
        raise ValueError("C debe ser mayor que 0 y debe haber al menos una cuota")

    bajo, alto = Decimal("-0.99"), Decimal(1)
    # Si 100 % anual no alcanza, se amplía el máximo (créditos muy caros).
    while valor_presente(cuotas, dg, alto) > C:
        alto *= 2
        if alto > 1000:
            raise ValueError("No se encontró la TCEA")

    for _ in range(_MAX_ITERACIONES):
        medio = (bajo + alto) / 2
        if valor_presente(cuotas, dg, medio) > C:
            bajo = medio
        else:
            alto = medio
        if alto - bajo < _TOLERANCIA:
            break

    return red_tasa((bajo + alto) / 2)
