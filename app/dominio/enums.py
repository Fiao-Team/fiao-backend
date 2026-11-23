"""Valores fijos del sistema (equivalen a los Enum del modelo de base de datos)."""

from enum import Enum


class Rol(str, Enum):
    ADMIN_SISTEMA = "ADMIN_SISTEMA"
    ADMIN_NEGOCIO = "ADMIN_NEGOCIO"
    CLIENTE = "CLIENTE"


class Moneda(str, Enum):
    PEN = "PEN"  # Soles
    USD = "USD"  # Dólares


class TipoTasa(str, Enum):
    NOMINAL = "NOMINAL"
    EFECTIVA = "EFECTIVA"


class PeriodoDias(str, Enum):
    """Período de la tasa o de capitalización. `.dias` da su equivalencia en días."""

    DIARIO = "DIARIO"
    QUINCENAL = "QUINCENAL"
    MENSUAL = "MENSUAL"
    BIMESTRAL = "BIMESTRAL"
    TRIMESTRAL = "TRIMESTRAL"
    CUATRIMESTRAL = "CUATRIMESTRAL"
    SEMESTRAL = "SEMESTRAL"
    ANUAL = "ANUAL"

    @property
    def dias(self) -> int:
        return _DIAS_POR_PERIODO[self]


class CapitalizacionDias(str, Enum):
    """Capitalización de una tasa nominal (en el DBML dice DIARIA, no DIARIO)."""

    DIARIA = "DIARIA"
    QUINCENAL = "QUINCENAL"
    MENSUAL = "MENSUAL"
    BIMESTRAL = "BIMESTRAL"
    TRIMESTRAL = "TRIMESTRAL"
    CUATRIMESTRAL = "CUATRIMESTRAL"
    SEMESTRAL = "SEMESTRAL"
    ANUAL = "ANUAL"

    @property
    def dias(self) -> int:
        return _DIAS_POR_PERIODO[self]


_DIAS_POR_PERIODO = {
    CapitalizacionDias.DIARIA: 1,
    CapitalizacionDias.QUINCENAL: 15,
    CapitalizacionDias.MENSUAL: 30,
    CapitalizacionDias.BIMESTRAL: 60,
    CapitalizacionDias.TRIMESTRAL: 90,
    CapitalizacionDias.CUATRIMESTRAL: 120,
    CapitalizacionDias.SEMESTRAL: 180,
    CapitalizacionDias.ANUAL: 360,
    PeriodoDias.DIARIO: 1,
    PeriodoDias.QUINCENAL: 15,
    PeriodoDias.MENSUAL: 30,
    PeriodoDias.BIMESTRAL: 60,
    PeriodoDias.TRIMESTRAL: 90,
    PeriodoDias.CUATRIMESTRAL: 120,
    PeriodoDias.SEMESTRAL: 180,
    PeriodoDias.ANUAL: 360,
}


class FormaVentaProducto(str, Enum):
    FIN_DE_MES = "FIN_DE_MES"
    EN_MESES = "EN_MESES"
    AMBAS = "AMBAS"


class ModalidadPago(str, Enum):
    FIN_DE_MES = "FIN_DE_MES"
    EN_MESES = "EN_MESES"


class EstadoTransaccion(str, Enum):
    PENDIENTE = "PENDIENTE"
    PAGADA = "PAGADA"
    ANULADA = "ANULADA"


class EstadoCuota(str, Enum):
    PENDIENTE = "PENDIENTE"
    PAGADA = "PAGADA"
    VENCIDA = "VENCIDA"


class EstadoListado(str, Enum):
    PENDIENTE = "PENDIENTE"
    PAGADO = "PAGADO"
    VENCIDO = "VENCIDO"
