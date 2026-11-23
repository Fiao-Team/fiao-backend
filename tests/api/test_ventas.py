"""Ventas (pseudocódigo 4.5, Fig. 13 a 19) con los Juegos 1 y 2 del informe."""

from datetime import date, datetime
from decimal import Decimal as D

import pytest
from sqlalchemy import func, select

from app.entidades.acceso import AuditoriaSistema
from app.entidades.enums import ModalidadPago, Rol
from app.entidades.tipos import BAJA
from app.entidades.venta import DetalleTransaccion, PlanPago, Transaccion
from tests.api.datos import (
    crear_carlos, crear_cliente, crear_productos, crear_rosa, crear_tienda, crear_usuario,
    fijar_momento, token,
)

FIN = ModalidadPago.FIN_DE_MES.value
MESES = ModalidadPago.EN_MESES.value


@pytest.fixture
def tienda(db):
    t = crear_tienda(db, "donpepe_t", "Bodega Don Pepe", "20123456789")
    t.productos = crear_productos(db, t)
    return t


@pytest.fixture
def cab(client, tienda):
    """Cabecera con el token del dueño de la tienda."""
    return token(client, "donpepe_t")


def item(producto, cantidad, modalidad=FIN):
    return {"producto_id": producto.producto_id, "cantidad": str(cantidad), "modalidad": modalidad}


def contar(db, modelo):
    return db.scalar(select(func.count()).select_from(modelo))


def venta_rosa(tienda, cliente):
    """Juego 1: abarrotes a fin de mes (45.00) y licuadora en 3 cuotas (210.00)."""
    p = tienda.productos
    return {
        "cliente_id": cliente.cliente_id,
        "items": [item(p["arroz"], 1), item(p["aceite"], 1), item(p["leche"], 2),
                  item(p["licuadora"], 1, MESES)],
        "cuotas": 3,
    }


# ---------------- Juego 1: Rosa Díaz, 15/09/2026 ----------------

def test_juego1_rosa_registra_fin_de_mes_y_3_cuotas(client, db, tienda, cab):
    rosa = crear_rosa(db, tienda)
    fijar_momento(db, datetime(2026, 9, 15, 10, 0))

    r = client.post("/ventas", json=venta_rosa(tienda, rosa), headers=cab)
    assert r.status_code == 201, r.text
    v = r.json()

    assert v["fecha_pago"] == "2026-09-26" and v["posterior_al_corte"] is False
    assert D(v["tea"]) == D("30.0000000")
    assert D(v["disponible"]) == D("500.00")
    assert D(v["total_capital"]) == D("255.00")
    assert D(v["disponible_despues"]) == D("245.00")

    fin, meses = v["grupos"]
    assert fin["modalidad"] == FIN
    assert (D(fin["C"]), fin["dias"], D(fin["tep"])) == (D("45.00"), 11, D("0.8048906"))
    assert (D(fin["total"]), D(fin["interes"])) == (D("45.36"), D("0.36"))
    assert D(fin["tcea"]) == D("29.7937494")
    assert [D(l["subtotal"]) for l in fin["lineas"]] == [D("24.00"), D("11.20"), D("9.80")]

    assert meses["modalidad"] == MESES and meses["cuotas"] == 3
    assert (D(meses["C"]), meses["dias"], D(meses["C_prima"])) == (D("210.00"), 11, D("211.69"))
    assert (D(meses["tem"]), D(meses["frc"]), D(meses["R"])) == (D("2.2104451"), D("0.3481770"), D("73.71"))
    assert D(meses["tcea"]) == D("29.9801205")
    assert [(c["vencimiento"], D(c["interes"]), D(c["amortizacion"]), D(c["cuota"]), D(c["saldo_final"]))
            for c in meses["cronograma"]] == [
        ("2026-10-26", D("4.68"), D("69.03"), D("73.71"), D("142.66")),
        ("2026-11-26", D("3.15"), D("70.56"), D("73.71"), D("72.10")),
        ("2026-12-26", D("1.59"), D("72.10"), D("73.69"), D("0.00")),
    ]
    assert D(meses["total"]) == D("221.11")
    assert D(v["total_a_pagar"]) == D("266.47")  # 45.36 + 221.11 (Fig. 15)

    # Lo guardado en la base
    t_fin = db.get(Transaccion, fin["transaccion_id"])
    assert (t_fin.monto_capital, t_fin.monto_total, t_fin.dias_financiamiento_gracia) == (D("45.00"), D("45.36"), 11)
    assert (t_fin.fecha_corte_aplicada, t_fin.fecha_vencimiento) == (date(2026, 9, 20), date(2026, 9, 26))
    assert t_fin.fecha_hora_compra == datetime(2026, 9, 15, 10, 0)
    assert (t_fin.tea_aplicada, t_fin.tcea) == (D("30.0000000"), D("29.7937494"))

    t_meses = db.get(Transaccion, meses["transaccion_id"])
    assert (t_meses.num_cuotas, t_meses.deuda_capitalizada, t_meses.monto_total) == (3, D("211.69"), D("221.11"))
    assert (t_meses.tem_aplicada, t_meses.tcea) == (D("2.2104451"), D("29.9801205"))
    assert [c.monto_cuota for c in t_meses.cuotas] == [D("73.71"), D("73.71"), D("73.69")]

    assert contar(db, DetalleTransaccion) == 4
    assert contar(db, PlanPago) == 3
    auditadas = db.scalars(select(AuditoriaSistema.registro_id).where(AuditoriaSistema.accion == "VENTA")).all()
    assert sorted(auditadas) == sorted([t_fin.transaccion_id, t_meses.transaccion_id])


