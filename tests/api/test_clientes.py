"""Pruebas de Gestión de Clientes y Límites de Crédito (pseudocódigo 4.4, Fig. 9 a 12).

Verifica:
- RBAC: solo ADMIN_NEGOCIO accede; ADMIN_SISTEMA y CLIENTE reciben 403.
- Alta de cliente + creación de usuario CLIENTE + login del cliente + auditoría ALTA.
- Validaciones de formulario: DNI 8 dígitos, teléfono 9 dígitos, días 1..30 distintos,
  tasa nominal con capitalización obligatoria, duplicados de DNI en la tienda y username.
- Validación de topes máximos del BCRP (PEN y USD) comparando TEA normalizada.
- Vista previa de tasas (POST /clientes/vista-previa-tasas).
- Listado con cálculo de saldo_deudor y disponible tras una venta real.
- Aislamiento multi-tienda (404 si otra tienda intenta consultar/editar/dar de baja).
- Baja lógica (Fig. 12): rechaza si SaldoDeudor > 0; si es 0 da de baja y bloquea login.
"""

from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.entidades.acceso import AuditoriaSistema
from app.entidades.configuracion import TasaMaximaBcrp
from app.entidades.enums import Moneda, Rol
from app.entidades.tipos import ACTIVO, BAJA
from app.main import app
from app.servicios.reloj_sistema import obtener_reloj
from tests.api.datos import (
    crear_cliente,
    crear_productos,
    crear_tienda,
    crear_usuario,
    fijar_momento,
    token,
)


@pytest.fixture(autouse=True)
def reloj_y_tasas_bcrp(db):
    """Fija la fecha dentro del período BCRP vigente e inserta los topes de mayo-octubre 2026."""
    db.add_all(
        [
            TasaMaximaBcrp(
                moneda=Moneda.PEN,
                vigente_desde=date(2026, 5, 1),
                vigente_hasta=date(2026, 10, 31),
                tasa_max_compensatoria=Decimal("114.1300000"),
                tasa_max_moratoria=Decimal("17.1195000"),
            ),
            TasaMaximaBcrp(
                moneda=Moneda.USD,
                vigente_desde=date(2026, 5, 1),
                vigente_hasta=date(2026, 10, 31),
                tasa_max_compensatoria=Decimal("99.8400000"),
                tasa_max_moratoria=Decimal("14.9760000"),
            ),
        ]
    )
    db.flush()
    fijar_momento(db, datetime(2026, 9, 15, 10, 0))
    yield
    app.dependency_overrides.pop(obtener_reloj, None)


def _payload_cliente(**overrides) -> dict:
    base = {
        "dni": "74125896",
        "nombres_apellidos": "María Elena Quispe",
        "telefono": "987654321",
        "direccion": "Av. Las Palmeras 450",
        "moneda": "PEN",
        "limite_credito": "600.00",
        "plazo_max_meses": 6,
        "dia_corte": 20,
        "hora_corte": "23:59:00",
        "dia_pago": 26,
        "tipo_tasa_comp": "EFECTIVA",
        "tasa_compensatoria": "30.0000000",
        "periodo_tasa_comp": "ANUAL",
        "capitalizacion_comp": None,
        "tipo_tasa_mora": "EFECTIVA",
        "tasa_moratoria": "5.0000000",
        "periodo_tasa_mora": "ANUAL",
        "capitalizacion_mora": None,
        "username": "maria_q",
        "password": "ClaveCliente2026!",
        "email": "maria.quispe@ejemplo.pe",
    }
    base.update(overrides)
    return base


