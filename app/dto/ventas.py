"""DTO de ventas (Fig. 13 a 19): datos que entran y salen de las rutas /ventas.

Las tasas salen en PORCENTAJE con 7 decimales (ej. 30.0000000); los montos con 2.
"""

from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, Field

from app.entidades.enums import FormaVentaProducto, ModalidadPago, Moneda

# ---------- Paso 1: cliente (Fig. 13) ----------


class ClienteBusqueda(BaseModel):
    cliente_id: int
    nombres_apellidos: str
    dni: str
    moneda: Moneda


class ClienteResumen(BaseModel):
    cliente_id: int
    nombres_apellidos: str
    dni: str
    moneda: Moneda
    limite_credito: Decimal
    saldo_deudor: Decimal
    disponible: Decimal
    plazo_max_meses: int
    dia_corte: int
    hora_corte: time
    dia_pago: int
    fecha_corte: datetime          # corte que le toca a una compra hecha ahora
    fecha_pago: date               # fecha de pago de ese corte
    posterior_al_corte: bool


# ---------- Paso 2: productos (Fig. 14) ----------


class ProductoVenta(BaseModel):
    producto_id: int
    nombre: str
    marca: str | None
    unidad_medida: str
    moneda: Moneda
    precio_lista: Decimal
    forma_venta_credito: FormaVentaProducto
    imagen_url: str | None


# ---------- Paso 3 y registro: lo que envía el frontend ----------


class ItemVenta(BaseModel):
    producto_id: int
    cantidad: Decimal = Field(max_digits=8, decimal_places=3)
    modalidad: ModalidadPago


class VentaEntrada(BaseModel):
    cliente_id: int
    items: list[ItemVenta]
    cuotas: int | None = None  # N: solo si hay productos en meses


# ---------- Resultado (vista previa y venta registrada) ----------


class LineaVenta(BaseModel):
    producto_id: int
    nombre: str
    cantidad: Decimal
    precio_unitario: Decimal
    subtotal: Decimal


class CuotaVista(BaseModel):
    numero: int
    vencimiento: date
    saldo_inicial: Decimal
    interes: Decimal
    amortizacion: Decimal
    cuota: Decimal
    saldo_final: Decimal


class GrupoVenta(BaseModel):
    """Una compra (transacción): todos los productos de una misma modalidad."""

    modalidad: ModalidadPago
    transaccion_id: int | None = None  # solo cuando se registró
    lineas: list[LineaVenta]
    C: Decimal                         # monto de la compra
    dias: int                          # d (fin de mes) o dg (días de gracia, en meses)
    tep: Decimal                       # % de los d / dg días
    interes: Decimal                   # interés total del grupo
    total: Decimal                     # S (fin de mes) o suma de cuotas (en meses)
    tcea: Decimal                      # %
    # Solo en meses:
    cuotas: int | None = None          # N
    C_prima: Decimal | None = None     # deuda capitalizada
    tem: Decimal | None = None         # %
    frc: Decimal | None = None
    R: Decimal | None = None
    cronograma: list[CuotaVista] = []


class VentaResultado(BaseModel):
    cliente_id: int
    moneda: Moneda
    fecha_compra: datetime
    fecha_corte: datetime
    fecha_pago: date
    posterior_al_corte: bool
    aviso: str | None                  # "Compra posterior al corte: se paga el ..." (Fig. 18)
    tea: Decimal                       # % TEA compensatoria aplicada
    total_capital: Decimal             # C_total
    total_a_pagar: Decimal             # suma de S y de las cuotas
    disponible: Decimal                # antes de la venta
    disponible_despues: Decimal
    aprobado: bool                     # False si excede el límite (Fig. 19)
    mensaje_limite: str | None
    grupos: list[GrupoVenta]