def test_vista_previa_da_lo_mismo_y_no_guarda_nada(client, db, tienda, cab):
    rosa = crear_rosa(db, tienda)
    fijar_momento(db, datetime(2026, 9, 15, 10, 0))

    previa = client.post("/ventas/vista-previa", json=venta_rosa(tienda, rosa), headers=cab)
    assert previa.status_code == 200
    assert contar(db, Transaccion) == 0

    registrada = client.post("/ventas", json=venta_rosa(tienda, rosa), headers=cab).json()
    p = previa.json()
    for g_previa, g_reg in zip(p["grupos"], registrada["grupos"]):
        g_previa.pop("transaccion_id"), g_reg.pop("transaccion_id")
        assert g_previa == g_reg


# ---------------- Juego 2: Carlos Mendoza ----------------

def test_juego2_carlos_compra_rechazada_y_compra_posterior_al_corte(client, db, tienda, cab):
    carlos = crear_carlos(db, tienda)
    p = tienda.productos

    # 10/08: licuadora en 2 cuotas
    fijar_momento(db, datetime(2026, 8, 10, 11, 0))
    r = client.post("/ventas", headers=cab, json={
        "cliente_id": carlos.cliente_id, "items": [item(p["licuadora"], 1, MESES)], "cuotas": 2})
    lic = r.json()["grupos"][0]
    assert (lic["dias"], D(lic["C_prima"]), D(lic["R"])) == (16, D("212.78"), D("110.40"))
    assert [D(c["cuota"]) for c in lic["cronograma"]] == [D("110.40"), D("110.39")]
    assert D(lic["tcea"]) == D("34.4673515")

    # 05/09: abarrotes a fin de mes (180.00)
    fijar_momento(db, datetime(2026, 9, 5, 9, 0))
    r = client.post("/ventas", headers=cab, json={"cliente_id": carlos.cliente_id, "items": [
        item(p["arroz"], 3), item(p["aceite"], 5), item(p["azucar"], 5),
        item(p["leche"], 4), item(p["fideos"], 2)]})
    fin = r.json()["grupos"][0]
    assert (D(fin["C"]), fin["dias"], D(fin["total"])) == (D("180.00"), 21, D("183.14"))
    assert D(r.json()["tea"]) == D("34.4888824")

    # 22/09: intento de 330.00 -> rechazado por 22.78 (Fig. 19)
    fijar_momento(db, datetime(2026, 9, 22, 18, 0))
    intento = {"cliente_id": carlos.cliente_id, "items": [item(p["licuadora"], 1), item(p["arroz"], 5)]}
    previa = client.post("/ventas/vista-previa", json=intento, headers=cab).json()
    assert previa["aprobado"] is False
    assert D(previa["disponible"]) == D("307.22")
    assert previa["mensaje_limite"] == "Límite de crédito excedido por S/ 22.78"
    assert D(previa["grupos"][0]["total"]) == D("339.37")  # 34 días, como en la Fig. 19

    antes = contar(db, Transaccion)
    r = client.post("/ventas", json=intento, headers=cab)
    assert (r.status_code, r.json()["detail"]) == (400, "Límite de crédito excedido por S/ 22.78")
    assert contar(db, Transaccion) == antes  # no se guardó nada

    # 22/09: compra de 60.00 después del corte -> se paga el 26/10 (Fig. 18)
    r = client.post("/ventas", headers=cab, json={"cliente_id": carlos.cliente_id,
                                                  "items": [item(p["detergente"], 2), item(p["gaseosa"], 3)]})
    v = r.json()
    assert r.status_code == 201
    assert v["posterior_al_corte"] is True
    assert v["aviso"] == "Compra posterior al corte: se paga el 26/10/2026"
    assert (v["fecha_corte"], v["fecha_pago"]) == ("2026-10-20T23:59:00", "2026-10-26")
    g = v["grupos"][0]
    assert (D(g["C"]), g["dias"], D(g["total"]), D(g["interes"])) == (D("60.00"), 34, D("61.70"), D("1.70"))
    assert D(g["tcea"]) == D("34.4239747")
    assert D(v["disponible_despues"]) == D("247.22")


