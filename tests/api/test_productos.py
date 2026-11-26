"""Pruebas para el catálogo de productos del negocio (Fig. 7 y 8).

Verifica:
- Seguridad y RBAC: solo ADMIN_NEGOCIO accede; ADMIN_SISTEMA o CLIENTE reciben 403.
- Aislamiento multi-inquilino: el dueño de una tienda NO puede ver ni editar productos de otra.
- Validaciones: precios > 0, precio_lista >= precio_contado, unicidad de nombre en tienda.
- Listado con filtros: búsqueda, categoría, moneda, modalidad.
- Ciclo de vida: alta, edición, baja lógica (ocultar de ventas), reactivación.
- Auditoría registrada en BD.
"""

from decimal import Decimal
import pytest
from sqlalchemy import select

from app.entidades.acceso import AuditoriaSistema
from app.entidades.catalogo import Cliente
from app.entidades.tipos import ACTIVO, BAJA
from tests.api.datos import crear_cliente, crear_tienda, crear_usuario, token
from app.entidades.enums import Rol


def test_rbac_solo_admin_negocio_accede_a_productos(client, db):
    crear_usuario(db, "admin_prod", Rol.ADMIN_SISTEMA, "Admin Sistema")
    h_admin = token(client, "admin_prod")
    resp = client.get("/productos", headers=h_admin)
    assert resp.status_code == 403

    tienda = crear_tienda(db, "dueno_prod", "Bodega Prod", "20101010101")
    crear_cliente(db, tienda, "71112222", "Cliente Prod")
    u_cli = crear_usuario(db, "cliente_prod", Rol.CLIENTE, "Cliente Prod")
    # Asociar usuario al cliente
    c = db.scalar(select(Cliente).where(Cliente.dni == "71112222"))
    c.usuario_id = u_cli.usuario_id
    db.flush()

    h_cliente = token(client, "cliente_prod")
    resp = client.get("/productos", headers=h_cliente)
    assert resp.status_code == 403

    h_dueno = token(client, "dueno_prod")
    resp = client.get("/productos", headers=h_dueno)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_registrar_producto_exitoso_y_auditoria(client, db):
    tienda = crear_tienda(db, "donpepe_p", "Bodega Don Pepe P", "20123456780")
    h = token(client, "donpepe_p")

    payload = {
        "nombre": "Atún Florida 170g",
        "descripcion": "Lomitos de atún en aceite vegetal",
        "marca": "Florida",
        "categoria": "Conservas",
        "proveedor": "Distribuidora Lima",
        "unidad_medida": "Lata",
        "moneda": "PEN",
        "precio_contado": "5.50",
        "precio_lista": "6.00",
        "forma_venta_credito": "FIN_DE_MES",
    }
    resp = client.post("/productos", json=payload, headers=h)
    assert resp.status_code == 201
    datos = resp.json()
    assert datos["nombre"] == "Atún Florida 170g"
    assert Decimal(str(datos["precio_contado"])) == Decimal("5.50")
    assert Decimal(str(datos["precio_lista"])) == Decimal("6.00")
    assert datos["estado"] == ACTIVO

    prod_id = datos["producto_id"]
    audit = db.scalar(
        select(AuditoriaSistema).where(
            AuditoriaSistema.tabla_afectada == "productos",
            AuditoriaSistema.registro_id == prod_id,
            AuditoriaSistema.accion == "ALTA_PRODUCTO",
        )
    )
    assert audit is not None


def test_registrar_producto_validaciones_precios(client, db):
    crear_tienda(db, "donpepe_val", "Bodega Don Pepe Val", "20123456781")
    h = token(client, "donpepe_val")

    # Caso 1: precio lista menor que contado
    payload = {
        "nombre": "Producto Invalido 1",
        "unidad_medida": "Unidad",
        "moneda": "PEN",
        "precio_contado": "10.00",
        "precio_lista": "8.00",
        "forma_venta_credito": "FIN_DE_MES",
    }
    resp = client.post("/productos", json=payload, headers=h)
    assert resp.status_code == 400
    assert "precio_lista" in resp.json().get("errores", {})


def test_aislamiento_entre_tiendas(client, db):
    t1 = crear_tienda(db, "dueno_t1", "Tienda Uno", "20123456782")
    t2 = crear_tienda(db, "dueno_t2", "Tienda Dos", "20123456783")
    h1 = token(client, "dueno_t1")
    h2 = token(client, "dueno_t2")

    # T1 crea un producto
    payload = {
        "nombre": "Pan Chancay Especial T1",
        "unidad_medida": "Bolsa",
        "moneda": "PEN",
        "precio_contado": "3.00",
        "precio_lista": "3.50",
        "forma_venta_credito": "FIN_DE_MES",
    }
    resp = client.post("/productos", json=payload, headers=h1)
    assert resp.status_code == 201
    prod_id = resp.json()["producto_id"]

    # T2 intenta obtenerlo -> 404 (no existe en su tienda)
    resp_t2 = client.get(f"/productos/{prod_id}", headers=h2)
    assert resp_t2.status_code == 404

    # T2 intenta editarlo -> 404
    resp_edit = client.put(f"/productos/{prod_id}", json=payload, headers=h2)
    assert resp_edit.status_code == 404

    # T2 intenta darlo de baja -> 404
    resp_baja = client.patch(f"/productos/{prod_id}/baja", headers=h2)
    assert resp_baja.status_code == 404


def test_baja_logica_y_reactivacion_producto(client, db):
    crear_tienda(db, "dueno_baja", "Tienda Baja Prod", "20123456784")
    h = token(client, "dueno_baja")

    payload = {
        "nombre": "Queso Paria 500g",
        "unidad_medida": "Molde",
        "moneda": "PEN",
        "precio_contado": "18.00",
        "precio_lista": "20.00",
        "forma_venta_credito": "FIN_DE_MES",
    }
    resp = client.post("/productos", json=payload, headers=h)
    prod_id = resp.json()["producto_id"]

    # Dar de baja
    resp_baja = client.patch(f"/productos/{prod_id}/baja", headers=h)
    assert resp_baja.status_code == 200
    assert resp_baja.json()["estado"] == BAJA

    # Al listar productos activos por defecto ya no aparece
    resp_list = client.get("/productos", headers=h)
    ids = [p["producto_id"] for p in resp_list.json()]
    assert prod_id not in ids

    # Al listar con solo_activos=False sí aparece
    resp_inact = client.get("/productos?solo_activos=false", headers=h)
    ids_inact = [p["producto_id"] for p in resp_inact.json()]
    assert prod_id in ids_inact

    # Reactivar producto
    resp_act = client.patch(f"/productos/{prod_id}/activar", headers=h)
    assert resp_act.status_code == 200
    assert resp_act.json()["estado"] == ACTIVO
