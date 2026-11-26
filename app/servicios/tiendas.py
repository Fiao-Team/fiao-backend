"""Servicio de tiendas (pseudocódigo 4.3, Fig. 2 a 5).

Solo el administrador del sistema (ADMIN_SISTEMA) usa estas operaciones:
listar con KPIs y filtros, registrar con validaciones por campo, editar,
dar de baja lógica y reactivar tiendas.
"""

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.config.auditoria import registrar_auditoria
from app.config.seguridad import hash_password
from app.dto.tiendas import (
    TiendaActualizarEntrada,
    TiendaCrearEntrada,
    TiendaItem,
    TiendaListadoSalida,
    TiendaResumen,
)
from app.entidades.acceso import Tienda, Usuario
from app.entidades.catalogo import Cliente
from app.entidades.enums import Rol
from app.entidades.tipos import ACTIVO, BAJA
from app.excepciones.errores import ErrorNegocio

LARGO_MINIMO_CLAVE = 8
LARGO_MINIMO_USUARIO = 3


def _limpiar(texto: str | None) -> str:
    return (texto or "").strip()


def _a_item(tienda: Tienda, clientes_count: int) -> TiendaItem:
    return TiendaItem(
        tienda_id=tienda.tienda_id,
        nombre_comercial=tienda.nombre_comercial,
        razon_social=tienda.razon_social,
        ruc=tienda.ruc,
        giro=tienda.giro,
        direccion=tienda.direccion,
        distrito=tienda.distrito,
        telefono=tienda.telefono,
        dueno_dni=tienda.dueno_dni,
        dueno_nombres=tienda.admin.nombres,
        dueno_email=tienda.admin.email,
        dueno_username=tienda.admin.username,
        moneda_defecto=tienda.moneda_defecto,
        logo_url=tienda.logo_url,
        estado=tienda.estado,
        clientes_count=clientes_count,
    )


def _contar_clientes(db: Session, tienda_id: int) -> int:
    return db.scalar(
        select(func.count(Cliente.cliente_id)).where(Cliente.tienda_id == tienda_id)
    ) or 0


def _buscar_tienda(db: Session, tienda_id: int) -> Tienda:
    tienda = db.scalar(
        select(Tienda).options(joinedload(Tienda.admin)).where(Tienda.tienda_id == tienda_id)
    )
    if tienda is None:
        raise ErrorNegocio(404, "Tienda no encontrada")
    return tienda


def _validar_datos(
    db: Session,
    datos: TiendaCrearEntrada | TiendaActualizarEntrada,
    tienda_id_actual: int | None = None,
    usuario_id_actual: int | None = None,
) -> dict[str, str]:
    """Valida todos los campos del formulario (Fig. 3 y 4) y acumula errores por campo."""
    errores: dict[str, str] = {}

    nombre = _limpiar(datos.nombre_comercial)
    ruc = _limpiar(datos.ruc)
    direccion = _limpiar(datos.direccion)
    distrito = _limpiar(datos.distrito)
    telefono = _limpiar(datos.telefono)
    giro = _limpiar(datos.giro)
    dueno_nombres = _limpiar(datos.dueno_nombres)
    dueno_dni = _limpiar(datos.dueno_dni)
    dueno_email = _limpiar(datos.dueno_email)

    if not nombre:
        errores["nombre_comercial"] = "Ingresa el nombre comercial"
    elif len(nombre) > 60:
        errores["nombre_comercial"] = "Máximo 60 caracteres"

    if len(ruc) != 11 or not ruc.isdigit() or not ruc.startswith(("10", "20")):
        errores["ruc"] = "Debe tener 11 dígitos y empezar con 10 o 20"
    else:
        consulta_ruc = select(Tienda.tienda_id).where(Tienda.ruc == ruc)
        if tienda_id_actual is not None:
            consulta_ruc = consulta_ruc.where(Tienda.tienda_id != tienda_id_actual)
        if db.scalar(consulta_ruc) is not None:
            errores["ruc"] = "RUC ya registrado"

    if not direccion:
        errores["direccion"] = "Ingresa la dirección"
    elif len(direccion) > 200:
        errores["direccion"] = "Máximo 200 caracteres"

    if not distrito:
        errores["distrito"] = "Ingresa el distrito"
    elif len(distrito) > 60:
        errores["distrito"] = "Máximo 60 caracteres"

    if len(telefono) != 9 or not telefono.isdigit():
        errores["telefono"] = "Debe tener 9 dígitos"

    if not giro:
        errores["giro"] = "Selecciona un giro"
    elif len(giro) > 40:
        errores["giro"] = "Máximo 40 caracteres"

    if not dueno_nombres:
        errores["dueno_nombres"] = "Ingresa nombres y apellidos"
    elif len(dueno_nombres) > 80:
        errores["dueno_nombres"] = "Máximo 80 caracteres"

    if len(dueno_dni) != 8 or not dueno_dni.isdigit():
        errores["dueno_dni"] = "Debe tener 8 dígitos"

    email_normalizado = dueno_email
    if not dueno_email:
        errores["dueno_email"] = "Ingresa un correo válido"
    else:
        try:
            email_normalizado = validate_email(dueno_email, check_deliverability=False).normalized
        except EmailNotValidError:
            errores["dueno_email"] = "Ingresa un correo válido"
        else:
            if len(email_normalizado) > 100:
                errores["dueno_email"] = "Máximo 100 caracteres"
            else:
                consulta_email = select(Usuario.usuario_id).where(Usuario.email == email_normalizado)
                if usuario_id_actual is not None:
                    consulta_email = consulta_email.where(Usuario.usuario_id != usuario_id_actual)
                if db.scalar(consulta_email) is not None:
                    errores["dueno_email"] = "Correo ya registrado"

    limpios = {
        "nombre_comercial": nombre,
        "ruc": ruc,
        "direccion": direccion,
        "distrito": distrito,
        "telefono": telefono,
        "giro": giro,
        "dueno_nombres": dueno_nombres,
        "dueno_dni": dueno_dni,
        "dueno_email": email_normalizado,
    }

    if isinstance(datos, TiendaCrearEntrada):
        username = _limpiar(datos.username)
        if len(username) < LARGO_MINIMO_USUARIO:
            errores["username"] = f"Mínimo {LARGO_MINIMO_USUARIO} caracteres"
        elif " " in username:
            errores["username"] = "El usuario no debe contener espacios"
        elif len(username) > 20:
            errores["username"] = "Máximo 20 caracteres"
        elif db.scalar(select(Usuario.usuario_id).where(Usuario.username == username)) is not None:
            errores["username"] = "Usuario ya existe"

        if len(datos.password) < LARGO_MINIMO_CLAVE:
            errores["password"] = f"Mínimo {LARGO_MINIMO_CLAVE} caracteres"

        limpios["username"] = username

    if errores:
        primer_mensaje = next(iter(errores.values()))
        raise ErrorNegocio(400, primer_mensaje, errores=errores)

    return limpios