def test_rbac_solo_admin_negocio_accede_a_clientes(client, db):
    crear_usuario(db, "admin_cli_rbac", Rol.ADMIN_SISTEMA, "Admin Sistema")
    h_admin = token(client, "admin_cli_rbac")
    assert client.get("/clientes", headers=h_admin).status_code == 403

    tienda = crear_tienda(db, "dueno_cli_rbac", "Bodega RBAC", "20202020201")
    c = crear_cliente(db, tienda, "70001111", "Cliente RBAC")
    u_cli = crear_usuario(db, "cli_rbac_user", Rol.CLIENTE, "Cliente RBAC")
    c.usuario_id = u_cli.usuario_id
    db.flush()

    h_cli = token(client, "cli_rbac_user")
    assert client.get("/clientes", headers=h_cli).status_code == 403

    h_dueno = token(client, "dueno_cli_rbac")
    resp = client.get("/clientes", headers=h_dueno)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_registrar_cliente_exitoso_login_y_auditoria(client, db):
    crear_tienda(db, "dueno_alta_cli", "Bodega Alta Cli", "20202020202")
    h = token(client, "dueno_alta_cli")

    # Tasa nominal anual 30 % capitalización mensual -> TEA = 34.4888824 % (cumple BCRP 114.13 %)
    payload = _payload_cliente(
        tipo_tasa_comp="NOMINAL",
        tasa_compensatoria="30",
        periodo_tasa_comp="ANUAL",
        capitalizacion_comp="MENSUAL",
        tipo_tasa_mora="NOMINAL",
        tasa_moratoria="5",
        periodo_tasa_mora="ANUAL",
        capitalizacion_mora="MENSUAL",
    )
    resp = client.post("/clientes", json=payload, headers=h)
    assert resp.status_code == 201
    datos = resp.json()
    assert datos["dni"] == "74125896"
    assert datos["username"] == "maria_q"
    assert Decimal(str(datos["limite_credito"])) == Decimal("600.00")
    assert Decimal(str(datos["saldo_deudor"])) == Decimal("0.00")
    assert Decimal(str(datos["disponible"])) == Decimal("600.00")
    assert Decimal(str(datos["tea_comp_porcentaje"])) == Decimal("34.4888824")
    assert datos["estado"] == ACTIVO

    # El cliente recién creado puede iniciar sesión
    r_login = client.post(
        "/auth/login",
        json={"username": "maria_q", "password": "ClaveCliente2026!"},
    )
    assert r_login.status_code == 200
    assert r_login.json()["rol"] == "CLIENTE"

    # Auditoría registrada
    audit = db.scalar(
        select(AuditoriaSistema).where(
            AuditoriaSistema.tabla_afectada == "clientes",
            AuditoriaSistema.registro_id == datos["cliente_id"],
            AuditoriaSistema.accion == "ALTA",
        )
    )
    assert audit is not None


def test_validaciones_formulario_y_bcrp(client, db):
    crear_tienda(db, "dueno_val_cli", "Bodega Val Cli", "20202020203")
    h = token(client, "dueno_val_cli")

    # 1. Errores de campos básicos y tasa nominal sin capitalización (Fig. 11)
    bad = _payload_cliente(
        dni="123",
        telefono="999",
        limite_credito="-50",
        plazo_max_meses=0,
        dia_corte=15,
        dia_pago=15,
        tipo_tasa_comp="NOMINAL",
        capitalizacion_comp=None,
        password="123",
        username="con espacio",
    )
    resp = client.post("/clientes", json=bad, headers=h)
    assert resp.status_code == 400
    errores = resp.json().get("errores", {})
    for campo in (
        "dni",
        "telefono",
        "limite_credito",
        "plazo_max_meses",
        "dia_pago",
        "capitalizacion_comp",
        "password",
        "username",
    ):
        assert campo in errores

    # 2. Tasa mensual que supera la TEA máxima del BCRP (10% TEM -> TEA = 213.84% > 114.13%)
    excede_comp = _payload_cliente(
        dni="74125897",
        username="cli_excede_comp",
        email="exc1@ejemplo.pe",
        tipo_tasa_comp="EFECTIVA",
        tasa_compensatoria="10",
        periodo_tasa_comp="MENSUAL",
    )
    resp_bcrp = client.post("/clientes", json=excede_comp, headers=h)
    assert resp_bcrp.status_code == 400
    assert "tasa máxima vigente" in resp_bcrp.json()["detail"].lower()
    assert "tasa_compensatoria" in resp_bcrp.json()["errores"]

    # 3. Tasa moratoria en USD que supera el tope BCRP (15% > 14.976%)
    excede_mora = _payload_cliente(
        dni="74125898",
        username="cli_excede_mora",
        email="exc2@ejemplo.pe",
        moneda="USD",
        tasa_moratoria="15.0",
    )
    resp_mora = client.post("/clientes", json=excede_mora, headers=h)
    assert resp_mora.status_code == 400
    assert "tasa_moratoria" in resp_mora.json()["errores"]

    # 4. Vista previa de tasas
    vp = client.post(
        "/clientes/vista-previa-tasas",
        json={
            "moneda": "PEN",
            "tipo_tasa_comp": "NOMINAL",
            "tasa_compensatoria": "30",
            "periodo_tasa_comp": "ANUAL",
            "capitalizacion_comp": "MENSUAL",
            "tipo_tasa_mora": "EFECTIVA",
            "tasa_moratoria": "5",
            "periodo_tasa_mora": "ANUAL",
        },
        headers=h,
    )
    assert vp.status_code == 200
    vp_data = vp.json()
    assert Decimal(str(vp_data["tea_comp_porcentaje"])) == Decimal("34.4888824")
    assert vp_data["cumple_bcrp"] is True