# ---------------- Hora de corte ----------------

@pytest.mark.parametrize("momento, pago, posterior", [
    (datetime(2026, 9, 20, 23, 59), "2026-09-26", False),   # justo a la hora de corte: entra
    (datetime(2026, 9, 20, 23, 59, 50), "2026-09-26", False),  # se compara al minuto
    (datetime(2026, 9, 21, 0, 0), "2026-10-26", True),       # un minuto después: siguiente corte
])
def test_compra_a_la_hora_de_corte(client, db, tienda, cab, momento, pago, posterior):
    rosa = crear_rosa(db, tienda)
    fijar_momento(db, momento)
    r = client.post("/ventas", headers=cab, json={
        "cliente_id": rosa.cliente_id, "items": [item(tienda.productos["arroz"], 1)]})
    assert r.status_code == 201
    assert (r.json()["fecha_pago"], r.json()["posterior_al_corte"]) == (pago, posterior)


# ---------------- Rechazos ----------------

def _rechazo(client, cab, cuerpo, codigo, mensaje):
    r = client.post("/ventas", json=cuerpo, headers=cab)
    assert r.status_code == codigo, r.text
    assert mensaje in r.json()["detail"]


def test_producto_en_otra_moneda(client, db, tienda, cab):
    rosa = crear_rosa(db, tienda)
    _rechazo(client, cab, {"cliente_id": rosa.cliente_id, "items": [
        item(tienda.productos["plancha_usd"], 1, MESES)], "cuotas": 2},
        400, "otra moneda")


@pytest.mark.parametrize("cuotas", [None, 0, 7])
def test_numero_de_cuotas_fuera_de_rango(client, db, tienda, cab, cuotas):
    rosa = crear_rosa(db, tienda)  # plazo máximo 6
    _rechazo(client, cab, {"cliente_id": rosa.cliente_id, "items": [
        item(tienda.productos["licuadora"], 1, MESES)], "cuotas": cuotas},
        400, "Número de cuotas no permitido")


def test_modalidad_no_permitida(client, db, tienda, cab):
    rosa = crear_rosa(db, tienda)
    _rechazo(client, cab, {"cliente_id": rosa.cliente_id, "items": [
        item(tienda.productos["arroz"], 1, MESES)], "cuotas": 2},
        400, "Forma de pago no permitida")


