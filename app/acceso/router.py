"""Acceso (pseudocódigo 4.2, Fig. 1): inicio de sesión."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.comun.auditoria import registrar_auditoria
from app.comun.seguridad import crear_token, verificar_password
from app.comun.sesion import Sesion, motivo_cuenta_inactiva, obtener_sesion, sesion_de
from app.db import get_db
from app.dominio.enums import Rol
from app.modelos import Usuario

router = APIRouter(prefix="/auth", tags=["acceso"])


class LoginEntrada(BaseModel):
    username: str
    password: str


class LoginSalida(BaseModel):
    access_token: str
    token_type: str = "bearer"
    rol: Rol
    nombres: str
    tienda_id: int | None
    cliente_id: int | None


@router.post("/login", response_model=LoginSalida)
def iniciar_sesion(datos: LoginEntrada, request: Request, db: Session = Depends(get_db)):
    """IniciarSesion: verifica usuario y contraseña y entrega el token."""
    usuario = db.scalar(select(Usuario).where(Usuario.username == datos.username))

    # Mismo mensaje si el usuario no existe o la clave está mal:
    # así no se revela qué usuarios existen.
    if usuario is None or not verificar_password(datos.password, usuario.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña incorrectos")

    motivo = motivo_cuenta_inactiva(usuario)
    if motivo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, motivo)

    sesion = sesion_de(usuario)
    ip = request.client.host if request.client else None
    registrar_auditoria(db, usuario.usuario_id, "LOGIN", "usuarios", usuario.usuario_id, ip)
    db.commit()

    return LoginSalida(
        access_token=crear_token(sesion.usuario_id, sesion.rol.value, sesion.tienda_id, sesion.cliente_id),
        rol=sesion.rol,
        nombres=usuario.nombres,
        tienda_id=sesion.tienda_id,
        cliente_id=sesion.cliente_id,
    )


@router.get("/yo", response_model=Sesion)
def quien_soy(sesion: Sesion = Depends(obtener_sesion)):
    """Devuelve la sesión actual (el frontend la usa para saber qué menú mostrar)."""
    return sesion
