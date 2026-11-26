"""Servicio de Gestión de Clientes y Límites de Crédito (pseudocódigo 4.4, Fig. 9 a 12).

Reglas del dominio:
- Aislamiento estricto por tienda (`sesion.tienda_id`).
- Usa `RelojSistema` para la fecha del negocio (saldos y vigencia BCRP).
- Valida tasas normalizadas a TEA contra `tasas_maximas_bcrp` vigente para la moneda.
- Impide dar de baja a un cliente si `SaldoDeudor > 0` ("El cliente tiene deuda pendiente").
- Registra auditoría en la misma transacción (ALTA, EDICION, BAJA, REACTIVACION).
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculo.redondeo import a_porcentaje
from app.calculo.tasas import normalizar_tea
from app.config.auditoria import registrar_auditoria
from app.config.seguridad import hash_password
from app.config.sesion import Sesion
from app.dto.clientes import (
    ActualizarClienteDTO,
    ClienteResumenDTO,
    RegistrarClienteDTO,
    VistaPreviaTasasEntradaDTO,
    VistaPreviaTasasRespuestaDTO,
)
from app.entidades.acceso import Usuario
from app.entidades.catalogo import Cliente
from app.entidades.configuracion import TasaMaximaBcrp
from app.entidades.enums import (
    CapitalizacionDias,
    Moneda,
    PeriodoDias,
    Rol,
    TipoTasa,
)
from app.entidades.tipos import ACTIVO, BAJA
from app.excepciones.errores import ErrorNegocio, NoEncontrado
from app.servicios.reloj_sistema import RelojSistema
from app.servicios.saldos import saldo_deudor_cliente
from app.servicios.tasas_cliente import tea_comp, tea_mora


def _obtener_tasa_bcrp_vigente(db: Session, moneda: Moneda, hoy: date) -> TasaMaximaBcrp:
    """Busca la tasa máxima del BCRP vigente para la moneda en la fecha del negocio."""
    tasa_bcrp = db.scalar(
        select(TasaMaximaBcrp).where(
            TasaMaximaBcrp.moneda == moneda,
            TasaMaximaBcrp.vigente_desde <= hoy,
            TasaMaximaBcrp.vigente_hasta >= hoy,
        )
    )
    if tasa_bcrp is None:
        raise ErrorNegocio(
            f"No hay tasa máxima del BCRP vigente para {moneda.value} en la fecha {hoy.isoformat()}."
        )
    return tasa_bcrp


def _validar_tasas_y_calcular_tea(
    db: Session,
    *,
    moneda: Moneda,
    tipo_tasa_comp: TipoTasa,
    tasa_compensatoria: Decimal,
    periodo_tasa_comp: PeriodoDias,
    capitalizacion_comp: CapitalizacionDias | None,
    tipo_tasa_mora: TipoTasa,
    tasa_moratoria: Decimal,
    periodo_tasa_mora: PeriodoDias,
    capitalizacion_mora: CapitalizacionDias | None,
    hoy: date,
    errores: dict[str, str],
) -> tuple[Decimal | None, Decimal | None, TasaMaximaBcrp | None]:
    """Valida reglas de tasas (valores, capitalización y tope BCRP) y retorna las TEA en %."""
    cap_comp = capitalizacion_comp if tipo_tasa_comp == TipoTasa.NOMINAL else None
    cap_mora = capitalizacion_mora if tipo_tasa_mora == TipoTasa.NOMINAL else None

    comp_valida = True
    if tasa_compensatoria <= 0:
        errores["tasa_compensatoria"] = "Tasa inválida: debe ser mayor a 0."
        comp_valida = False
    if tipo_tasa_comp == TipoTasa.NOMINAL and cap_comp is None:
        errores["capitalizacion_comp"] = "Indique la capitalización."
        comp_valida = False

    mora_valida = True
    if tasa_moratoria < 0:
        errores["tasa_moratoria"] = "Tasa inválida: no puede ser negativa."
        mora_valida = False
    if tipo_tasa_mora == TipoTasa.NOMINAL and cap_mora is None:
        errores["capitalizacion_mora"] = "Indique la capitalización."
        mora_valida = False

    if not comp_valida or not mora_valida:
        return None, None, None

    tea_comp_pct = a_porcentaje(
        normalizar_tea(tipo_tasa_comp, tasa_compensatoria, periodo_tasa_comp, cap_comp)
    )
    tea_mora_pct = a_porcentaje(
        normalizar_tea(tipo_tasa_mora, tasa_moratoria, periodo_tasa_mora, cap_mora)
    )

    tasa_bcrp = _obtener_tasa_bcrp_vigente(db, moneda, hoy)

    if tea_comp_pct > tasa_bcrp.tasa_max_compensatoria:
        errores["tasa_compensatoria"] = (
            f"La tasa supera la tasa máxima vigente ({tasa_bcrp.tasa_max_compensatoria:.2f} % TEA)."
        )
    if tea_mora_pct > tasa_bcrp.tasa_max_moratoria:
        errores["tasa_moratoria"] = (
            f"La tasa supera la tasa máxima vigente ({tasa_bcrp.tasa_max_moratoria:.2f} % TEA)."
        )

    return tea_comp_pct, tea_mora_pct, tasa_bcrp


def _validar_datos_comunes(
    *,
    dni: str,
    telefono: str,
    limite_credito: Decimal,
    plazo_max_meses: int,
    dia_corte: int,
    dia_pago: int,
    errores: dict[str, str],
) -> None:
    if len(dni) != 8 or not dni.isdigit():
        errores["dni"] = "DNI inválido: debe tener 8 dígitos numéricos."
    if len(telefono) != 9 or not telefono.isdigit():
        errores["telefono"] = "Teléfono inválido: debe tener 9 dígitos numéricos."
    if limite_credito <= 0:
        errores["limite_credito"] = "Límite de crédito debe ser positivo."
    if plazo_max_meses < 1:
        errores["plazo_max_meses"] = "El plazo máximo debe ser al menos 1 mes."
    if not (1 <= dia_corte <= 30):
        errores["dia_corte"] = "El día de corte debe estar entre 1 y 30."
    if not (1 <= dia_pago <= 30):
        errores["dia_pago"] = "El día de pago debe estar entre 1 y 30."
    if 1 <= dia_corte <= 30 and 1 <= dia_pago <= 30 and dia_pago == dia_corte:
        errores["dia_pago"] = "El día de pago debe ser distinto al día de corte."


def _a_dto(db: Session, cliente: Cliente, hoy: date) -> ClienteResumenDTO:
    usado = saldo_deudor_cliente(db, cliente.cliente_id, hoy)
    disponible = cliente.limite_credito - usado
    return ClienteResumenDTO(
        cliente_id=cliente.cliente_id,
        dni=cliente.dni.strip(),
        nombres_apellidos=cliente.nombres_apellidos,
        telefono=cliente.telefono.strip(),
        direccion=cliente.direccion,
        username=cliente.usuario.username if cliente.usuario else None,
        email=cliente.usuario.email if cliente.usuario else None,
        moneda=cliente.moneda,
        limite_credito=cliente.limite_credito,
        saldo_deudor=usado,
        disponible=disponible,
        plazo_max_meses=cliente.plazo_max_meses,
        dia_corte=cliente.dia_corte,
        hora_corte=cliente.hora_corte,
        dia_pago=cliente.dia_pago,
        tipo_tasa_comp=cliente.tipo_tasa_comp,
        tasa_compensatoria=cliente.tasa_compensatoria,
        periodo_tasa_comp=cliente.periodo_tasa_comp,
        capitalizacion_comp=cliente.capitalizacion_comp,
        tea_comp_porcentaje=a_porcentaje(tea_comp(cliente)),
        tipo_tasa_mora=cliente.tipo_tasa_mora,
        tasa_moratoria=cliente.tasa_moratoria,
        periodo_tasa_mora=cliente.periodo_tasa_mora,
        capitalizacion_mora=cliente.capitalizacion_mora,
        tea_mora_porcentaje=a_porcentaje(tea_mora(cliente)),
        estado=cliente.estado,
    )


def vista_previa_tasas(
    db: Session,
    reloj: RelojSistema,
    dto: VistaPreviaTasasEntradaDTO,
) -> VistaPreviaTasasRespuestaDTO:
    """Calcula la TEA compensatoria y moratoria y las compara con el tope vigente del BCRP."""
    errores: dict[str, str] = {}
    cap_comp = dto.capitalizacion_comp if dto.tipo_tasa_comp == TipoTasa.NOMINAL else None
    cap_mora = dto.capitalizacion_mora if dto.tipo_tasa_mora == TipoTasa.NOMINAL else None

    if dto.tasa_compensatoria <= 0:
        errores["tasa_compensatoria"] = "Tasa inválida: debe ser mayor a 0."
    if dto.tipo_tasa_comp == TipoTasa.NOMINAL and cap_comp is None:
        errores["capitalizacion_comp"] = "Indique la capitalización."
    if dto.tasa_moratoria < 0:
        errores["tasa_moratoria"] = "Tasa inválida: no puede ser negativa."
    if dto.tipo_tasa_mora == TipoTasa.NOMINAL and cap_mora is None:
        errores["capitalizacion_mora"] = "Indique la capitalización."

    if errores:
        raise ErrorNegocio("Errores de validación en las tasas.", errores=errores)

    tea_comp_pct = a_porcentaje(
        normalizar_tea(dto.tipo_tasa_comp, dto.tasa_compensatoria, dto.periodo_tasa_comp, cap_comp)
    )
    tea_mora_pct = a_porcentaje(
        normalizar_tea(dto.tipo_tasa_mora, dto.tasa_moratoria, dto.periodo_tasa_mora, cap_mora)
    )
    tasa_bcrp = _obtener_tasa_bcrp_vigente(db, dto.moneda, reloj.hoy())
    cumple = (
        tea_comp_pct <= tasa_bcrp.tasa_max_compensatoria
        and tea_mora_pct <= tasa_bcrp.tasa_max_moratoria
    )
    return VistaPreviaTasasRespuestaDTO(
        moneda=dto.moneda,
        tea_comp_porcentaje=tea_comp_pct,
        tea_mora_porcentaje=tea_mora_pct,
        tasa_max_comp_bcrp=tasa_bcrp.tasa_max_compensatoria,
        tasa_max_mora_bcrp=tasa_bcrp.tasa_max_moratoria,
        cumple_bcrp=cumple,
    )


def listar_clientes(
    db: Session,
    sesion: Sesion,
    reloj: RelojSistema,
    buscar: str | None = None,
    moneda: Moneda | None = None,
    solo_activos: bool = True,
) -> list[ClienteResumenDTO]:
    """Lista los clientes de la tienda con límite, saldo deudor y disponible (Fig. 9)."""
    if sesion.tienda_id is None:
        raise ErrorNegocio("El usuario no administra ninguna tienda.")

    stmt = select(Cliente).where(Cliente.tienda_id == sesion.tienda_id)
    if solo_activos:
        stmt = stmt.where(Cliente.estado == ACTIVO)
    if buscar:
        termino = f"%{buscar.strip()}%"
        stmt = stmt.where(
            (Cliente.nombres_apellidos.ilike(termino))
            | (Cliente.dni.ilike(termino))
            | (Cliente.telefono.ilike(termino))
        )
    if moneda:
        stmt = stmt.where(Cliente.moneda == moneda)

    stmt = stmt.order_by(Cliente.nombres_apellidos)
    clientes = db.scalars(stmt).all()
    hoy = reloj.hoy()
    return [_a_dto(db, c, hoy) for c in clientes]


def obtener_cliente(
    db: Session,
    sesion: Sesion,
    reloj: RelojSistema,
    cliente_id: int,
) -> ClienteResumenDTO:
    """Obtiene el detalle de un cliente garantizando pertenencia a la tienda."""
    if sesion.tienda_id is None:
        raise ErrorNegocio("El usuario no administra ninguna tienda.")

    cliente = db.scalar(
        select(Cliente).where(
            Cliente.cliente_id == cliente_id,
            Cliente.tienda_id == sesion.tienda_id,
        )
    )
    if cliente is None:
        raise NoEncontrado(f"Cliente {cliente_id} no encontrado en su tienda.")
    return _a_dto(db, cliente, reloj.hoy())


def registrar_cliente(
    db: Session,
    sesion: Sesion,
    reloj: RelojSistema,
    dto: RegistrarClienteDTO,
    ip_cliente: str | None = None,
) -> ClienteResumenDTO:
    """Registra un nuevo cliente, valida topes BCRP y crea su usuario de acceso (Fig. 10 y 11)."""
    if sesion.tienda_id is None:
        raise ErrorNegocio("El usuario no administra ninguna tienda.")

    hoy = reloj.hoy()
    errores: dict[str, str] = {}

    dni = dto.dni.strip()
    telefono = dto.telefono.strip()
    username = dto.username.strip()
    email = dto.email.strip() if dto.email else None

    _validar_datos_comunes(
        dni=dni,
        telefono=telefono,
        limite_credito=dto.limite_credito,
        plazo_max_meses=dto.plazo_max_meses,
        dia_corte=dto.dia_corte,
        dia_pago=dto.dia_pago,
        errores=errores,
    )

    if " " in username:
        errores["username"] = "El usuario no puede contener espacios."
    if len(dto.password) < 8:
        errores["password"] = "La contraseña debe tener al menos 8 caracteres."

    # Duplicado de DNI dentro de la misma tienda
    if "dni" not in errores:
        existe_dni = db.scalar(
            select(Cliente).where(
                Cliente.tienda_id == sesion.tienda_id,
                Cliente.dni == dni,
            )
        )
        if existe_dni is not None:
            errores["dni"] = "DNI ya registrado en esta tienda."

    # Duplicado de username global
    if "username" not in errores:
        existe_user = db.scalar(select(Usuario).where(Usuario.username == username))
        if existe_user is not None:
            errores["username"] = "El nombre de usuario ya existe."

    # Duplicado de email si se proporcionó
    if email:
        existe_email = db.scalar(select(Usuario).where(Usuario.email == email))
        if existe_email is not None:
            errores["email"] = "El correo electrónico ya está registrado."

    # Validación de tasas y topes BCRP
    _validar_tasas_y_calcular_tea(
        db,
        moneda=dto.moneda,
        tipo_tasa_comp=dto.tipo_tasa_comp,
        tasa_compensatoria=dto.tasa_compensatoria,
        periodo_tasa_comp=dto.periodo_tasa_comp,
        capitalizacion_comp=dto.capitalizacion_comp,
        tipo_tasa_mora=dto.tipo_tasa_mora,
        tasa_moratoria=dto.tasa_moratoria,
        periodo_tasa_mora=dto.periodo_tasa_mora,
        capitalizacion_mora=dto.capitalizacion_mora,
        hoy=hoy,
        errores=errores,
    )

    if errores:
        mensaje_general = "Errores de validación en el formulario."
        if (
            "tasa_compensatoria" in errores
            and "tasa máxima vigente" in errores["tasa_compensatoria"]
        ) or (
            "tasa_moratoria" in errores
            and "tasa máxima vigente" in errores["tasa_moratoria"]
        ):
            mensaje_general = "La tasa supera la tasa máxima vigente"
        raise ErrorNegocio(mensaje_general, estado=400, errores=errores)

    cap_comp = dto.capitalizacion_comp if dto.tipo_tasa_comp == TipoTasa.NOMINAL else None
    cap_mora = dto.capitalizacion_mora if dto.tipo_tasa_mora == TipoTasa.NOMINAL else None

    usuario = Usuario(
        username=username,
        password_hash=hash_password(dto.password),
        email=email,
        nombres=dto.nombres_apellidos.strip(),
        rol=Rol.CLIENTE,
        estado=ACTIVO,
    )
    db.add(usuario)
    db.flush()

    cliente = Cliente(
        tienda_id=sesion.tienda_id,
        usuario_id=usuario.usuario_id,
        dni=dni,
        nombres_apellidos=dto.nombres_apellidos.strip(),
        telefono=telefono,
        direccion=dto.direccion.strip(),
        moneda=dto.moneda,
        limite_credito=dto.limite_credito,
        plazo_max_meses=dto.plazo_max_meses,
        dia_corte=dto.dia_corte,
        hora_corte=dto.hora_corte,
        dia_pago=dto.dia_pago,
        tipo_tasa_comp=dto.tipo_tasa_comp,
        tasa_compensatoria=dto.tasa_compensatoria,
        periodo_tasa_comp=dto.periodo_tasa_comp,
        capitalizacion_comp=cap_comp,
        tipo_tasa_mora=dto.tipo_tasa_mora,
        tasa_moratoria=dto.tasa_moratoria,
        periodo_tasa_mora=dto.periodo_tasa_mora,
        capitalizacion_mora=cap_mora,
        estado=ACTIVO,
    )
    db.add(cliente)
    db.flush()

    registrar_auditoria(
        db,
        usuario_id=sesion.usuario_id,
        accion="ALTA",
        tabla="clientes",
        registro_id=cliente.cliente_id,
        ip=ip_cliente,
        datos_nuevos={
            "dni": cliente.dni,
            "nombres_apellidos": cliente.nombres_apellidos,
            "moneda": cliente.moneda.value,
            "limite_credito": str(cliente.limite_credito),
            "username": usuario.username,
        },
    )
    db.commit()
    return _a_dto(db, cliente, hoy)


def actualizar_cliente(
    db: Session,
    sesion: Sesion,
    reloj: RelojSistema,
    cliente_id: int,
    dto: ActualizarClienteDTO,
    ip_cliente: str | None = None,
) -> ClienteResumenDTO:
    """Actualiza datos de contacto y condiciones de crédito de un cliente existente."""
    if sesion.tienda_id is None:
        raise ErrorNegocio("El usuario no administra ninguna tienda.")

    cliente = db.scalar(
        select(Cliente).where(
            Cliente.cliente_id == cliente_id,
            Cliente.tienda_id == sesion.tienda_id,
        )
    )
    if cliente is None:
        raise NoEncontrado(f"Cliente {cliente_id} no encontrado en su tienda.")

    hoy = reloj.hoy()
    errores: dict[str, str] = {}
    dni = dto.dni.strip()
    telefono = dto.telefono.strip()

    _validar_datos_comunes(
        dni=dni,
        telefono=telefono,
        limite_credito=dto.limite_credito,
        plazo_max_meses=dto.plazo_max_meses,
        dia_corte=dto.dia_corte,
        dia_pago=dto.dia_pago,
        errores=errores,
    )

    if "dni" not in errores:
        otro_dni = db.scalar(
            select(Cliente).where(
                Cliente.tienda_id == sesion.tienda_id,
                Cliente.dni == dni,
                Cliente.cliente_id != cliente_id,
            )
        )
        if otro_dni is not None:
            errores["dni"] = "Ya existe otro cliente con ese DNI en esta tienda."

    # No permitir cambiar moneda si el cliente tiene deuda pendiente
    if dto.moneda != cliente.moneda and saldo_deudor_cliente(db, cliente.cliente_id, hoy) > 0:
        errores["moneda"] = "No se puede cambiar la moneda mientras el cliente tenga deuda pendiente."

    _validar_tasas_y_calcular_tea(
        db,
        moneda=dto.moneda,
        tipo_tasa_comp=dto.tipo_tasa_comp,
        tasa_compensatoria=dto.tasa_compensatoria,
        periodo_tasa_comp=dto.periodo_tasa_comp,
        capitalizacion_comp=dto.capitalizacion_comp,
        tipo_tasa_mora=dto.tipo_tasa_mora,
        tasa_moratoria=dto.tasa_moratoria,
        periodo_tasa_mora=dto.periodo_tasa_mora,
        capitalizacion_mora=dto.capitalizacion_mora,
        hoy=hoy,
        errores=errores,
    )

    if errores:
        mensaje_general = "Errores de validación en el formulario."
        if (
            "tasa_compensatoria" in errores
            and "tasa máxima vigente" in errores["tasa_compensatoria"]
        ) or (
            "tasa_moratoria" in errores
            and "tasa máxima vigente" in errores["tasa_moratoria"]
        ):
            mensaje_general = "La tasa supera la tasa máxima vigente"
        raise ErrorNegocio(mensaje_general, estado=400, errores=errores)

    valores_anteriores = {
        "dni": cliente.dni.strip(),
        "nombres_apellidos": cliente.nombres_apellidos,
        "moneda": cliente.moneda.value,
        "limite_credito": str(cliente.limite_credito),
        "plazo_max_meses": cliente.plazo_max_meses,
        "dia_corte": cliente.dia_corte,
        "dia_pago": cliente.dia_pago,
    }

    cap_comp = dto.capitalizacion_comp if dto.tipo_tasa_comp == TipoTasa.NOMINAL else None
    cap_mora = dto.capitalizacion_mora if dto.tipo_tasa_mora == TipoTasa.NOMINAL else None

    cliente.dni = dni
    cliente.nombres_apellidos = dto.nombres_apellidos.strip()
    cliente.telefono = telefono
    cliente.direccion = dto.direccion.strip()
    cliente.moneda = dto.moneda
    cliente.limite_credito = dto.limite_credito
    cliente.plazo_max_meses = dto.plazo_max_meses
    cliente.dia_corte = dto.dia_corte
    cliente.hora_corte = dto.hora_corte
    cliente.dia_pago = dto.dia_pago
    cliente.tipo_tasa_comp = dto.tipo_tasa_comp
    cliente.tasa_compensatoria = dto.tasa_compensatoria
    cliente.periodo_tasa_comp = dto.periodo_tasa_comp
    cliente.capitalizacion_comp = cap_comp
    cliente.tipo_tasa_mora = dto.tipo_tasa_mora
    cliente.tasa_moratoria = dto.tasa_moratoria
    cliente.periodo_tasa_mora = dto.periodo_tasa_mora
    cliente.capitalizacion_mora = cap_mora

    if cliente.usuario is not None:
        cliente.usuario.nombres = cliente.nombres_apellidos

    db.flush()
    registrar_auditoria(
        db,
        usuario_id=sesion.usuario_id,
        accion="EDICION",
        tabla="clientes",
        registro_id=cliente.cliente_id,
        ip=ip_cliente,
        datos_anteriores=valores_anteriores,
        datos_nuevos={
            "dni": cliente.dni,
            "nombres_apellidos": cliente.nombres_apellidos,
            "moneda": cliente.moneda.value,
            "limite_credito": str(cliente.limite_credito),
            "plazo_max_meses": cliente.plazo_max_meses,
            "dia_corte": cliente.dia_corte,
            "dia_pago": cliente.dia_pago,
        },
    )
    db.commit()
    return _a_dto(db, cliente, hoy)


def dar_de_baja_cliente(
    db: Session,
    sesion: Sesion,
    reloj: RelojSistema,
    cliente_id: int,
    ip_cliente: str | None = None,
) -> ClienteResumenDTO:
    """Baja lógica de un cliente (Fig. 12). Rechaza si tiene saldo deudor > 0."""
    if sesion.tienda_id is None:
        raise ErrorNegocio("El usuario no administra ninguna tienda.")

    cliente = db.scalar(
        select(Cliente).where(
            Cliente.cliente_id == cliente_id,
            Cliente.tienda_id == sesion.tienda_id,
        )
    )
    if cliente is None:
        raise NoEncontrado(f"Cliente {cliente_id} no encontrado en su tienda.")

    hoy = reloj.hoy()
    if saldo_deudor_cliente(db, cliente.cliente_id, hoy) > 0:
        raise ErrorNegocio(400, "El cliente tiene deuda pendiente")

    if cliente.estado == BAJA:
        return _a_dto(db, cliente, hoy)

    cliente.estado = BAJA
    db.flush()
    registrar_auditoria(
        db,
        usuario_id=sesion.usuario_id,
        accion="BAJA",
        tabla="clientes",
        registro_id=cliente.cliente_id,
        ip=ip_cliente,
        datos_nuevos={"estado": BAJA},
    )
    db.commit()
    return _a_dto(db, cliente, hoy)


def reactivar_cliente(
    db: Session,
    sesion: Sesion,
    reloj: RelojSistema,
    cliente_id: int,
    ip_cliente: str | None = None,
) -> ClienteResumenDTO:
    """Reactiva un cliente dado de baja (`estado = 1`)."""
    if sesion.tienda_id is None:
        raise ErrorNegocio("El usuario no administra ninguna tienda.")

    cliente = db.scalar(
        select(Cliente).where(
            Cliente.cliente_id == cliente_id,
            Cliente.tienda_id == sesion.tienda_id,
        )
    )
    if cliente is None:
        raise NoEncontrado(f"Cliente {cliente_id} no encontrado en su tienda.")

    cliente.estado = ACTIVO
    db.flush()
    registrar_auditoria(
        db,
        usuario_id=sesion.usuario_id,
        accion="REACTIVACION",
        tabla="clientes",
        registro_id=cliente.cliente_id,
        ip=ip_cliente,
        datos_nuevos={"estado": ACTIVO},
    )
    db.commit()
    return _a_dto(db, cliente, reloj.hoy())
