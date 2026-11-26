"""Pruebas del Dashboard Inicio del Dueño de Negocio (Fig. 6 — GET /negocio/inicio)."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.entidades.cobro import ListadoPago
from app.entidades.enums import EstadoListado, Moneda, Rol
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
def reloj_fijo(db):
    fijar_momento(db, datetime(2026, 9, 28, 10, 0))
    yield
    app.dependency_overrides.pop(obtener_reloj, None)


def test_rbac_inicio_negocio(client, db):
    crear_usuario(db, "admin_ini", Rol.ADMIN_SISTEMA, "Admin")
    assert client.get("/negocio/inicio", headers=token(client, "admin_ini")).status_code == 403

    tienda = crear_tienda(db, "dueno_ini", "Bodega Inicio", "20303030301")
    c = crear_cliente(db, tienda, "78881111", "Cliente Ini")
    u_cli = crear_usuario(db, "cli_ini", Rol.CLIENTE, "Cliente Ini")
    c.usuario_id = u_cli.usuario_id
    db.flush()
    assert client.get("/negocio/inicio", headers=token(client, "cli_ini")).status_code == 403

    resp = client.get("/negocio/inicio", headers=token(client, "dueno_ini"))
    assert resp.status_code == 200
    assert resp.json()["clientes_activos"] == 1


def test_kpis_separados_por_moneda_y_cliente_en_mora(client, db):
    tienda = crear_tienda(db, "dueno_kpi", "Bodega KPI", "20303030302")
    prods = crear_productos(db, tienda)
    c_pen = crear_cliente(db, tienda, "78882222", "Carlos Mora", moneda=Moneda.PEN, limite_credito=Decimal("700.00"))
    c_usd = crear_cliente(db, tienda, "78883333", "Lucía Dólares", moneda=Moneda.USD, limite_credito=Decimal("500.00"))
    h = token(client, "dueno_kpi")

    # Venta PEN a Carlos (S/ 48.00) y venta USD a Lucía (US$ 120.00 en 2 cuotas)
    r1 = client.post(
        "/ventas",
        json={
            "cliente_id": c_pen.cliente_id,
            "items": [{"producto_id": prods["arroz"].producto_id, "cantidad": 2, "modalidad": "FIN_DE_MES"}],
        },
        headers=h,
    )
    assert r1.status_code == 201

    r2 = client.post(
        "/ventas",
        json={
            "cliente_id": c_usd.cliente_id,
            "items": [{"producto_id": prods["plancha_usd"].producto_id, "cantidad": 1, "modalidad": "EN_MESES"}],
            "cuotas": 2,
        },
        headers=h,
    )
    assert r2.status_code == 201

    # Listado vencido de hace 2 días para Carlos (hoy = 2026-09-28, pactada = 2026-09-26)
    db.add(
        ListadoPago(
            cliente_id=c_pen.cliente_id,
            fecha_corte=date(2026, 9, 20),
            fecha_pago_pactada=date(2026, 9, 26),
            subtotal=Decimal("200.00"),
            tea_comp_aplicada=Decimal("30.0000000"),
            tea_mora_aplicada=Decimal("5.0000000"),
            total=Decimal("200.00"),
            estado=EstadoListado.PENDIENTE,
        )
    )
    db.flush()

    resp = client.get("/negocio/inicio", headers=h)
    assert resp.status_code == 200
    data = resp.json()

    assert data["clientes_activos"] == 2
    assert Decimal(str(data["total_por_cobrar_pen"])) == Decimal("48.00")
    assert Decimal(str(data["total_por_cobrar_usd"])) == Decimal("120.00")
    assert Decimal(str(data["credito_este_mes_pen"])) == Decimal("48.00")
    assert Decimal(str(data["credito_este_mes_usd"])) == Decimal("120.00")
    assert data["ventas_este_mes_count"] == 2
    assert data["clientes_en_mora_count"] == 1
    assert len(data["clientes_en_mora"]) == 1
    assert data["clientes_en_mora"][0]["dias_atraso"] == 2
    assert Decimal(str(data["clientes_en_mora"][0]["monto_vencido"])) > Decimal("200.00")
    assert data["proximos_vencimientos"][0]["situacion"] == "EN_MORA"
