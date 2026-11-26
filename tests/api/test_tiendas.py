"""Pruebas de tiendas — Administrador del Sistema (pseudocódigo 4.3, Fig. 2 a 5)."""

import pytest
from sqlalchemy import select

from app.entidades.acceso import AuditoriaSistema, Tienda
from app.entidades.enums import Rol
from app.entidades.tipos import ACTIVO, BAJA
from tests.api.datos import crear_cliente, crear_rosa, crear_tienda, crear_usuario, token


def _payload_tienda(**overrides) -> dict:
    base = {
        "nombre_comercial": "Panadería San José",
        "ruc": "20456789123",
        "direccion": "Av. Universitaria 1200",
        "distrito": "Los Olivos",
        "telefono": "987654321",
        "giro": "Panadería",
        "dueno_nombres": "María Torres",
        "dueno_dni": "40123456",
        "dueno_email": "maria@sanjose.pe",
        "username": "sanjose",
        "password": "ClaveSegura123",
    }
    base.update(overrides)
    return base


@pytest.fixture
def admin_headers(client, db):
    crear_usuario(db, "admin_sys", Rol.ADMIN_SISTEMA, "Milagros Salazar")
    return token(client, "admin_sys")


# --- Permisos / RBAC ---


def test_solo_admin_sistema_accede_a_tiendas(client, db):
    crear_tienda(db, "dueno_perm", "Bodega Uno", "20111111111")
    crear_usuario(db, "cli_perm", Rol.CLIENTE, "Cliente Uno")

    assert client.get("/tiendas").status_code == 401
    assert client.get("/tiendas", headers=token(client, "dueno_perm")).status_code == 403
    assert client.get("/tiendas", headers=token(client, "cli_perm")).status_code == 403
    assert client.post("/tiendas", json=_payload_tienda(), headers=token(client, "dueno_perm")).status_code == 403


# --- Registrar tienda (Fig. 3 y 4) ---


def test_registrar_tienda_correcto_y_login_del_dueno(client, db, admin_headers):
    r = client.post("/tiendas", json=_payload_tienda(), headers=admin_headers)
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["nombre_comercial"] == "Panadería San José"
    assert cuerpo["ruc"] == "20456789123"
    assert cuerpo["dueno_dni"] == "40123456"
    assert cuerpo["dueno_username"] == "sanjose"
    assert cuerpo["estado"] == ACTIVO
    assert cuerpo["clientes_count"] == 0

    # El dueño creado puede iniciar sesión inmediatamente con rol ADMIN_NEGOCIO
    login = client.post("/auth/login", json={"username": "sanjose", "password": "ClaveSegura123"})
    assert login.status_code == 200
    assert login.json()["rol"] == "ADMIN_NEGOCIO"
    assert login.json()["tienda_id"] == cuerpo["tienda_id"]

    # Queda registrado en auditoría
    log = db.scalar(
        select(AuditoriaSistema).where(
            AuditoriaSistema.accion == "ALTA",
            AuditoriaSistema.tabla_afectada == "tiendas",
            AuditoriaSistema.registro_id == cuerpo["tienda_id"],
        )
    )
    assert log is not None


def test_registrar_tienda_valida_campos_fig4(client, admin_headers):
    invalido = _payload_tienda(
        nombre_comercial="  ",
        ruc="15515fffcdf",
        direccion="",
        distrito="",
        telefono="12345",
        giro="",
        dueno_nombres="",
        dueno_dni="123",
        dueno_email="correo-malo",
        username="ab",
        password="123",
    )
    r = client.post("/tiendas", json=invalido, headers=admin_headers)
    assert r.status_code == 400
    errores = r.json()["errores"]
    assert errores["nombre_comercial"] == "Ingresa el nombre comercial"
    assert errores["ruc"] == "Debe tener 11 dígitos y empezar con 10 o 20"
    assert errores["direccion"] == "Ingresa la dirección"
    assert errores["distrito"] == "Ingresa el distrito"
    assert errores["telefono"] == "Debe tener 9 dígitos"
    assert errores["giro"] == "Selecciona un giro"
    assert errores["dueno_nombres"] == "Ingresa nombres y apellidos"
    assert errores["dueno_dni"] == "Debe tener 8 dígitos"
    assert errores["dueno_email"] == "Ingresa un correo válido"
    assert errores["username"] == "Mínimo 3 caracteres"
    assert errores["password"] == "Mínimo 8 caracteres"


def test_registrar_tienda_rechaza_duplicados_y_espacios_en_usuario(client, admin_headers):
    assert client.post("/tiendas", json=_payload_tienda(), headers=admin_headers).status_code == 201

    duplicado = _payload_tienda(username="sanjose", ruc="20456789123", dueno_email="maria@sanjose.pe")
    r = client.post("/tiendas", json=duplicado, headers=admin_headers)
    assert r.status_code == 400
    errores = r.json()["errores"]
    assert errores["ruc"] == "RUC ya registrado"
    assert errores["username"] == "Usuario ya existe"
    assert errores["dueno_email"] == "Correo ya registrado"

    con_espacio = _payload_tienda(ruc="10456789123", username="san jose", dueno_email="otro@sanjose.pe")
    r2 = client.post("/tiendas", json=con_espacio, headers=admin_headers)
    assert r2.status_code == 400
    assert "espacios" in r2.json()["errores"]["username"]


