"""Controlador de tiendas (Fig. 2 a 5): rutas /tiendas.

Solo el administrador del sistema (ADMIN_SISTEMA) puede acceder.
"""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.config.db import get_db
from app.config.sesion import Sesion, requiere_rol
from app.dto.tiendas import (
    TiendaActualizarEntrada,
    TiendaCrearEntrada,
    TiendaItem,
    TiendaListadoSalida,
)
from app.entidades.enums import Rol
from app.servicios import tiendas as servicio

router = APIRouter(prefix="/tiendas", tags=["tiendas"])
solo_sistema = requiere_rol(Rol.ADMIN_SISTEMA)


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=TiendaListadoSalida)
def listar_tiendas(
    buscar: str = "",
    giro: str = "",
    estado: str = "TODAS",
    _: Sesion = Depends(solo_sistema),
    db: Session = Depends(get_db),
):
    """Fig. 2: listado de tiendas con KPIs, conteo de clientes y filtros."""
    return servicio.listar_tiendas(db, buscar, giro, estado)


@router.get("/{tienda_id}", response_model=TiendaItem)
def obtener_tienda(
    tienda_id: int,
    _: Sesion = Depends(solo_sistema),
    db: Session = Depends(get_db),
):
    """Obtiene los datos de una tienda específica."""
    return servicio.obtener_tienda(db, tienda_id)


@router.post("", response_model=TiendaItem, status_code=status.HTTP_201_CREATED)
def registrar_tienda(
    datos: TiendaCrearEntrada,
    request: Request,
    sesion: Sesion = Depends(solo_sistema),
    db: Session = Depends(get_db),
):
    """Fig. 3 y 4: registra una nueva tienda y su administrador de negocio."""
    return servicio.registrar_tienda(db, sesion.usuario_id, datos, _ip(request))


@router.put("/{tienda_id}", response_model=TiendaItem)
def actualizar_tienda(
    tienda_id: int,
    datos: TiendaActualizarEntrada,
    request: Request,
    sesion: Sesion = Depends(solo_sistema),
    db: Session = Depends(get_db),
):
    """Fig. 2: edita los datos de una tienda y su dueño."""
    return servicio.actualizar_tienda(db, sesion.usuario_id, tienda_id, datos, _ip(request))


@router.patch("/{tienda_id}/baja", response_model=TiendaItem)
def dar_de_baja_tienda(
    tienda_id: int,
    request: Request,
    sesion: Sesion = Depends(solo_sistema),
    db: Session = Depends(get_db),
):
    """Fig. 5: da de baja lógica una tienda (bloquea dueño y clientes, conserva historial)."""
    return servicio.dar_de_baja_tienda(db, sesion.usuario_id, tienda_id, _ip(request))


@router.patch("/{tienda_id}/activar", response_model=TiendaItem)
def reactivar_tienda(
    tienda_id: int,
    request: Request,
    sesion: Sesion = Depends(solo_sistema),
    db: Session = Depends(get_db),
):
    """Fig. 2 y 5: reactiva una tienda previamente dada de baja."""
    return servicio.reactivar_tienda(db, sesion.usuario_id, tienda_id, _ip(request))
