"""Inicio de sesión con los 3 roles (pseudocódigo 4.2, Fig. 1)."""

from datetime import time
from decimal import Decimal as D

import pytest
from fastapi import Depends
from sqlalchemy import select

from app.comun.seguridad import hash_password
from app.comun.sesion import Sesion, requiere_rol
from app.dominio.enums import Rol
from app.main import app
from app.modelos import AuditoriaSistema, Cliente, Tienda, Usuario
from app.modelos.tipos import BAJA

CLAVE = "clave-de-prueba"


# Ruta solo para probar el candado requiere_rol (no existe en la app real).
@app.get("/_prueba/solo-negocio")
def _solo_negocio(sesion: Sesion = Depends(requiere_rol(Rol.ADMIN_NEGOCIO))):
    return {"tienda_id": sesion.tienda_id}


def crear_usuario(db, username, rol, nombres="Prueba"):
    u = Usuario(username=username, password_hash=hash_password(CLAVE), nombres=nombres, rol=rol)
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def datos(db):
    """Admin del sistema, una tienda con su dueño y una clienta."""
    admin = crear_usuario(db, "admin_t", Rol.ADMIN_SISTEMA)
    dueno = crear_usuario(db, "donpepe_t", Rol.ADMIN_NEGOCIO, "José Ramírez")
    tienda = Tienda(admin_usuario_id=dueno.usuario_id, nombre_comercial="Bodega Don Pepe", ruc="20123456789")
    db.add(tienda)
    db.flush()
    u_rosa = crear_usuario(db, "rosa_t", Rol.CLIENTE, "Rosa Díaz")
    rosa = Cliente(
        tienda_id=tienda.tienda_id, usuario_id=u_rosa.usuario_id, dni="72819436",
        nombres_apellidos="Rosa Díaz", telefono="987654321", direccion="Av. Los Olivos 245",
        limite_credito=D("500.00"), plazo_max_meses=6, dia_corte=20, hora_corte=time(23, 59),
        dia_pago=26, tasa_compensatoria=D("30"), tasa_moratoria=D("5"),
    )
    db.add(rosa)
    db.flush()
    return {"admin": admin, "dueno": dueno, "tienda": tienda, "u_rosa": u_rosa, "rosa": rosa}


def login(client, username, password=CLAVE):
    return client.post("/auth/login", json={"username": username, "password": password})


def token(client, username):
    return {"Authorization": f"Bearer {login(client, username).json()['access_token']}"}


# --- Inicio de sesión correcto, uno por rol ---

def test_login_admin_sistema(client, datos):
    r = login(client, "admin_t")
    assert r.status_code == 200
    assert r.json()["rol"] == "ADMIN_SISTEMA"
    assert r.json()["tienda_id"] is None


def test_login_admin_negocio_lleva_su_tienda(client, datos):
    r = login(client, "donpepe_t")
    assert r.status_code == 200
    assert r.json()["rol"] == "ADMIN_NEGOCIO"
    assert r.json()["tienda_id"] == datos["tienda"].tienda_id


def test_login_cliente_lleva_su_cliente(client, datos):
    r = login(client, "rosa_t")
    assert r.status_code == 200
    assert r.json()["cliente_id"] == datos["rosa"].cliente_id
    assert r.json()["tienda_id"] == datos["tienda"].tienda_id


# --- Errores ---

def test_clave_incorrecta(client, datos):
    r = login(client, "rosa_t", "otra-clave")
    assert r.status_code == 401
    assert r.json()["detail"] == "Usuario o contraseña incorrectos"


def test_usuario_inexistente_da_el_mismo_mensaje(client, datos):
    r = login(client, "nadie")
    assert r.status_code == 401
    assert r.json()["detail"] == "Usuario o contraseña incorrectos"


def test_tienda_de_baja_bloquea_al_dueno_y_a_sus_clientes(client, db, datos):
    datos["tienda"].estado = BAJA
    db.flush()
    assert login(client, "donpepe_t").status_code == 403
    assert login(client, "rosa_t").status_code == 403


def test_cliente_de_baja_no_puede_entrar(client, db, datos):
    datos["rosa"].estado = BAJA
    db.flush()
    r = login(client, "rosa_t")
    assert (r.status_code, r.json()["detail"]) == (403, "Cuenta inactiva")


def test_baja_bloquea_aunque_ya_tenga_token(client, db, datos):
    cabecera = token(client, "donpepe_t")
    datos["tienda"].estado = BAJA
    db.flush()
    assert client.get("/auth/yo", headers=cabecera).status_code == 403


# --- Auditoría ---

def test_login_queda_en_auditoria(client, db, datos):
    login(client, "rosa_t")
    registro = db.scalar(select(AuditoriaSistema).where(AuditoriaSistema.usuario_id == datos["u_rosa"].usuario_id))
    assert (registro.accion, registro.tabla_afectada) == ("LOGIN", "usuarios")


# --- Sesión y candado por rol ---

def test_sin_token_no_hay_acceso(client, datos):
    assert client.get("/auth/yo").status_code == 401


def test_token_falso_no_sirve(client, datos):
    assert client.get("/auth/yo", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401


def test_candado_por_rol(client, datos):
    ok = client.get("/_prueba/solo-negocio", headers=token(client, "donpepe_t"))
    assert ok.status_code == 200
    assert ok.json() == {"tienda_id": datos["tienda"].tienda_id}

    assert client.get("/_prueba/solo-negocio", headers=token(client, "rosa_t")).status_code == 403
    assert client.get("/_prueba/solo-negocio", headers=token(client, "admin_t")).status_code == 403