# --- Listar tiendas con KPIs, conteo de clientes y filtros (Fig. 2) ---


def test_listar_tiendas_kpis_clientes_y_filtros(client, db, admin_headers):
    t1 = crear_tienda(db, "bodega_u", "Bodega Don Pepe", "20123456789")
    t1.giro = "Bodega"
    t2 = crear_tienda(db, "polleria_u", "Pollería El Sabor", "20678912345")
    t2.giro = "Pollería"
    t2.estado = BAJA
    crear_rosa(db, t1)
    crear_cliente(db, t1, "41928653", "Carlos Mendoza")
    db.flush()

    r = client.get("/tiendas", headers=admin_headers)
    assert r.status_code == 200
    datos = r.json()
    assert datos["resumen"] == {"total": 2, "activas": 1, "inactivas": 1}
    assert datos["giros"] == ["Bodega", "Pollería"]
    assert len(datos["tiendas"]) == 2
    assert datos["tiendas"][0]["nombre_comercial"] == "Bodega Don Pepe"
    assert datos["tiendas"][0]["clientes_count"] == 2

    # Filtro por búsqueda (RUC)
    por_ruc = client.get("/tiendas?buscar=20678912345", headers=admin_headers).json()
    assert [t["nombre_comercial"] for t in por_ruc["tiendas"]] == ["Pollería El Sabor"]

    # Filtro por giro
    por_giro = client.get("/tiendas?giro=Bodega", headers=admin_headers).json()
    assert [t["nombre_comercial"] for t in por_giro["tiendas"]] == ["Bodega Don Pepe"]

    # Filtro por estado
    solo_inactivas = client.get("/tiendas?estado=INACTIVA", headers=admin_headers).json()
    assert [t["nombre_comercial"] for t in solo_inactivas["tiendas"]] == ["Pollería El Sabor"]


# --- Editar tienda (Fig. 2) ---


def test_editar_tienda_y_auditoria(client, db, admin_headers):
    creada = client.post("/tiendas", json=_payload_tienda(), headers=admin_headers).json()
    tid = creada["tienda_id"]

    actualizado = _payload_tienda(
        nombre_comercial="Panadería San José Central",
        distrito="San Martín de Porres",
        dueno_nombres="María Torres Vega",
    )
    actualizado.pop("username")
    actualizado.pop("password")

    r = client.put(f"/tiendas/{tid}", json=actualizado, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["nombre_comercial"] == "Panadería San José Central"
    assert r.json()["distrito"] == "San Martín de Porres"
    assert r.json()["dueno_nombres"] == "María Torres Vega"

    log = db.scalar(
        select(AuditoriaSistema).where(
            AuditoriaSistema.accion == "EDICION",
            AuditoriaSistema.tabla_afectada == "tiendas",
            AuditoriaSistema.registro_id == tid,
        )
    )
    assert log is not None
    assert log.datos_anteriores["nombre_comercial"] == "Panadería San José"
    assert log.datos_nuevos["nombre_comercial"] == "Panadería San José Central"


# --- Baja lógica y reactivación (Fig. 2 y Fig. 5) ---


def test_dar_de_baja_y_reactivar_tienda(client, db, admin_headers):
    creada = client.post("/tiendas", json=_payload_tienda(), headers=admin_headers).json()
    tid = creada["tienda_id"]

    # Dar de baja
    baja = client.patch(f"/tiendas/{tid}/baja", headers=admin_headers)
    assert baja.status_code == 200
    assert baja.json()["estado"] == BAJA

    # El dueño ya no puede iniciar sesión
    login_baja = client.post("/auth/login", json={"username": "sanjose", "password": "ClaveSegura123"})
    assert login_baja.status_code == 403

    # Doble baja da 400
    assert client.patch(f"/tiendas/{tid}/baja", headers=admin_headers).status_code == 400

    # Reactivar
    activar = client.patch(f"/tiendas/{tid}/activar", headers=admin_headers)
    assert activar.status_code == 200
    assert activar.json()["estado"] == ACTIVO

    # El dueño vuelve a poder ingresar
    login_ok = client.post("/auth/login", json={"username": "sanjose", "password": "ClaveSegura123"})
    assert login_ok.status_code == 200

    # Ambas operaciones quedaron auditadas
    acciones = db.scalars(
        select(AuditoriaSistema.accion).where(
            AuditoriaSistema.tabla_afectada == "tiendas",
            AuditoriaSistema.registro_id == tid,
        )
    ).all()
    assert {"ALTA", "BAJA", "REACTIVACION"}.issubset(set(acciones))

    # Tienda inexistente -> 404
    assert client.get("/tiendas/999999", headers=admin_headers).status_code == 404
