"""Controlador de Catálogo de Productos (Fig. 7 y 8).

Rutas protegidas para ADMIN_NEGOCIO. Solo opera sobre su propia tienda.
"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.config.db import get_db
from app.config.sesion import Sesion, requiere_rol
from app.dto.productos import ActualizarProductoDTO, ProductoResumenDTO, RegistrarProductoDTO
from app.entidades.enums import FormaVentaProducto, Moneda, Rol
from app.servicios import productos as servicio_productos

router = APIRouter(prefix="/productos", tags=["Catálogo de Productos"])


@router.get("", response_model=list[ProductoResumenDTO])
def listar_productos(
    buscar: str | None = Query(None, description="Buscar por nombre, marca o proveedor"),
    categoria: str | None = Query(None, description="Filtrar por categoría"),
    moneda: Moneda | None = Query(None, description="Filtrar por moneda (PEN / USD)"),
    forma_venta: FormaVentaProducto | None = Query(None, description="Filtrar por modalidad de fiado"),
    solo_activos: bool = Query(True, description="Si es True, oculta los productos dados de baja"),
    sesion: Sesion = Depends(requiere_rol(Rol.ADMIN_NEGOCIO)),
    db: Session = Depends(get_db),
):
    """Lista todos los productos del catálogo de la tienda del comerciante (Fig. 7)."""
    return servicio_productos.listar_productos(
        db,
        sesion,
        buscar=buscar,
        categoria=categoria,
        moneda=moneda,
        forma_venta=forma_venta,
        solo_activos=solo_activos,
    )


@router.get("/{producto_id}", response_model=ProductoResumenDTO)
def obtener_producto(
    producto_id: int,
    sesion: Sesion = Depends(requiere_rol(Rol.ADMIN_NEGOCIO)),
    db: Session = Depends(get_db),
):
    """Obtiene el detalle de un producto específico de la tienda."""
    return servicio_productos.obtener_producto(db, sesion, producto_id)


@router.post("", response_model=ProductoResumenDTO, status_code=201)
def registrar_producto(
    dto: RegistrarProductoDTO,
    request: Request,
    sesion: Sesion = Depends(requiere_rol(Rol.ADMIN_NEGOCIO)),
    db: Session = Depends(get_db),
):
    """Registra un nuevo producto en el catálogo de la tienda (Fig. 8)."""
    ip_cliente = request.client.host if request.client else None
    return servicio_productos.registrar_producto(db, sesion, dto, ip_cliente=ip_cliente)


@router.put("/{producto_id}", response_model=ProductoResumenDTO)
def actualizar_producto(
    producto_id: int,
    dto: ActualizarProductoDTO,
    request: Request,
    sesion: Sesion = Depends(requiere_rol(Rol.ADMIN_NEGOCIO)),
    db: Session = Depends(get_db),
):
    """Actualiza la descripción, precios o datos de un producto existente."""
    ip_cliente = request.client.host if request.client else None
    return servicio_productos.actualizar_producto(db, sesion, producto_id, dto, ip_cliente=ip_cliente)


@router.patch("/{producto_id}/baja", response_model=ProductoResumenDTO)
def dar_de_baja_producto(
    producto_id: int,
    request: Request,
    sesion: Sesion = Depends(requiere_rol(Rol.ADMIN_NEGOCIO)),
    db: Session = Depends(get_db),
):
    """Baja lógica de un producto del catálogo (estado = 0)."""
    ip_cliente = request.client.host if request.client else None
    return servicio_productos.dar_de_baja_producto(db, sesion, producto_id, ip_cliente=ip_cliente)


@router.patch("/{producto_id}/activar", response_model=ProductoResumenDTO)
def reactivar_producto(
    producto_id: int,
    request: Request,
    sesion: Sesion = Depends(requiere_rol(Rol.ADMIN_NEGOCIO)),
    db: Session = Depends(get_db),
):
    """Reactiva un producto previamente dado de baja (estado = 1)."""
    ip_cliente = request.client.host if request.client else None
    return servicio_productos.reactivar_producto(db, sesion, producto_id, ip_cliente=ip_cliente)