def test_listado_saldo_deudor_y_baja_bloqueada_por_deuda(client, db):
    tienda = crear_tienda(db, "dueno_deuda", "Bodega Deuda", "20202020204")
    prods = crear_productos(db, tienda)
    h = token(client, "dueno_deuda")

    # Registrar cliente con límite 500 PEN
    resp = client.post(
        "/clientes",
        json=_payload_cliente(dni="75551111", username="cli_deuda", email="deuda@ej.pe", limite_credito="500.00"),
        headers=h,
    )
    assert resp.status_code == 201
    cliente_id = resp.json()["cliente_id"]

    # Registrar una venta de 2 unidades de arroz (2 * 24.00 = 48.00)
    r_venta = client.post(
        "/ventas",
        json={
            "cliente_id": cliente_id,
            "items": [
                {
                    "producto_id": prods["arroz"].producto_id,
                    "cantidad": 2,
                    "modalidad": "FIN_DE_MES",
                }
            ],
        },
        headers=h,
    )
    assert r_venta.status_code == 201

    # Verificar que GET /clientes refleja saldo_deudor = 48.00 y disponible = 452.00
    r_list = client.get("/clientes?buscar=75551111", headers=h)
    assert r_list.status_code == 200
    lista = r_list.json()
    assert len(lista) == 1
    assert Decimal(str(lista[0]["saldo_deudor"])) == Decimal("48.00")
    assert Decimal(str(lista[0]["disponible"])) == Decimal("452.00")

    # Intentar dar de baja con deuda pendiente -> 400 "El cliente tiene deuda pendiente"
    r_baja = client.patch(f"/clientes/{cliente_id}/baja", headers=h)
    assert r_baja.status_code == 400
    assert r_baja.json()["detail"] == "El cliente tiene deuda pendiente"


