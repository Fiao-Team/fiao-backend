"""Controlador de Gestión de Clientes, Límites de Crédito y Estado de Cuenta (Fig. 9 a 12).

Rutas protegidas para ADMIN_NEGOCIO. Opera estrictamente sobre la tienda de la sesión.
"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.config.db import get_db
from app.config.sesion import Sesion, requiere_rol
from app.dto.clientes import (
    ActualizarClienteDTO,
    ClienteResumenDTO,
    EstadoCuentaClienteDTO,
    RegistrarClienteDTO,
    VistaPreviaTasasEntradaDTO,
    VistaPreviaTasasRespuestaDTO,
)
from app.entidades.enums import Moneda, Rol
from app.servicios import clientes as servicio_clientes
from app.servicios.reloj_sistema import RelojSistema, obtener_reloj

router = APIRouter(prefix="/clientes", tags=["Gestión de Clientes"])


@router.get("", response_model=list[ClienteResumenDTO])
def listar_clientes(
    buscar: str | None = Query(None, description="Buscar por nombre, DNI o teléfono"),
    moneda: Moneda | None = Query(None, description="Filtrar por moneda (PEN / USD)"),
    situacion: str | None = Query(
        None, description="Filtrar por situación: AL_DIA, CON_DEUDA, EN_MORA, INACTIVO"
    ),
    solo_activos: bool = Query(True, description="Si es True, oculta clientes dados de baja"),
    sesion: Sesion = Depends(requiere_rol(Rol.ADMIN_NEGOCIO)),
    reloj: RelojSistema = Depends(obtener_reloj),
    db: Session = Depends(get_db),
):
    """Lista los clientes de la tienda con límite, saldo usado, disponible y situación (Fig. 9)."""
    return servicio_clientes.listar_clientes(
        db,
        sesion,
        reloj,
        buscar=buscar,
        moneda=moneda,
        situacion=situacion,
        solo_activos=solo_activos,
    )


@router.post("/vista-previa-tasas", response_model=VistaPreviaTasasRespuestaDTO)
def vista_previa_tasas(
    dto: VistaPreviaTasasEntradaDTO,
    _: Sesion = Depends(requiere_rol(Rol.ADMIN_NEGOCIO)),
    reloj: RelojSistema = Depends(obtener_reloj),
    db: Session = Depends(get_db),
):
    """Calcula la TEA compensatoria y moratoria y las contrasta con el tope vigente del BCRP."""
    return servicio_clientes.vista_previa_tasas(db, reloj, dto)


@router.get("/{cliente_id}", response_model=ClienteResumenDTO)
def obtener_cliente(
    cliente_id: int,
    sesion: Sesion = Depends(requiere_rol(Rol.ADMIN_NEGOCIO)),
    reloj: RelojSistema = Depends(obtener_reloj),
    db: Session = Depends(get_db),
):
    """Obtiene el detalle y condiciones de crédito de un cliente de la tienda."""
    return servicio_clientes.obtener_cliente(db, sesion, reloj, cliente_id)


@router.get("/{cliente_id}/estado-cuenta", response_model=EstadoCuentaClienteDTO)
def obtener_estado_cuenta(
    cliente_id: int,
    sesion: Sesion = Depends(requiere_rol(Rol.ADMIN_NEGOCIO)),
    reloj: RelojSistema = Depends(obtener_reloj),
    db: Session = Depends(get_db),
):
    """Devuelve el estado de cuenta completo del cliente: Movimientos, Cuotas y Pagos."""
    return servicio_clientes.obtener_estado_cuenta(db, sesion, reloj, cliente_id)


@router.post("", response_model=ClienteResumenDTO, status_code=201)
def registrar_cliente(
    dto: RegistrarClienteDTO,
    request: Request,
    sesion: Sesion = Depends(requiere_rol(Rol.ADMIN_NEGOCIO)),
    reloj: RelojSistema = Depends(obtener_reloj),
    db: Session = Depends(get_db),
):
    """Registra un nuevo cliente, valida topes BCRP y crea su usuario de acceso (Fig. 10 y 11)."""
    ip_cliente = request.client.host if request.client else None
    return servicio_clientes.registrar_cliente(db, sesion, reloj, dto, ip_cliente=ip_cliente)


@router.put("/{cliente_id}", response_model=ClienteResumenDTO)
def actualizar_cliente(
    cliente_id: int,
    dto: ActualizarClienteDTO,
    request: Request,
    sesion: Sesion = Depends(requiere_rol(Rol.ADMIN_NEGOCIO)),
    reloj: RelojSistema = Depends(obtener_reloj),
    db: Session = Depends(get_db),
):
    """Actualiza los datos y condiciones de crédito de un cliente de la tienda."""
    ip_cliente = request.client.host if request.client else None
    return servicio_clientes.actualizar_cliente(
        db, sesion, reloj, cliente_id, dto, ip_cliente=ip_cliente
    )


@router.patch("/{cliente_id}/baja", response_model=ClienteResumenDTO)
def dar_de_baja_cliente(
    cliente_id: int,
    request: Request,
    sesion: Sesion = Depends(requiere_rol(Rol.ADMIN_NEGOCIO)),
    reloj: RelojSistema = Depends(obtener_reloj),
    db: Session = Depends(get_db),
):
    """Baja lógica de un cliente (Fig. 12). Rechaza si tiene saldo deudor pendiente."""
    ip_cliente = request.client.host if request.client else None
    return servicio_clientes.dar_de_baja_cliente(
        db, sesion, reloj, cliente_id, ip_cliente=ip_cliente
    )


@router.patch("/{cliente_id}/activar", response_model=ClienteResumenDTO)
def reactivar_cliente(
    cliente_id: int,
    request: Request,
    sesion: Sesion = Depends(requiere_rol(Rol.ADMIN_NEGOCIO)),
    reloj: RelojSistema = Depends(obtener_reloj),
    db: Session = Depends(get_db),
):
    """Reactiva un cliente previamente dado de baja (`estado = 1`)."""
    ip_cliente = request.client.host if request.client else None
    return servicio_clientes.reactivar_cliente(
        db, sesion, reloj, cliente_id, ip_cliente=ip_cliente
    )
