"""RegistrarAuditoria (pseudocódigo 4.1): el enunciado pide registrar todas
las operaciones en la tabla auditoria_sistema."""

from sqlalchemy.orm import Session

from app.entidades.acceso import AuditoriaSistema


def registrar_auditoria(
    db: Session,
    usuario_id: int | None,  # None cuando la operación la hace el sistema (corte automático)
    accion: str,             # LOGIN, ALTA, BAJA, VENTA, PAGO, LISTADO...
    tabla: str,
    registro_id: int | None,
    ip: str | None = None,
    datos_anteriores: dict | None = None,
    datos_nuevos: dict | None = None,
) -> None:
    """Agrega el registro a la sesión de base de datos.

    No hace commit: se guarda junto con la operación que audita, así nunca
    queda una operación sin su auditoría (ni una auditoría sin operación).
    """
    db.add(
        AuditoriaSistema(
            usuario_id=usuario_id,
            accion=accion,
            tabla_afectada=tabla,
            registro_id=registro_id,
            ip_address=ip,
            datos_anteriores=datos_anteriores,
            datos_nuevos=datos_nuevos,
        )
    )