# ---------- Listar (Fig. 2) ----------


def listar_tiendas(
    db: Session, buscar: str = "", giro: str = "", estado: str = "TODAS"
) -> TiendaListadoSalida:
    """ListarTiendas: KPIs globales, giros disponibles y tiendas filtradas con conteo de clientes."""
    total = db.scalar(select(func.count(Tienda.tienda_id))) or 0
    activas = db.scalar(select(func.count(Tienda.tienda_id)).where(Tienda.estado == ACTIVO)) or 0
    inactivas = total - activas

    giros = [
        g
        for g in db.scalars(
            select(Tienda.giro).where(Tienda.giro.is_not(None)).distinct().order_by(Tienda.giro)
        ).all()
        if g
    ]

    conteo = (
        select(Cliente.tienda_id, func.count(Cliente.cliente_id).label("clientes_count"))
        .group_by(Cliente.tienda_id)
        .subquery()
    )
    consulta = (
        select(Tienda, func.coalesce(conteo.c.clientes_count, 0))
        .options(joinedload(Tienda.admin))
        .outerjoin(conteo, Tienda.tienda_id == conteo.c.tienda_id)
    )

    texto = _limpiar(buscar)
    if texto:
        consulta = consulta.where(
            or_(Tienda.nombre_comercial.ilike(f"%{texto}%"), Tienda.ruc.like(f"%{texto}%"))
        )

    giro_limpio = _limpiar(giro)
    if giro_limpio and giro_limpio.upper() != "TODOS":
        consulta = consulta.where(Tienda.giro == giro_limpio)

    estado_norm = _limpiar(estado).upper()
    if estado_norm in ("ACTIVA", "ACTIVAS", "1"):
        consulta = consulta.where(Tienda.estado == ACTIVO)
    elif estado_norm in ("INACTIVA", "INACTIVAS", "BAJA", "0"):
        consulta = consulta.where(Tienda.estado == BAJA)

    filas = db.execute(consulta.order_by(Tienda.nombre_comercial)).all()
    return TiendaListadoSalida(
        resumen=TiendaResumen(total=total, activas=activas, inactivas=inactivas),
        giros=giros,
        tiendas=[_a_item(tienda, int(clientes_count)) for tienda, clientes_count in filas],
    )


def obtener_tienda(db: Session, tienda_id: int) -> TiendaItem:
    """Detalle de una tienda para edición o consulta."""
    tienda = _buscar_tienda(db, tienda_id)
    return _a_item(tienda, _contar_clientes(db, tienda.tienda_id))


# ---------- Registrar (Fig. 3 y 4) ----------


