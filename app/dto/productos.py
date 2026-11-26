"""Modelos Pydantic (DTOs) para la gestión del catálogo de productos (Fig. 7 y 8)."""

from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

from app.entidades.enums import FormaVentaProducto, Moneda


class ProductoResumenDTO(BaseModel):
    """Fila del catálogo de productos en la bandeja del negocio (Fig. 7)."""

    producto_id: int
    nombre: str
    descripcion: str | None = None
    marca: str | None = None
    categoria: str | None = None
    proveedor: str | None = None
    unidad_medida: str
    moneda: Moneda
    precio_contado: Decimal
    precio_lista: Decimal
    forma_venta_credito: FormaVentaProducto
    imagen_url: str | None = None
    estado: int

    model_config = ConfigDict(from_attributes=True)


class RegistrarProductoDTO(BaseModel):
    """Datos para crear un nuevo producto en la tienda (Fig. 8)."""

    nombre: str = Field(..., min_length=2, max_length=80, description="Descripción / Nombre del producto")
    descripcion: str | None = Field(default=None, max_length=500)
    marca: str | None = Field(default=None, max_length=40)
    categoria: str | None = Field(default=None, max_length=40)
    proveedor: str | None = Field(default=None, max_length=60)
    unidad_medida: str = Field(default="Unidad", min_length=1, max_length=15)
    moneda: Moneda = Field(default=Moneda.PEN)
    precio_contado: Decimal = Field(..., gt=0, description="Precio al contado en efectivo (mayor a 0)")
    precio_lista: Decimal = Field(..., gt=0, description="Precio de lista para fiado (mayor o igual a contado)")
    forma_venta_credito: FormaVentaProducto = Field(
        default=FormaVentaProducto.FIN_DE_MES,
        description="Modalidad permitida: FIN_DE_MES, EN_MESES o AMBAS",
    )
    imagen_url: str | None = Field(default=None, max_length=255)


class ActualizarProductoDTO(BaseModel):
    """Datos para editar un producto existente de la tienda."""

    nombre: str = Field(..., min_length=2, max_length=80)
    descripcion: str | None = Field(default=None, max_length=500)
    marca: str | None = Field(default=None, max_length=40)
    categoria: str | None = Field(default=None, max_length=40)
    proveedor: str | None = Field(default=None, max_length=60)
    unidad_medida: str = Field(default="Unidad", min_length=1, max_length=15)
    moneda: Moneda = Field(default=Moneda.PEN)
    precio_contado: Decimal = Field(..., gt=0)
    precio_lista: Decimal = Field(..., gt=0)
    forma_venta_credito: FormaVentaProducto = Field(default=FormaVentaProducto.FIN_DE_MES)
    imagen_url: str | None = Field(default=None, max_length=255)