def test_cantidad_invalida(client, db, tienda, cab):
    rosa = crear_rosa(db, tienda)
    _rechazo(client, cab, {"cliente_id": rosa.cliente_id, "items": [
        item(tienda.productos["arroz"], 0)]}, 400, "Cantidad inválida")


def test_carrito_vacio(client, db, tienda, cab):
    rosa = crear_rosa(db, tienda)
    _rechazo(client, cab, {"cliente_id": rosa.cliente_id, "items": []}, 400, "Agregue al menos un producto")


def test_cliente_de_otra_tienda(client, db, tienda, cab):
    otra = crear_tienda(db, "otra_t", "Panadería San José", "20456789123")
    ajeno = crear_rosa(db, otra)
    _rechazo(client, cab, {"cliente_id": ajeno.cliente_id, "items": [
        item(tienda.productos["arroz"], 1)]}, 403, "Acceso denegado")
    assert client.get(f"/ventas/clientes/{ajeno.cliente_id}", headers=cab).status_code == 403


def test_producto_de_otra_tienda(client, db, tienda, cab):
    rosa = crear_rosa(db, tienda)
    otra = crear_tienda(db, "otra_t", "Panadería San José", "20456789123")
    ajeno = crear_productos(db, otra)["arroz"]
    _rechazo(client, cab, {"cliente_id": rosa.cliente_id, "items": [item(ajeno, 1)]},
             400, "Producto no encontrado")


def test_cliente_de_baja(client, db, tienda, cab):
    rosa = crear_rosa(db, tienda)
    rosa.estado = BAJA
    db.flush()
    _rechazo(client, cab, {"cliente_id": rosa.cliente_id, "items": [
        item(tienda.productos["arroz"], 1)]}, 400, "Cliente dado de baja")


def test_solo_el_administrador_del_negocio(client, db, tienda):
    crear_usuario(db, "admin_t", Rol.ADMIN_SISTEMA)
    assert client.get("/ventas/clientes", headers=token(client, "admin_t")).status_code == 403
    assert client.get("/ventas/clientes").status_code == 401


# ---------------- Pasos 1 y 2 ----------------

def test_paso1_buscar_y_resumen_del_cliente(client, db, tienda, cab):
    rosa = crear_rosa(db, tienda)
    baja = crear_cliente(db, tienda, "11111111", "Pedro Ríos", estado=BAJA)
    crear_rosa(db, crear_tienda(db, "otra_t", "Panadería", "20456789123"))  # otra tienda

    encontrados = client.get("/ventas/clientes", params={"buscar": "ros"}, headers=cab).json()
    assert [c["cliente_id"] for c in encontrados] == [rosa.cliente_id]
    por_dni = client.get("/ventas/clientes", params={"buscar": "7281"}, headers=cab).json()
    assert [c["nombres_apellidos"] for c in por_dni] == ["Rosa Díaz"]
    todos = client.get("/ventas/clientes", headers=cab).json()
    assert baja.cliente_id not in [c["cliente_id"] for c in todos]

    fijar_momento(db, datetime(2026, 9, 15, 10, 0))
    resumen = client.get(f"/ventas/clientes/{rosa.cliente_id}", headers=cab).json()
    assert (D(resumen["disponible"]), resumen["fecha_pago"]) == (D("500.00"), "2026-09-26")
    assert resumen["fecha_corte"] == "2026-09-20T23:59:00"
    assert resumen["plazo_max_meses"] == 6


def test_paso2_solo_productos_en_la_moneda_del_cliente(client, db, tienda, cab):
    rosa = crear_rosa(db, tienda)  # PEN
    productos = client.get("/ventas/productos", params={"cliente_id": rosa.cliente_id}, headers=cab).json()
    nombres = {p["nombre"] for p in productos}
    assert "Licuadora Oster" in nombres
    assert "Plancha" not in nombres  # está en dólares
    assert all(p["moneda"] == "PEN" for p in productos)