def registrar_tienda(
    db: Session, usuario_id: int, datos: TiendaCrearEntrada, ip: str | None = None
) -> TiendaItem:
    """RegistrarTienda: valida, crea el dueño (ADMIN_NEGOCIO) y la tienda en una transacción."""
    limpios = _validar_datos(db, datos)

    dueno = Usuario(
        username=limpios["username"],
        password_hash=hash_password(datos.password),
        email=limpios["dueno_email"],
        nombres=limpios["dueno_nombres"],
        rol=Rol.ADMIN_NEGOCIO,
        estado=ACTIVO,
    )
    db.add(dueno)
    db.flush()

    tienda = Tienda(
        admin_usuario_id=dueno.usuario_id,
        nombre_comercial=limpios["nombre_comercial"],
        razon_social=_limpiar(datos.razon_social) or None,
        ruc=limpios["ruc"],
        giro=limpios["giro"],
        direccion=limpios["direccion"],
        distrito=limpios["distrito"],
        telefono=limpios["telefono"],
        dueno_dni=limpios["dueno_dni"],
        moneda_defecto=datos.moneda_defecto,
        logo_url=_limpiar(datos.logo_url) or None,
        estado=ACTIVO,
    )
    db.add(tienda)
    db.flush()

    registrar_auditoria(
        db,
        usuario_id,
        "ALTA",
        "tiendas",
        tienda.tienda_id,
        ip,
        datos_nuevos={
            "nombre_comercial": tienda.nombre_comercial,
            "ruc": tienda.ruc,
            "giro": tienda.giro,
            "dueno_username": dueno.username,
        },
    )
    db.commit()
    tienda.admin = dueno
    return _a_item(tienda, 0)


# ---------- Editar (Fig. 2) ----------


def actualizar_tienda(
    db: Session,
    usuario_id: int,
    tienda_id: int,
    datos: TiendaActualizarEntrada,
    ip: str | None = None,
) -> TiendaItem:
    """Edita los datos de una tienda y su dueño conservando el historial."""
    tienda = _buscar_tienda(db, tienda_id)
    limpios = _validar_datos(
        db, datos, tienda_id_actual=tienda.tienda_id, usuario_id_actual=tienda.admin_usuario_id
    )

    anteriores = {
        "nombre_comercial": tienda.nombre_comercial,
        "ruc": tienda.ruc,
        "giro": tienda.giro,
        "direccion": tienda.direccion,
        "distrito": tienda.distrito,
        "telefono": tienda.telefono,
        "dueno_dni": tienda.dueno_dni,
        "dueno_nombres": tienda.admin.nombres,
        "dueno_email": tienda.admin.email,
    }

    tienda.nombre_comercial = limpios["nombre_comercial"]
    tienda.razon_social = _limpiar(datos.razon_social) or None
    tienda.ruc = limpios["ruc"]
    tienda.giro = limpios["giro"]
    tienda.direccion = limpios["direccion"]
    tienda.distrito = limpios["distrito"]
    tienda.telefono = limpios["telefono"]
    tienda.dueno_dni = limpios["dueno_dni"]
    tienda.moneda_defecto = datos.moneda_defecto
    tienda.logo_url = _limpiar(datos.logo_url) or None

    tienda.admin.nombres = limpios["dueno_nombres"]
    tienda.admin.email = limpios["dueno_email"]

    nuevos = {
        "nombre_comercial": tienda.nombre_comercial,
        "ruc": tienda.ruc,
        "giro": tienda.giro,
        "direccion": tienda.direccion,
        "distrito": tienda.distrito,
        "telefono": tienda.telefono,
        "dueno_dni": tienda.dueno_dni,
        "dueno_nombres": tienda.admin.nombres,
        "dueno_email": tienda.admin.email,
    }
    registrar_auditoria(
        db,
        usuario_id,
        "EDICION",
        "tiendas",
        tienda.tienda_id,
        ip,
        datos_anteriores=anteriores,
        datos_nuevos=nuevos,
    )
    db.commit()
    return _a_item(tienda, _contar_clientes(db, tienda.tienda_id))


# ---------- Baja lógica y reactivación (Fig. 2 y Fig. 5) ----------


def dar_de_baja_tienda(
    db: Session, usuario_id: int, tienda_id: int, ip: str | None = None
) -> TiendaItem:
    """DarDeBajaTienda: baja lógica (estado = 0). Bloquea dueño y clientes, conserva historial."""
    tienda = _buscar_tienda(db, tienda_id)
    if tienda.estado == BAJA:
        raise ErrorNegocio(400, "La tienda ya está dada de baja")

    tienda.estado = BAJA
    registrar_auditoria(
        db,
        usuario_id,
        "BAJA",
        "tiendas",
        tienda.tienda_id,
        ip,
        datos_anteriores={"estado": ACTIVO},
        datos_nuevos={"estado": BAJA},
    )
    db.commit()
    return _a_item(tienda, _contar_clientes(db, tienda.tienda_id))


def reactivar_tienda(
    db: Session, usuario_id: int, tienda_id: int, ip: str | None = None
) -> TiendaItem:
    """Reactiva una tienda dada de baja (acción Reactivar en Fig. 2 y mensaje de Fig. 5)."""
    tienda = _buscar_tienda(db, tienda_id)
    if tienda.estado == ACTIVO:
        raise ErrorNegocio(400, "La tienda ya está activa")

    tienda.estado = ACTIVO
    registrar_auditoria(
        db,
        usuario_id,
        "REACTIVACION",
        "tiendas",
        tienda.tienda_id,
        ip,
        datos_anteriores={"estado": BAJA},
        datos_nuevos={"estado": ACTIVO},
    )
    db.commit()
    return _a_item(tienda, _contar_clientes(db, tienda.tienda_id))
