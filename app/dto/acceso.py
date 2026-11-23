"""DTO de acceso: datos que entran y salen de las rutas /auth (como `dto/` en Spring)."""

from pydantic import BaseModel

from app.entidades.enums import Rol


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


class CambioClaveEntrada(BaseModel):
    password_actual: str
    password_nueva: str