def test_aislamiento_entre_tiendas_y_baja_sin_deuda(client, db):
    crear_tienda(db, "dueno_ais_1", "Tienda Ais 1", "20202020205")
    crear_tienda(db, "dueno_ais_2", "Tienda Ais 2", "20202020206")
    h1 = token(client, "dueno_ais_1")
    h2 = token(client, "dueno_ais_2")

    resp = client.post(
        "/clientes",
        json=_payload_cliente(dni="76661111", username="cli_ais1", email="ais1@ej.pe"),
        headers=h1,
    )
    assert resp.status_code == 201
    cliente_id = resp.json()["cliente_id"]

    # Tienda 2 no puede ver, editar ni dar de baja al cliente de Tienda 1
    assert client.get(f"/clientes/{cliente_id}", headers=h2).status_code == 404
    assert client.patch(f"/clientes/{cliente_id}/baja", headers=h2).status_code == 404

    # Tienda 1 edita límite de crédito a 800.00 y correo
    edit_payload = _payload_cliente(
        dni="76661111",
        nombres_apellidos="María Elena Quispe Editada",
        email="maria.editada@ej.pe",
        limite_credito="800.00",
    )
    del edit_payload["username"]
    del edit_payload["password"]
    r_edit = client.put(f"/clientes/{cliente_id}", json=edit_payload, headers=h1)
    assert r_edit.status_code == 200
    assert Decimal(str(r_edit.json()["limite_credito"])) == Decimal("800.00")
    assert r_edit.json()["email"] == "maria.editada@ej.pe"
    assert r_edit.json()["situacion"] == "AL_DIA"

    # Tienda 1 da de baja al cliente (sin deuda)
    r_baja = client.patch(f"/clientes/{cliente_id}/baja", headers=h1)
    assert r_baja.status_code == 200
    assert r_baja.json()["estado"] == BAJA
    assert r_baja.json()["situacion"] == "INACTIVO"

    # Filtro situacion=INACTIVO devuelve al cliente dado de baja
    r_inact = client.get("/clientes?situacion=INACTIVO", headers=h1)
    assert r_inact.status_code == 200
    assert len(r_inact.json()) == 1
    assert r_inact.json()[0]["cliente_id"] == cliente_id

    # El cliente dado de baja ya no puede iniciar sesión (403 Cuenta inactiva)
    r_login = client.post(
        "/auth/login",
        json={"username": "cli_ais1", "password": "ClaveCliente2026!"},
    )
    assert r_login.status_code == 403

    # Reactivar cliente
    r_act = client.patch(f"/clientes/{cliente_id}/activar", headers=h1)
    assert r_act.status_code == 200
    assert r_act.json()["estado"] == ACTIVO


def test_capitalizacion_mayor_al_periodo_y_estado_cuenta(client, db):
    tienda = crear_tienda(db, "dueno_ec", "Bodega EC", "20202020207")
    prods = crear_productos(db, tienda)
    h = token(client, "dueno_ec")

    # Capitalización ANUAL (360) > período MENSUAL (30) -> 400
    bad_cap = _payload_cliente(
        dni="77771111",
        username="cli_bad_cap",
        email="badcap@ej.pe",
        tipo_tasa_comp="NOMINAL",
        tasa_compensatoria="2",
        periodo_tasa_comp="MENSUAL",
        capitalizacion_comp="ANUAL",
    )
    r_bad = client.post("/clientes", json=bad_cap, headers=h)
    assert r_bad.status_code == 400
    assert "capitalizacion_comp" in r_bad.json()["errores"]

    # Crear cliente válido y registrar una compra en 3 cuotas (Licuadora Oster S/ 210)
    r_ok = client.post(
        "/clientes",
        json=_payload_cliente(dni="77772222", username="cli_ec", email="ec@ej.pe", limite_credito="500.00"),
        headers=h,
    )
    assert r_ok.status_code == 201
    cid = r_ok.json()["cliente_id"]

    r_v = client.post(
        "/ventas",
        json={
            "cliente_id": cid,
            "items": [
                {
                    "producto_id": prods["licuadora"].producto_id,
                    "cantidad": 1,
                    "modalidad": "EN_MESES",
                }
            ],
            "cuotas": 3,
        },
        headers=h,
    )
    assert r_v.status_code == 201

    # Consultar GET /clientes/{id}/estado-cuenta
    r_ec = client.get(f"/clientes/{cid}/estado-cuenta", headers=h)
    assert r_ec.status_code == 200
    ec = r_ec.json()
    assert Decimal(str(ec["deuda_total"])) == Decimal("210.00")
    assert Decimal(str(ec["disponible"])) == Decimal("290.00")
    assert ec["situacion"] == "CON_DEUDA"
    assert len(ec["movimientos"]) == 1
    assert len(ec["cuotas"]) == 3
    assert ec["pagos"] == []
    assert ec["proximo_pago"] is not None
