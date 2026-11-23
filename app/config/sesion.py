"""Sesión del usuario: quién hace la petición y qué puede ver.

Equivale a `sesion.Tienda` y `sesion.Cliente` del pseudocódigo. Las rutas
toman la tienda o el cliente DE AQUÍ (del token), nunca de lo que envía el
navegador: así una tienda no puede pedir datos de otra.
"""

from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config.seguridad import leer_token
from app.config.db import get_db
from app.entidades.enums import Rol
from app.entidades.acceso import Usuario
from app.entidades.tipos import BAJA

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Sesion:
    usuario_id: int
    rol: Rol
    tienda_id: int | None   # solo ADMIN_NEGOCIO y CLIENTE
    cliente_id: int | None  # solo CLIENTE


def motivo_cuenta_inactiva(usuario: Usuario) -> str | None:
    """Devuelve por qué la cuenta no puede entrar, o None si está activa.

    - Usuario dado de baja.
    - Dueño de una tienda dada de baja (Fig. 5).
    - Cliente dado de baja (Fig. 12) o cuya tienda está de baja (Fig. 5).
    """
    if usuario.estado == BAJA:
        return "Cuenta inactiva"
    if usuario.tienda is not None and usuario.tienda.estado == BAJA:
        return "Cuenta inactiva"
    if usuario.cliente is not None and (
        usuario.cliente.estado == BAJA or usuario.cliente.tienda.estado == BAJA
    ):
        return "Cuenta inactiva"
    return None


def sesion_de(usuario: Usuario) -> Sesion:
    """Arma la sesión a partir del usuario (qué tienda o cliente le corresponde)."""
    tienda_id = cliente_id = None
    if usuario.rol == Rol.ADMIN_NEGOCIO and usuario.tienda is not None:
        tienda_id = usuario.tienda.tienda_id
    elif usuario.rol == Rol.CLIENTE and usuario.cliente is not None:
        cliente_id = usuario.cliente.cliente_id
        tienda_id = usuario.cliente.tienda_id
    return Sesion(usuario.usuario_id, usuario.rol, tienda_id, cliente_id)


def obtener_sesion(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Sesion:
    """Lee el token y vuelve a revisar en la base que la cuenta siga activa
    (si dan de baja una tienda, su dueño queda fuera aunque tenga un token vigente)."""
    no_autorizado = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Inicie sesión", headers={"WWW-Authenticate": "Bearer"}
    )
    if credenciales is None:
        raise no_autorizado
    try:
        datos = leer_token(credenciales.credentials)
    except jwt.InvalidTokenError:
        raise no_autorizado

    usuario = db.get(Usuario, int(datos["sub"]))
    if usuario is None:
        raise no_autorizado
    motivo = motivo_cuenta_inactiva(usuario)
    if motivo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, motivo)
    return sesion_de(usuario)


def requiere_rol(*roles: Rol):
    """Candado para una ruta: solo deja pasar a los roles indicados.

    Uso:  def ruta(sesion: Sesion = Depends(requiere_rol(Rol.ADMIN_NEGOCIO))): ...
    """

    def verificar(sesion: Sesion = Depends(obtener_sesion)) -> Sesion:
        if sesion.rol not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Acceso denegado")
        return sesion

    return verificar
