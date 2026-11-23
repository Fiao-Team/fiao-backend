"""Servicio de acceso (pseudocódigo 4.2): la lógica del inicio de sesión y
del cambio de contraseña. No sabe nada de HTTP; si algo falla, lanza ErrorNegocio."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.auditoria import registrar_auditoria
from app.config.seguridad import crear_token, hash_password, verificar_password
from app.config.sesion import motivo_cuenta_inactiva, sesion_de
from app.dto.acceso import LoginSalida
from app.entidades.acceso import Usuario
from app.excepciones.errores import ErrorNegocio

LARGO_MINIMO_CLAVE = 8  # igual que en RegistrarTienda (pseudocódigo 4.3)


def iniciar_sesion(db: Session, username: str, password: str, ip: str | None) -> LoginSalida:
    """IniciarSesion: verifica usuario y contraseña, registra el LOGIN y entrega el token."""
    usuario = db.scalar(select(Usuario).where(Usuario.username == username))

    # Mismo mensaje si el usuario no existe o la clave está mal:
    # así no se revela qué usuarios existen.
    if usuario is None or not verificar_password(password, usuario.password_hash):
        raise ErrorNegocio(401, "Usuario o contraseña incorrectos")

    motivo = motivo_cuenta_inactiva(usuario)
    if motivo:
        raise ErrorNegocio(403, motivo)

    sesion = sesion_de(usuario)
    registrar_auditoria(db, usuario.usuario_id, "LOGIN", "usuarios", usuario.usuario_id, ip)
    db.commit()

    return LoginSalida(
        access_token=crear_token(sesion.usuario_id, sesion.rol.value, sesion.tienda_id, sesion.cliente_id),
        rol=sesion.rol,
        nombres=usuario.nombres,
        tienda_id=sesion.tienda_id,
        cliente_id=sesion.cliente_id,
    )


def cambiar_contrasena(
    db: Session, usuario_id: int, actual: str, nueva: str, ip: str | None
) -> None:
    """Cambia la contraseña del usuario que inició sesión (cualquier rol).

    Los errores usan 400 y no 401: un 401 haría que el frontend cierre la sesión.
    """
    usuario = db.get(Usuario, usuario_id)

    if not verificar_password(actual, usuario.password_hash):
        raise ErrorNegocio(400, "La contraseña actual no es correcta")
    if len(nueva) < LARGO_MINIMO_CLAVE:
        raise ErrorNegocio(400, f"La contraseña nueva debe tener al menos {LARGO_MINIMO_CLAVE} caracteres")
    if nueva == actual:
        raise ErrorNegocio(400, "La contraseña nueva debe ser distinta de la actual")

    usuario.password_hash = hash_password(nueva)
    # No se guardan las contraseñas (ni sus hashes) en la auditoría, solo que hubo un cambio.
    registrar_auditoria(db, usuario.usuario_id, "CAMBIO_CLAVE", "usuarios", usuario.usuario_id, ip)
    db.commit()
