"""Conversión de tasas (informe 3.3.2 y pseudocódigo 4.1).

Las tasas se INGRESAN en porcentaje (30 = 30 %) y aquí se dividen entre 100.
Todas las funciones devuelven la tasa en fracción (0.30 = 30 %), redondeada
a 9 decimales.
"""

from decimal import Decimal

from app.calculo.redondeo import dividir, potencia, red_tasa
from app.entidades.enums import CapitalizacionDias, PeriodoDias, TipoTasa

UNO = Decimal(1)
CIEN = Decimal(100)
ANIO = Decimal(360)  # año comercial (Anexo A)


def normalizar_tea(
    tipo: TipoTasa,
    tasa_porcentaje: Decimal,
    periodo: PeriodoDias,
    capitalizacion: CapitalizacionDias | None = None,
) -> Decimal:
    """NormalizarTEA: convierte la tasa pactada en Tasa Efectiva Anual.

    - Nominal:  TEA = (1 + tasa / m) ^ (360 / c) - 1,  con m = p / c
    - Efectiva: TEA = (1 + tasa) ^ (360 / p) - 1

    p = días del período de la tasa; c = días de capitalización.
    """
    tasa = dividir(Decimal(tasa_porcentaje), CIEN)
    p = Decimal(periodo.dias)

    if tipo == TipoTasa.NOMINAL:
        if capitalizacion is None:
            raise ValueError("La tasa nominal necesita su capitalización")
        c = Decimal(capitalizacion.dias)
        m = dividir(p, c)
        return red_tasa(potencia(UNO + dividir(tasa, m), dividir(ANIO, c)) - UNO)

    return red_tasa(potencia(UNO + tasa, dividir(ANIO, p)) - UNO)


def tep(tea: Decimal, dias: int) -> Decimal:
    """TEPd: tasa efectiva de d días a partir de la TEA.
    TEPd = (1 + TEA) ^ (d / 360) - 1. Con d = 30 se obtiene la TEM."""
    return red_tasa(potencia(UNO + tea, dividir(Decimal(dias), ANIO)) - UNO)
