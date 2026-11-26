"""Modelos Pydantic (DTOs) para la gestión de clientes y límites de crédito (Fig. 9 a 12)."""

from datetime import time
from decimal import Decimal
from pydantic import BaseModel, Field

from app.entidades.enums import CapitalizacionDias, Moneda, PeriodoDias, TipoTasa


class ClienteResumenDTO(BaseModel):
    """Fila de la lista de clientes de la tienda (Fig. 9) y vista detalle."""

    cliente_id: int
    dni: str
    nombres_apellidos: str
    telefono: str
    direccion: str
    username: str | None = None
    email: str | None = None

    moneda: Moneda
    limite_credito: Decimal
    saldo_deudor: Decimal
    disponible: Decimal
    plazo_max_meses: int

    dia_corte: int
    hora_corte: time
    dia_pago: int

    tipo_tasa_comp: TipoTasa
    tasa_compensatoria: Decimal
    periodo_tasa_comp: PeriodoDias
    capitalizacion_comp: CapitalizacionDias | None = None
    tea_comp_porcentaje: Decimal

    tipo_tasa_mora: TipoTasa
    tasa_moratoria: Decimal
    periodo_tasa_mora: PeriodoDias
    capitalizacion_mora: CapitalizacionDias | None = None
    tea_mora_porcentaje: Decimal

    estado: int


class VistaPreviaTasasEntradaDTO(BaseModel):
    """Datos para previsualizar las TEA calculadas y contrastarlas con los topes BCRP (Fig. 10-11)."""

    moneda: Moneda = Field(default=Moneda.PEN)

    tipo_tasa_comp: TipoTasa = Field(default=TipoTasa.EFECTIVA)
    tasa_compensatoria: Decimal
    periodo_tasa_comp: PeriodoDias = Field(default=PeriodoDias.ANUAL)
    capitalizacion_comp: CapitalizacionDias | None = None

    tipo_tasa_mora: TipoTasa = Field(default=TipoTasa.EFECTIVA)
    tasa_moratoria: Decimal
    periodo_tasa_mora: PeriodoDias = Field(default=PeriodoDias.ANUAL)
    capitalizacion_mora: CapitalizacionDias | None = None


class VistaPreviaTasasRespuestaDTO(BaseModel):
    """Resultado de la vista previa de TEA frente a las tasas máximas del BCRP."""

    moneda: Moneda
    tea_comp_porcentaje: Decimal
    tea_mora_porcentaje: Decimal
    tasa_max_comp_bcrp: Decimal
    tasa_max_mora_bcrp: Decimal
    cumple_bcrp: bool


class RegistrarClienteDTO(BaseModel):
    """Datos para registrar un cliente y sus condiciones de crédito (Fig. 10 y 11)."""

    dni: str = Field(..., description="DNI de 8 dígitos numéricos")
    nombres_apellidos: str = Field(..., min_length=2, max_length=80)
    telefono: str = Field(..., description="Teléfono de 9 dígitos numéricos")
    direccion: str = Field(..., min_length=2, max_length=100)

    moneda: Moneda = Field(default=Moneda.PEN)
    limite_credito: Decimal
    plazo_max_meses: int = Field(default=6)

    dia_corte: int
    hora_corte: time = Field(default=time(23, 59))
    dia_pago: int

    tipo_tasa_comp: TipoTasa = Field(default=TipoTasa.EFECTIVA)
    tasa_compensatoria: Decimal
    periodo_tasa_comp: PeriodoDias = Field(default=PeriodoDias.ANUAL)
    capitalizacion_comp: CapitalizacionDias | None = None

    tipo_tasa_mora: TipoTasa = Field(default=TipoTasa.EFECTIVA)
    tasa_moratoria: Decimal
    periodo_tasa_mora: PeriodoDias = Field(default=PeriodoDias.ANUAL)
    capitalizacion_mora: CapitalizacionDias | None = None

    # Cuenta de acceso para el portal del cliente
    username: str = Field(..., min_length=3, max_length=20)
    password: str = Field(..., description="Contraseña inicial (mínimo 8 caracteres)")
    email: str | None = Field(default=None, max_length=100)


class ActualizarClienteDTO(BaseModel):
    """Datos para editar información de contacto y condiciones de crédito de un cliente."""

    dni: str = Field(..., description="DNI de 8 dígitos numéricos")
    nombres_apellidos: str = Field(..., min_length=2, max_length=80)
    telefono: str = Field(..., description="Teléfono de 9 dígitos numéricos")
    direccion: str = Field(..., min_length=2, max_length=100)

    moneda: Moneda = Field(default=Moneda.PEN)
    limite_credito: Decimal
    plazo_max_meses: int

    dia_corte: int
    hora_corte: time = Field(default=time(23, 59))
    dia_pago: int

    tipo_tasa_comp: TipoTasa = Field(default=TipoTasa.EFECTIVA)
    tasa_compensatoria: Decimal
    periodo_tasa_comp: PeriodoDias = Field(default=PeriodoDias.ANUAL)
    capitalizacion_comp: CapitalizacionDias | None = None

    tipo_tasa_mora: TipoTasa = Field(default=TipoTasa.EFECTIVA)
    tasa_moratoria: Decimal
    periodo_tasa_mora: PeriodoDias = Field(default=PeriodoDias.ANUAL)
    capitalizacion_mora: CapitalizacionDias | None = None
