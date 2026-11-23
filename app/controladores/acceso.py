"""Controlador de acceso (Fig. 1): rutas /auth. Solo recibe la petición,
llama al servicio y responde (como `controllers/` en Spring)."""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.config.db import get_db
from app.config.sesion import Sesion, obtener_sesion
from app.dto.acceso import CambioClaveEntrada, LoginEntrada, LoginSalida
from app.servicios import acceso as servicio

router = APIRouter(prefix="/auth", tags=["acceso"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/login", response_model=LoginSalida)
def iniciar_sesion(datos: LoginEntrada, request: Request, db: Session = Depends(get_db)):
    """Inicia sesión y devuelve el token."""
    return servicio.iniciar_sesion(db, datos.username, datos.password, _ip(request))


@router.get("/yo", response_model=Sesion)
def quien_soy(sesion: Sesion = Depends(obtener_sesion)):
    """Devuelve la sesión actual (el frontend la usa para saber qué menú mostrar)."""
    return sesion


@router.post("/cambiar-contrasena", status_code=status.HTTP_204_NO_CONTENT)
def cambiar_contrasena(
    datos: CambioClaveEntrada,
    request: Request,
    sesion: Sesion = Depends(obtener_sesion),
    db: Session = Depends(get_db),
):
    """Cambia la contraseña del usuario que inició sesión."""
    servicio.cambiar_contrasena(
        db, sesion.usuario_id, datos.password_actual, datos.password_nueva, _ip(request)
    )
