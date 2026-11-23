"""Manejo de fechas (pseudocódigo 4.1).

REGLA DEL PROYECTO: `dias_entre` es el ÚNICO lugar del código que resta
fechas. Si el profesor cambia el criterio de conteo de días, solo se
modifica esta función (y sus pruebas).
"""

import calendar
from datetime import date


def dias_entre(f1: date, f2: date) -> int:
    """DiasEntre: días calendario reales de f1 a f2 (meses de 28 a 31 días y
    años bisiestos). Equivale a DiaSerial(f2) - DiaSerial(f1) del pseudocódigo.

    Ejemplo: 20/10/2026 -> 05/11/2026 = 16 días.
    """
    return (f2 - f1).days


def dias_del_mes(anio: int, mes: int) -> int:
    """DiasDelMes: 28, 29, 30 o 31 (tiene en cuenta los años bisiestos)."""
    return calendar.monthrange(anio, mes)[1]


def fecha_con_dia(anio: int, mes: int, dia: int) -> date:
    """FechaConDia: arma una fecha válida. Si el día pactado no existe en ese
    mes (por ejemplo 30 en febrero), usa el último día del mes."""
    return date(anio, mes, min(dia, dias_del_mes(anio, mes)))


def sumar_meses(f: date, k: int, dia_pactado: int) -> date:
    """SumarMeses: avanza k meses desde f manteniendo el día pactado."""
    total = (f.year * 12 + f.month - 1) + k
    anio, mes0 = divmod(total, 12)
    return fecha_con_dia(anio, mes0 + 1, dia_pactado)
