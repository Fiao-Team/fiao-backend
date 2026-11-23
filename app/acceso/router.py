"""Acceso (pseudocódigo 4.2, Fig. 1): inicio de sesión y cambio de contraseña."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.comun.auditoria import registrar_auditoria
from app.comun.seguridad import crear_token, hash_password, verificar_password
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


# ---------- Cambiar contraseña (menú del usuario, Fig. 2) ----------

LARGO_MINIMO_CLAVE = 8  # igual que en RegistrarTienda (pseudocódigo 4.3)


class CambioClaveEntrada(BaseModel):
    password_actual: str
    password_nueva: str


@router.post("/cambiar-contrasena", status_code=status.HTTP_204_NO_CONTENT)
def cambiar_contrasena(
    datos: CambioClaveEntrada,
    request: Request,
    sesion: Sesion = Depends(obtener_sesion),
    db: Session = Depends(get_db),
):
    """Cambia la contraseña del usuario que inició sesión (cualquier rol).

    Los errores usan 400 y no 401: un 401 haría que el frontend cierre la sesión.
    """
    usuario = db.get(Usuario, sesion.usuario_id)

    if not verificar_password(datos.password_actual, usuario.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La contraseña actual no es correcta")
    if len(datos.password_nueva) < LARGO_MINIMO_CLAVE:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"La contraseña nueva debe tener al menos {LARGO_MINIMO_CLAVE} caracteres",
        )
    if datos.password_nueva == datos.password_actual:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "La contraseña nueva debe ser distinta de la actual"
        )

    usuario.password_hash = hash_password(datos.password_nueva)
    ip = request.client.host if request.client else None
    # No se guardan las contraseñas (ni sus hashes) en la auditoría, solo que hubo un cambio.
    registrar_auditoria(db, usuario.usuario_id, "CAMBIO_CLAVE", "usuarios", usuario.usuario_id, ip)
    db.commit()
