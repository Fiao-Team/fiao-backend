"""Redondeo (Anexo A): montos a 2 decimales y tasas a 9 decimales en fracción
(= 7 decimales en porcentaje), siempre "mitad hacia arriba" (HALF_UP).

Se usa Decimal y nunca float: float no puede guardar 0.10 exacto y los
centavos se descuadran.
"""

from decimal import ROUND_HALF_UP, Decimal, localcontext

# Precisión interna de las operaciones (dígitos significativos).
# Es mucho más de lo necesario; el resultado final siempre se redondea.
PRECISION = 40

_DOS_DECIMALES = Decimal("0.01")
_NUEVE_DECIMALES = Decimal("0.000000001")
_SIETE_DECIMALES = Decimal("0.0000001")


def red_monto(x: Decimal) -> Decimal:
    """RedMonto: redondea un monto a 2 decimales."""
    return x.quantize(_DOS_DECIMALES, rounding=ROUND_HALF_UP)


def red_tasa(x: Decimal) -> Decimal:
    """RedTasa: redondea una tasa en fracción a 9 decimales (7 en %)."""
    return x.quantize(_NUEVE_DECIMALES, rounding=ROUND_HALF_UP)


def red_factor(x: Decimal) -> Decimal:
    """Redondea un factor (FRC) a 7 decimales, como en el informe."""
    return x.quantize(_SIETE_DECIMALES, rounding=ROUND_HALF_UP)


def potencia(base: Decimal, exponente: Decimal) -> Decimal:
    """base ^ exponente con alta precisión. Acepta exponentes con decimales,
    por ejemplo (1 + TEA) ^ (11/360)."""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return base ** exponente


def dividir(a: Decimal, b: Decimal) -> Decimal:
    """a / b con alta precisión (sin redondear todavía)."""
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return a / b


def a_porcentaje(tasa: Decimal) -> Decimal:
    """Convierte una tasa en fracción (0.344888824) a % con 7 decimales (34.4888824)."""
    return (tasa * 100).quantize(_SIETE_DECIMALES, rounding=ROUND_HALF_UP)
