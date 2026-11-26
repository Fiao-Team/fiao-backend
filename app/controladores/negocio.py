"""Controlador del Dashboard Inicio del Dueño de Negocio (Fig. 6).

Ruta protegida para ADMIN_NEGOCIO.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config.db import get_db
from app.config.sesion import Sesion, requiere_rol
from app.dto.negocio import InicioNegocioDTO
from app.entidades.enums import Rol
from app.servicios import negocio as servicio_negocio
from app.servicios.reloj_sistema import RelojSistema, obtener_reloj

router = APIRouter(prefix="/negocio", tags=["Inicio del Negocio"])


@router.get("/inicio", response_model=InicioNegocioDTO)
def inicio_negocio(
    sesion: Sesion = Depends(requiere_rol(Rol.ADMIN_NEGOCIO)),
    reloj: RelojSistema = Depends(obtener_reloj),
    db: Session = Depends(get_db),
):
    """KPIs, próximos vencimientos y clientes en mora del negocio (Fig. 6)."""
    return servicio_negocio.obtener_inicio_negocio(db, sesion, reloj)
