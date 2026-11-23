"""Controlador de ventas (Fig. 13 a 19). Solo el administrador del negocio,
y siempre con los datos de SU tienda (sesion.tienda_id)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config.db import get_db
from app.config.sesion import Sesion, requiere_rol
from app.dto.ventas import ClienteBusqueda, ClienteResumen, ProductoVenta, VentaEntrada, VentaResultado
from app.entidades.enums import Rol
from app.servicios import ventas as servicio
from app.servicios.reloj_sistema import RelojSistema, obtener_reloj

router = APIRouter(prefix="/ventas", tags=["ventas"])
solo_negocio = requiere_rol(Rol.ADMIN_NEGOCIO)


@router.get("/clientes", response_model=list[ClienteBusqueda])
def buscar_clientes(
    buscar: str = "", sesion: Sesion = Depends(solo_negocio), db: Session = Depends(get_db)
):
    """Paso 1 (Fig. 13): clientes activos de la tienda por nombre o DNI."""
    return servicio.buscar_clientes(db, sesion.tienda_id, buscar)


@router.get("/clientes/{cliente_id}", response_model=ClienteResumen)
def resumen_cliente(
    cliente_id: int,
    sesion: Sesion = Depends(solo_negocio),
    db: Session = Depends(get_db),
    reloj: RelojSistema = Depends(obtener_reloj),
):
    """Paso 1 (Fig. 13): disponible, corte y fecha de pago que le tocan hoy."""
    return servicio.resumen_cliente(db, sesion.tienda_id, cliente_id, reloj)


@router.get("/productos", response_model=list[ProductoVenta])
def productos(
    cliente_id: int,
    buscar: str = "",
    sesion: Sesion = Depends(solo_negocio),
    db: Session = Depends(get_db),
):
    """Paso 2 (Fig. 14): productos en la moneda del cliente."""
    return servicio.productos_para_cliente(db, sesion.tienda_id, cliente_id, buscar)


@router.post("/vista-previa", response_model=VentaResultado)
def vista_previa(
    datos: VentaEntrada,
    sesion: Sesion = Depends(solo_negocio),
    db: Session = Depends(get_db),
    reloj: RelojSistema = Depends(obtener_reloj),
):
    """Paso 3 (Fig. 15 y 16): calcula intereses, cronograma y TCEA sin guardar."""
    return servicio.vista_previa(db, sesion.tienda_id, datos, reloj)


@router.post("", response_model=VentaResultado, status_code=201)
def registrar_venta(
    datos: VentaEntrada,
    request: Request,
    sesion: Sesion = Depends(solo_negocio),
    db: Session = Depends(get_db),
    reloj: RelojSistema = Depends(obtener_reloj),
):
    """Registra la venta (Fig. 17); rechaza si excede el límite (Fig. 19)."""
    ip = request.client.host if request.client else None
    return servicio.registrar_venta(db, sesion.tienda_id, sesion.usuario_id, datos, reloj, ip)
