"""Servicio de ventas (pseudocódigo 4.5, Fig. 13 a 19).

Reutiliza el módulo de cálculo (no repite fórmulas):
fecha_pago_del_ciclo, dias_entre, compra_fin_de_mes, generar_cronograma,
tcea_fin_de_mes, tcea_en_meses y saldo_deudor (vía servicios/saldos.py).

La vista previa y el registro usan la MISMA función (_calcular), así nunca
pueden mostrar montos distintos.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.calculo.ciclo import Ciclo, fecha_pago_del_ciclo
from app.calculo.compras import compra_fin_de_mes, generar_cronograma
from app.calculo.fechas import dias_entre
from app.calculo.redondeo import a_porcentaje, red_monto
from app.calculo.tcea import tcea_en_meses, tcea_fin_de_mes
from app.config.auditoria import registrar_auditoria
from app.dto.ventas import (
    ClienteBusqueda,
    ClienteResumen,
    CuotaVista,
    GrupoVenta,
    LineaVenta,
    ProductoVenta,
    VentaEntrada,
    VentaResultado,
)
from app.entidades.catalogo import Cliente, Producto
from app.entidades.enums import FormaVentaProducto, ModalidadPago, Moneda
from app.entidades.tipos import ACTIVO, BAJA
from app.entidades.venta import DetalleTransaccion, PlanPago, Transaccion
from app.excepciones.errores import ErrorNegocio
from app.servicios.reloj_sistema import RelojSistema
from app.servicios.saldos import disponible_cliente, saldo_deudor_cliente
from app.servicios.tasas_cliente import tea_comp

CERO = Decimal("0.00")
SIMBOLO = {Moneda.PEN: "S/", Moneda.USD: "US$"}

# Qué modalidades permite cada forma de venta del producto.
PERMITIDAS = {
    FormaVentaProducto.FIN_DE_MES: {ModalidadPago.FIN_DE_MES},
    FormaVentaProducto.EN_MESES: {ModalidadPago.EN_MESES},
    FormaVentaProducto.AMBAS: {ModalidadPago.FIN_DE_MES, ModalidadPago.EN_MESES},
}


def _dinero(moneda: Moneda, monto: Decimal) -> str:
    return f"{SIMBOLO[moneda]} {monto:,.2f}"


def _ahora_al_minuto(reloj: RelojSistema) -> datetime:
    """La compra se registra al minuto (formato dd/mm/aaaa HH:mm de la Tabla 5)."""
    return reloj.ahora().replace(second=0, microsecond=0)


def _ciclo(cliente: Cliente, momento: datetime) -> Ciclo:
    return fecha_pago_del_ciclo(momento, cliente.dia_corte, cliente.hora_corte, cliente.dia_pago)


# ---------- Cliente de la tienda ----------


def _cliente_de_tienda(db: Session, tienda_id: int, cliente_id: int, bloquear: bool = False) -> Cliente:
    """Busca el cliente y verifica que sea de la tienda de la sesión y esté activo.

    bloquear=True: bloquea su fila hasta el fin de la transacción, para que dos
    ventas al mismo tiempo no pasen juntas el límite de crédito.
    """
    cliente = db.get(Cliente, cliente_id, with_for_update=bloquear)
    if cliente is None or cliente.tienda_id != tienda_id:
        raise ErrorNegocio(403, "Acceso denegado")
    if cliente.estado == BAJA:
        raise ErrorNegocio(400, "Cliente dado de baja")
    return cliente


# ---------- Paso 1 (Fig. 13) ----------


def buscar_clientes(db: Session, tienda_id: int, texto: str) -> list[ClienteBusqueda]:
    """Clientes ACTIVOS de la tienda que coinciden por nombre o DNI."""
    consulta = select(Cliente).where(Cliente.tienda_id == tienda_id, Cliente.estado == ACTIVO)
    texto = texto.strip()
    if texto:
        consulta = consulta.where(
            or_(Cliente.nombres_apellidos.ilike(f"%{texto}%"), Cliente.dni.like(f"{texto}%"))
        )
    clientes = db.scalars(consulta.order_by(Cliente.nombres_apellidos).limit(20)).all()
    return [
        ClienteBusqueda(
            cliente_id=c.cliente_id, nombres_apellidos=c.nombres_apellidos, dni=c.dni, moneda=c.moneda
        )
        for c in clientes
    ]


def resumen_cliente(db: Session, tienda_id: int, cliente_id: int, reloj: RelojSistema) -> ClienteResumen:
    """VentaPaso1_SeleccionarCliente: disponible y fechas de corte y pago que le tocan hoy."""
    cliente = _cliente_de_tienda(db, tienda_id, cliente_id)
    ahora = _ahora_al_minuto(reloj)
    saldo = saldo_deudor_cliente(db, cliente.cliente_id, ahora.date())
    ciclo = _ciclo(cliente, ahora)
    return ClienteResumen(
        cliente_id=cliente.cliente_id,
        nombres_apellidos=cliente.nombres_apellidos,
        dni=cliente.dni,
        moneda=cliente.moneda,
        limite_credito=cliente.limite_credito,
        saldo_deudor=saldo,
        disponible=cliente.limite_credito - saldo,
        plazo_max_meses=cliente.plazo_max_meses,
        dia_corte=cliente.dia_corte,
        hora_corte=cliente.hora_corte,
        dia_pago=cliente.dia_pago,
        fecha_corte=ciclo.corte,
        fecha_pago=ciclo.fecha_pago,
        posterior_al_corte=ciclo.posterior_al_corte,
    )


# ---------- Paso 2 (Fig. 14) ----------


def productos_para_cliente(
    db: Session, tienda_id: int, cliente_id: int, texto: str
) -> list[ProductoVenta]:
    """Productos activos de la tienda EN LA MONEDA del crédito del cliente."""
    cliente = _cliente_de_tienda(db, tienda_id, cliente_id)
    consulta = select(Producto).where(
        Producto.tienda_id == tienda_id,
        Producto.estado == ACTIVO,
        Producto.moneda == cliente.moneda,
    )
    texto = texto.strip()
    if texto:
        consulta = consulta.where(
            or_(Producto.nombre.ilike(f"%{texto}%"), Producto.marca.ilike(f"%{texto}%"))
        )
    return [
        ProductoVenta(
            producto_id=p.producto_id,
            nombre=p.nombre,
            marca=p.marca,
            unidad_medida=p.unidad_medida,
            moneda=p.moneda,
            precio_lista=p.precio_lista,
            forma_venta_credito=p.forma_venta_credito,
            imagen_url=p.imagen_url,
        )
        for p in db.scalars(consulta.order_by(Producto.nombre)).all()
    ]


# ---------- Validación del carrito (pasos 2 y 3) ----------


@dataclass
class _Linea:
    producto: Producto
    cantidad: Decimal
    modalidad: ModalidadPago
    subtotal: Decimal


def _validar_carrito(db: Session, tienda_id: int, cliente: Cliente, datos: VentaEntrada) -> list[_Linea]:
    """VentaPaso2 y las validaciones por grupo de RegistrarVenta."""
    if not datos.items:
        raise ErrorNegocio(400, "Agregue al menos un producto")

    lineas: list[_Linea] = []
    for item in datos.items:
        if item.cantidad <= 0:
            raise ErrorNegocio(400, "Cantidad inválida")
        producto = db.get(Producto, item.producto_id)
        if producto is None or producto.tienda_id != tienda_id or producto.estado != ACTIVO:
            raise ErrorNegocio(400, "Producto no encontrado")
        if producto.moneda != cliente.moneda:
            raise ErrorNegocio(400, "El producto está en otra moneda que el crédito del cliente")
        if item.modalidad not in PERMITIDAS[producto.forma_venta_credito]:
            raise ErrorNegocio(400, f"Forma de pago no permitida para {producto.nombre}")
        lineas.append(
            _Linea(producto, item.cantidad, item.modalidad, red_monto(item.cantidad * producto.precio_lista))
        )

    hay_en_meses = any(l.modalidad == ModalidadPago.EN_MESES for l in lineas)
    if hay_en_meses and (datos.cuotas is None or not 1 <= datos.cuotas <= cliente.plazo_max_meses):
        raise ErrorNegocio(400, f"Número de cuotas no permitido (entre 1 y {cliente.plazo_max_meses})")
    return lineas


# ---------- Cálculo común (vista previa y registro) ----------


def _calcular(
    db: Session, tienda_id: int, cliente: Cliente, datos: VentaEntrada, momento: datetime
) -> tuple[VentaResultado, list[list[_Linea]]]:
    """VentaPaso3_FormaDePago: calcula todo sin guardar nada."""
    lineas = _validar_carrito(db, tienda_id, cliente, datos)
    tea = tea_comp(cliente)
    ciclo = _ciclo(cliente, momento)
    d = dias_entre(momento.date(), ciclo.fecha_pago)

    grupos: list[GrupoVenta] = []
    lineas_por_grupo: list[list[_Linea]] = []
    for modalidad in (ModalidadPago.FIN_DE_MES, ModalidadPago.EN_MESES):
        del_grupo = [l for l in lineas if l.modalidad == modalidad]
        if not del_grupo:
            continue
        C = sum((l.subtotal for l in del_grupo), CERO)
        vista = [
            LineaVenta(
                producto_id=l.producto.producto_id,
                nombre=l.producto.nombre,
                cantidad=l.cantidad,
                precio_unitario=l.producto.precio_lista,
                subtotal=l.subtotal,
            )
            for l in del_grupo
        ]
        if modalidad == ModalidadPago.FIN_DE_MES:
            r = compra_fin_de_mes(C, tea, d)  # interés sobre el total del grupo
            grupos.append(
                GrupoVenta(
                    modalidad=modalidad, lineas=vista, C=C, dias=d, tep=a_porcentaje(r.tep),
                    interes=r.I, total=r.S, tcea=a_porcentaje(tcea_fin_de_mes(C, r.S, d)),
                )
            )
        else:
            cr = generar_cronograma(C, tea, d, datos.cuotas, ciclo.fecha_pago, cliente.dia_pago)
            cuotas_R = [c.cuota for c in cr.cuotas]
            grupos.append(
                GrupoVenta(
                    modalidad=modalidad, lineas=vista, C=C, dias=d, tep=a_porcentaje(cr.tepg),
                    interes=cr.total - C,  # gracia capitalizada + intereses de las cuotas
                    total=cr.total, tcea=a_porcentaje(tcea_en_meses(C, d, cuotas_R)),
                    cuotas=datos.cuotas, C_prima=cr.C_prima, tem=a_porcentaje(cr.tem),
                    frc=cr.frc, R=cr.R,
                    cronograma=[
                        CuotaVista(
                            numero=c.k, vencimiento=c.vencimiento, saldo_inicial=c.saldo_inicial,
                            interes=c.interes, amortizacion=c.amortizacion, cuota=c.cuota,
                            saldo_final=c.saldo_final,
                        )
                        for c in cr.cuotas
                    ],
                )
            )
        lineas_por_grupo.append(del_grupo)

    total_capital = sum((g.C for g in grupos), CERO)
    disponible = disponible_cliente(db, cliente, momento.date())
    excedido = total_capital > disponible
    resultado = VentaResultado(
        cliente_id=cliente.cliente_id,
        moneda=cliente.moneda,
        fecha_compra=momento,
        fecha_corte=ciclo.corte,
        fecha_pago=ciclo.fecha_pago,
        posterior_al_corte=ciclo.posterior_al_corte,
        aviso=(
            f"Compra posterior al corte: se paga el {ciclo.fecha_pago:%d/%m/%Y}"
            if ciclo.posterior_al_corte else None
        ),
        tea=a_porcentaje(tea),
        total_capital=total_capital,
        total_a_pagar=sum((g.total for g in grupos), CERO),
        disponible=disponible,
        disponible_despues=disponible - total_capital,
        aprobado=not excedido,
        mensaje_limite=(
            f"Límite de crédito excedido por {_dinero(cliente.moneda, total_capital - disponible)}"
            if excedido else None
        ),
        grupos=grupos,
    )
    return resultado, lineas_por_grupo


def vista_previa(
    db: Session, tienda_id: int, datos: VentaEntrada, reloj: RelojSistema
) -> VentaResultado:
    """Paso 3 (Fig. 15 y 16): calcula y muestra; NO guarda nada.
    Si excede el límite no es error: se muestra con aprobado=False (Fig. 19)."""
    cliente = _cliente_de_tienda(db, tienda_id, datos.cliente_id)
    resultado, _ = _calcular(db, tienda_id, cliente, datos, _ahora_al_minuto(reloj))
    return resultado


# ---------- Registrar (Fig. 17, 18 y 19) ----------


def registrar_venta(
    db: Session, tienda_id: int, usuario_id: int, datos: VentaEntrada, reloj: RelojSistema,
    ip: str | None = None,
) -> VentaResultado:
    """RegistrarVenta: valida todo de nuevo y guarda en UNA sola transacción.
    Si algo falla, no se guarda nada (el commit es al final)."""
    cliente = _cliente_de_tienda(db, tienda_id, datos.cliente_id, bloquear=True)
    momento = _ahora_al_minuto(reloj)
    resultado, lineas_por_grupo = _calcular(db, tienda_id, cliente, datos, momento)

    if not resultado.aprobado:
        raise ErrorNegocio(400, resultado.mensaje_limite)

    for grupo, lineas in zip(resultado.grupos, lineas_por_grupo):
        en_meses = grupo.modalidad == ModalidadPago.EN_MESES
        t = Transaccion(
            cliente_id=cliente.cliente_id,
            fecha_hora_compra=momento,
            modalidad_pago=grupo.modalidad,
            num_cuotas=grupo.cuotas,
            monto_capital=grupo.C,
            tea_aplicada=resultado.tea,
            tem_aplicada=grupo.tem,
            dias_financiamiento_gracia=grupo.dias,
            deuda_capitalizada=grupo.C_prima,
            monto_total=grupo.total,
            tcea=grupo.tcea,
            fecha_corte_aplicada=resultado.fecha_corte.date(),
            fecha_vencimiento=resultado.fecha_pago,
        )
        db.add(t)
        db.flush()  # para obtener transaccion_id

        for l in lineas:
            db.add(
                DetalleTransaccion(
                    transaccion_id=t.transaccion_id, producto_id=l.producto.producto_id,
                    cantidad=l.cantidad, precio_unitario=l.producto.precio_lista, subtotal=l.subtotal,
                )
            )
        if en_meses:
            for c in grupo.cronograma:
                db.add(
                    PlanPago(
                        transaccion_id=t.transaccion_id, numero_cuota=c.numero,
                        fecha_vencimiento=c.vencimiento, saldo_inicial=c.saldo_inicial,
                        interes_compensatorio=c.interes, amortizacion=c.amortizacion,
                        monto_cuota=c.cuota, saldo_final=c.saldo_final,
                    )
                )
        registrar_auditoria(db, usuario_id, "VENTA", "transacciones", t.transaccion_id, ip)
        grupo.transaccion_id = t.transaccion_id

    db.commit()
    return resultado
