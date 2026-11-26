"""Servicio del Dashboard Inicio del Dueño de Negocio (pseudocódigo 4.4, Fig. 6).

Reglas financieras:
- Nunca mezcla PEN y USD en un mismo monto: devuelve totales separados por moneda.
- Usa `RelojSistema` para determinar `hoy`, la semana actual y el mes actual.
- Reutiliza `saldo_deudor_cliente()` y `calcular_atraso()` sin duplicar fórmulas.
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculo.cobro import calcular_atraso
from app.calculo.redondeo import dividir
from app.config.sesion import Sesion
from app.dto.negocio import (
    ClienteEnMoraDTO,
    InicioNegocioDTO,
    ProximoVencimientoDTO,
)
from app.entidades.acceso import Tienda
from app.entidades.catalogo import Cliente
from app.entidades.cobro import ListadoPago
from app.entidades.enums import (
    EstadoCuota,
    EstadoListado,
    EstadoTransaccion,
    ModalidadPago,
    Moneda,
)
from app.entidades.tipos import ACTIVO
from app.entidades.venta import PlanPago, Transaccion
from app.excepciones.errores import ErrorNegocio, NoEncontrado
from app.servicios.reloj_sistema import RelojSistema
from app.servicios.saldos import saldo_deudor_cliente

CERO = Decimal("0.00")
CIEN = Decimal("100")


def obtener_inicio_negocio(
    db: Session,
    sesion: Sesion,
    reloj: RelojSistema,
) -> InicioNegocioDTO:
    """Construye los KPIs, próximos vencimientos y clientes en mora del negocio (Fig. 6)."""
    if sesion.tienda_id is None:
        raise ErrorNegocio("El usuario no administra ninguna tienda.")

    tienda = db.get(Tienda, sesion.tienda_id)
    if tienda is None:
        raise NoEncontrado("Tienda no encontrada.")

    hoy = reloj.hoy()
    fin_semana = hoy + timedelta(days=7)

    clientes = db.scalars(
        select(Cliente)
        .where(Cliente.tienda_id == tienda.tienda_id, Cliente.estado == ACTIVO)
        .order_by(Cliente.nombres_apellidos)
    ).all()

    total_pen = CERO
    total_usd = CERO
    vencen_semana_count = 0
    vencen_semana_pen = CERO
    vencen_semana_usd = CERO

    proximos_vencimientos: list[ProximoVencimientoDTO] = []
    clientes_en_mora: list[ClienteEnMoraDTO] = []

    for c in clientes:
        saldo = saldo_deudor_cliente(db, c.cliente_id, hoy)
        if c.moneda == Moneda.PEN:
            total_pen += saldo
        else:
            total_usd += saldo

        # Revisar listados no pagados del cliente
        listados_pendientes = db.scalars(
            select(ListadoPago)
            .where(
                ListadoPago.cliente_id == c.cliente_id,
                ListadoPago.estado != EstadoListado.PAGADO,
            )
            .order_by(ListadoPago.fecha_pago_pactada.asc())
        ).all()

        max_dias_mora = 0
        monto_mora_total = CERO
        fecha_proxima: date | None = None
        monto_proximo = CERO

        for lst in listados_pendientes:
            atraso = calcular_atraso(
                lst.subtotal,
                dividir(lst.tea_comp_aplicada, CIEN),
                dividir(lst.tea_mora_aplicada, CIEN),
                lst.fecha_pago_pactada,
                hoy,
            )
            total_actual = lst.subtotal + atraso.I_C + atraso.M

            if atraso.dm > 0:
                max_dias_mora = max(max_dias_mora, atraso.dm)
                monto_mora_total += total_actual

            if fecha_proxima is None:
                fecha_proxima = lst.fecha_pago_pactada
                monto_proximo = total_actual

            if hoy <= lst.fecha_pago_pactada <= fin_semana:
                vencen_semana_count += 1
                if c.moneda == Moneda.PEN:
                    vencen_semana_pen += total_actual
                else:
                    vencen_semana_usd += total_actual

        if max_dias_mora > 0:
            clientes_en_mora.append(
                ClienteEnMoraDTO(
                    cliente_id=c.cliente_id,
                    nombres_apellidos=c.nombres_apellidos,
                    moneda=c.moneda,
                    dias_atraso=max_dias_mora,
                    monto_vencido=monto_mora_total,
                )
            )
            proximos_vencimientos.append(
                ProximoVencimientoDTO(
                    cliente_id=c.cliente_id,
                    nombres_apellidos=c.nombres_apellidos,
                    moneda=c.moneda,
                    monto=monto_mora_total,
                    fecha_pago=fecha_proxima or hoy,
                    situacion="EN_MORA",
                    dias_mora=max_dias_mora,
                )
            )
        elif fecha_proxima is not None:
            proximos_vencimientos.append(
                ProximoVencimientoDTO(
                    cliente_id=c.cliente_id,
                    nombres_apellidos=c.nombres_apellidos,
                    moneda=c.moneda,
                    monto=monto_proximo,
                    fecha_pago=fecha_proxima,
                    situacion="CON_DEUDA",
                    dias_mora=0,
                )
            )
        elif saldo > 0:
            # Tiene compras pendientes aún sin listado generado (antes del corte)
            prox_fin_mes = db.scalar(
                select(Transaccion.fecha_vencimiento)
                .where(
                    Transaccion.cliente_id == c.cliente_id,
                    Transaccion.estado_transaccion == EstadoTransaccion.PENDIENTE,
                    Transaccion.modalidad_pago == ModalidadPago.FIN_DE_MES,
                )
                .order_by(Transaccion.fecha_vencimiento.asc())
                .limit(1)
            )
            prox_cuota = db.scalar(
                select(PlanPago.fecha_vencimiento)
                .join(Transaccion, PlanPago.transaccion_id == Transaccion.transaccion_id)
                .where(
                    Transaccion.cliente_id == c.cliente_id,
                    PlanPago.estado_cuota != EstadoCuota.PAGADA,
                )
                .order_by(PlanPago.fecha_vencimiento.asc())
                .limit(1)
            )
            candidatas = [f for f in (prox_fin_mes, prox_cuota) if f is not None]
            if candidatas:
                fecha_est = min(candidatas)
                proximos_vencimientos.append(
                    ProximoVencimientoDTO(
                        cliente_id=c.cliente_id,
                        nombres_apellidos=c.nombres_apellidos,
                        moneda=c.moneda,
                        monto=saldo,
                        fecha_pago=fecha_est,
                        situacion="CON_DEUDA",
                        dias_mora=0,
                    )
                )
                if hoy <= fecha_est <= fin_semana:
                    vencen_semana_count += 1
                    if c.moneda == Moneda.PEN:
                        vencen_semana_pen += saldo
                    else:
                        vencen_semana_usd += saldo

    # Crédito otorgado este mes calendario
    inicio_mes = date(hoy.year, hoy.month, 1)
    if hoy.month == 12:
        inicio_sig_mes = date(hoy.year + 1, 1, 1)
    else:
        inicio_sig_mes = date(hoy.year, hoy.month + 1, 1)

    transacciones_mes = db.execute(
        select(Transaccion.monto_capital, Cliente.moneda)
        .join(Cliente, Transaccion.cliente_id == Cliente.cliente_id)
        .where(
            Cliente.tienda_id == tienda.tienda_id,
            Transaccion.estado_transaccion != EstadoTransaccion.ANULADA,
            Transaccion.fecha_hora_compra >= inicio_mes,
            Transaccion.fecha_hora_compra < inicio_sig_mes,
        )
    ).all()

    credito_mes_pen = CERO
    credito_mes_usd = CERO
    for monto_cap, mon in transacciones_mes:
        if mon == Moneda.PEN:
            credito_mes_pen += monto_cap
        else:
            credito_mes_usd += monto_cap

    proximos_vencimientos.sort(key=lambda x: (0 if x.situacion == "EN_MORA" else 1, x.fecha_pago))
    clientes_en_mora.sort(key=lambda x: x.dias_atraso, reverse=True)

    return InicioNegocioDTO(
        tienda_id=tienda.tienda_id,
        nombre_comercial=tienda.nombre_comercial,
        clientes_activos=len(clientes),
        total_por_cobrar_pen=total_pen,
        total_por_cobrar_usd=total_usd,
        clientes_en_mora_count=len(clientes_en_mora),
        vencen_esta_semana_count=vencen_semana_count,
        vencen_esta_semana_pen=vencen_semana_pen,
        vencen_esta_semana_usd=vencen_semana_usd,
        credito_este_mes_pen=credito_mes_pen,
        credito_este_mes_usd=credito_mes_usd,
        ventas_este_mes_count=len(transacciones_mes),
        proximos_vencimientos=proximos_vencimientos,
        clientes_en_mora=clientes_en_mora,
    )
