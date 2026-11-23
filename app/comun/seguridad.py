"""Contraseñas: se guardan solo como hash (bcrypt), nunca en texto.

bcrypt agrega una "sal" aleatoria, así que dos usuarios con la misma
contraseña tienen hashes distintos. Para verificar no se "descifra" el hash:
se vuelve a calcular con la clave ingresada y se compara.
"""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import get_settings

_ALGORITMO = "HS256"


def hash_password(clave: str) -> str:
    """Devuelve el hash de la contraseña (60 caracteres, cabe en varchar(64))."""
    return bcrypt.hashpw(clave.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_password(clave: str, password_hash: str) -> bool:
    """True si la contraseña ingresada corresponde al hash guardado."""
    return bcrypt.checkpw(clave.encode("utf-8"), password_hash.encode("utf-8"))


# ---------- Tokens de sesión (JWT) ----------
# El token es un texto firmado con JWT_SECRET que el frontend envía en cada
# petición. Si alguien lo modifica, la firma deja de coincidir y se rechaza.


def crear_token(usuario_id: int, rol: str, tienda_id: int | None, cliente_id: int | None) -> str:
    """Crea el token que se entrega al iniciar sesión."""
    s = get_settings()
    datos = {
        "sub": str(usuario_id),
        "rol": rol,
        "tienda_id": tienda_id,
        "cliente_id": cliente_id,
        "exp": datetime.now(UTC) + timedelta(minutes=s.jwt_minutos_expiracion),
    }
    return jwt.encode(datos, s.jwt_secret, algorithm=_ALGORITMO)


def leer_token(token: str) -> dict:
    """Devuelve los datos del token. Lanza jwt.InvalidTokenError si es falso o venció."""
    return jwt.decode(token, get_settings().jwt_secret, algorithms=[_ALGORITMO])
