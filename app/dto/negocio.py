"""Modelos Pydantic (DTOs) para el Dashboard Inicio del Dueño de Negocio (Fig. 6)."""

from datetime import date
from decimal import Decimal
from pydantic import BaseModel

from app.entidades.enums import Moneda


class ProximoVencimientoDTO(BaseModel):
    """Fila de la tarjeta 'Próximos vencimientos' en el inicio del negocio."""

    cliente_id: int
    nombres_apellidos: str
    moneda: Moneda
    monto: Decimal
    fecha_pago: date
    situacion: str  # EN_MORA | CON_DEUDA
    dias_mora: int = 0


class ClienteEnMoraDTO(BaseModel):
    """Tarjeta lateral 'Clientes en mora' en el inicio del negocio."""

    cliente_id: int
    nombres_apellidos: str
    moneda: Moneda
    dias_atraso: int
    monto_vencido: Decimal


class InicioNegocioDTO(BaseModel):
    """Respuesta completa del Dashboard Inicio del Dueño de Negocio (Fig. 6)."""

    tienda_id: int
    nombre_comercial: str
    clientes_activos: int

    # Totales por cobrar separados por moneda (nunca se mezclan PEN y USD)
    total_por_cobrar_pen: Decimal
    total_por_cobrar_usd: Decimal

    # Mora
    clientes_en_mora_count: int

    # Vencen esta semana (próximos 7 días incluyendo hoy)
    vencen_esta_semana_count: int
    vencen_esta_semana_pen: Decimal
    vencen_esta_semana_usd: Decimal

    # Crédito otorgado en el mes calendario actual
    credito_este_mes_pen: Decimal
    credito_este_mes_usd: Decimal
    ventas_este_mes_count: int

    proximos_vencimientos: list[ProximoVencimientoDTO]
    clientes_en_mora: list[ClienteEnMoraDTO]
