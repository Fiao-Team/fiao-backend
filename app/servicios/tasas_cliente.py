"""TEAComp y TEAMora (pseudocódigo 4.1): la TEA de las tasas pactadas con el cliente."""

from decimal import Decimal

from app.calculo.tasas import normalizar_tea
from app.entidades.catalogo import Cliente


def tea_comp(cliente: Cliente) -> Decimal:
    """TEA compensatoria del cliente, en fracción (0.344888824 = 34.4888824 %)."""
    return normalizar_tea(
        cliente.tipo_tasa_comp,
        cliente.tasa_compensatoria,
        cliente.periodo_tasa_comp,
        cliente.capitalizacion_comp,
    )


def tea_mora(cliente: Cliente) -> Decimal:
    """TEA moratoria del cliente, en fracción."""
    return normalizar_tea(
        cliente.tipo_tasa_mora,
        cliente.tasa_moratoria,
        cliente.periodo_tasa_mora,
        cliente.capitalizacion_mora,
    )
