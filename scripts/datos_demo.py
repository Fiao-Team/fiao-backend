"""Datos de prueba para usar la app en el navegador (SOLO DESARROLLO).

Crea la tienda Bodega Don Pepe, su dueño, los clientes de los Juegos 1, 2 y 3
y los productos de los mockups. Si algo ya existe, no lo duplica.

Uso (desde fiao-backend):
    .\\.venv\\Scripts\\python.exe -m scripts.datos_demo
    .\\.venv\\Scripts\\python.exe -m scripts.datos_demo --fecha-simulada 2026-09-15
    .\\.venv\\Scripts\\python.exe -m scripts.datos_demo --sin-fecha-simulada

Usuarios creados (contraseña = DEMO_PASSWORD del .env):
    donpepe  administrador del negocio (Bodega Don Pepe)
    rosa     cliente, Juego 1 (soles, 30 % efectiva anual)
    carlos   cliente, Juego 2 (soles, 30 % nominal anual cap. mensual)
    luis     cliente, Juego 3 (dólares, 2 % efectiva mensual)
"""

import argparse
from datetime import date, time
from decimal import Decimal as D

from sqlalchemy import select

import app.entidades.todas  # noqa: F401  (carga las 13 tablas)
from app.config.configuracion import get_settings
from app.config.db import SessionLocal
from app.config.seguridad import hash_password
from app.entidades.acceso import Tienda, Usuario
from app.entidades.catalogo import Cliente, Producto
from app.entidades.configuracion import ParametrosSistema
from app.entidades.enums import (
    CapitalizacionDias, FormaVentaProducto, Moneda, PeriodoDias, Rol, TipoTasa,
)

FIN, MESES, AMBAS = (
    FormaVentaProducto.FIN_DE_MES, FormaVentaProducto.EN_MESES, FormaVentaProducto.AMBAS,
)

# nombre, marca, categoría, moneda, precio contado, precio de lista, forma de venta (Fig. 7 y 14)
PRODUCTOS = [
    ("Arroz Costeño 5 kg", "Costeño", "Abarrotes", Moneda.PEN, "22.50", "24.00", FIN),
    ("Aceite vegetal 1 L", "Primor", "Abarrotes", Moneda.PEN, "10.50", "11.20", FIN),
    ("Azúcar rubia 1 kg", "Cartavio", "Abarrotes", Moneda.PEN, "4.20", "4.60", FIN),
    ("Leche evaporada", "Gloria", "Lácteos", Moneda.PEN, "4.50", "4.90", FIN),
    ("Pan francés x10", "Don Pepe", "Panadería", Moneda.PEN, "4.00", "4.50", FIN),
    ("Gaseosa 3 L", "Inca Kola", "Bebidas", Moneda.PEN, "12.00", "13.00", FIN),
    ("Detergente 800 g", "Bolívar", "Limpieza", Moneda.PEN, "9.80", "10.50", FIN),
    ("Fideos 500 g", "Don Vittorio", "Abarrotes", Moneda.PEN, "4.30", "4.70", FIN),
    ("Huevos x12", "La Calera", "Frescos", Moneda.PEN, "9.00", "10.00", FIN),
    ("Licuadora Oster", "Oster", "Electrodomésticos", Moneda.PEN, "199.00", "210.00", AMBAS),
    ("Abarrotes (canasta)", None, "Abarrotes", Moneda.USD, "75.00", "80.00", FIN),
    ("Plancha", "Imaco", "Electrodomésticos", Moneda.USD, "110.00", "120.00", MESES),
]


def _usuario(db, username, rol, nombres, clave) -> Usuario:
    u = db.scalar(select(Usuario).where(Usuario.username == username))
    if u is None:
        u = Usuario(username=username, password_hash=hash_password(clave), nombres=nombres, rol=rol)
        db.add(u)
        db.flush()
        print(f"  + usuario {username}")
    return u


def _cliente(db, tienda, username, clave, dni, nombres, **condiciones) -> None:
    if db.scalar(select(Cliente).where(Cliente.tienda_id == tienda.tienda_id, Cliente.dni == dni)):
        return
    usuario = _usuario(db, username, Rol.CLIENTE, nombres, clave)
    datos = dict(
        telefono="987654321", direccion="Lima", moneda=Moneda.PEN, plazo_max_meses=6,
        dia_corte=20, hora_corte=time(23, 59), dia_pago=26,
        tipo_tasa_comp=TipoTasa.EFECTIVA, tasa_compensatoria=D("30"), periodo_tasa_comp=PeriodoDias.ANUAL,
        tipo_tasa_mora=TipoTasa.EFECTIVA, tasa_moratoria=D("5"), periodo_tasa_mora=PeriodoDias.ANUAL,
    )
    datos.update(condiciones)
    db.add(Cliente(tienda_id=tienda.tienda_id, usuario_id=usuario.usuario_id, dni=dni,
                   nombres_apellidos=nombres, **datos))
    print(f"  + cliente {nombres}")


def cargar(fecha_simulada: date | None, quitar_fecha: bool) -> None:
    clave = get_settings().demo_password
    if not clave or len(clave) < 8:
        raise SystemExit("Falta DEMO_PASSWORD en el archivo .env (mínimo 8 caracteres).")

    with SessionLocal() as db:
        dueno = _usuario(db, "donpepe", Rol.ADMIN_NEGOCIO, "José Ramírez", clave)
        tienda = db.scalar(select(Tienda).where(Tienda.admin_usuario_id == dueno.usuario_id))
        if tienda is None:
            tienda = Tienda(
                admin_usuario_id=dueno.usuario_id, nombre_comercial="Bodega Don Pepe",
                razon_social="Bodega Don Pepe E.I.R.L.", ruc="20123456789", giro="Bodega",
                direccion="Av. Los Olivos 245", distrito="Los Olivos", telefono="987123456",
                dueno_dni="40123456",
            )
            db.add(tienda)
            db.flush()
            print("  + tienda Bodega Don Pepe")

        _cliente(db, tienda, "rosa", clave, "72819436", "Rosa Díaz", limite_credito=D("500.00"))
        _cliente(db, tienda, "carlos", clave, "41928653", "Carlos Mendoza", limite_credito=D("700.00"),
                 tipo_tasa_comp=TipoTasa.NOMINAL, capitalizacion_comp=CapitalizacionDias.MENSUAL,
                 tipo_tasa_mora=TipoTasa.NOMINAL, capitalizacion_mora=CapitalizacionDias.MENSUAL)
        _cliente(db, tienda, "luis", clave, "45678912", "Luis Ramos", moneda=Moneda.USD,
                 limite_credito=D("300.00"), dia_corte=25, dia_pago=10,
                 tasa_compensatoria=D("2"), periodo_tasa_comp=PeriodoDias.MENSUAL)

        for nombre, marca, categoria, moneda, contado, lista, forma in PRODUCTOS:
            existe = db.scalar(select(Producto).where(
                Producto.tienda_id == tienda.tienda_id, Producto.nombre == nombre))
            if existe is None:
                db.add(Producto(
                    tienda_id=tienda.tienda_id, nombre=nombre, marca=marca, categoria=categoria,
                    moneda=moneda, precio_contado=D(contado), precio_lista=D(lista),
                    forma_venta_credito=forma,
                ))
                print(f"  + producto {nombre}")

        if fecha_simulada or quitar_fecha:
            parametros = db.scalar(select(ParametrosSistema).limit(1))
            if parametros is None:  # la migración 0002 la crea; por si acaso
                parametros = ParametrosSistema(parametro_id=1)
                db.add(parametros)
            parametros.fecha_simulada = None if quitar_fecha else fecha_simulada
            print(f"  * fecha simulada: {parametros.fecha_simulada or 'ninguna (fecha real)'}")

        db.commit()
    print("Listo.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Carga datos de prueba (solo desarrollo).")
    parser.add_argument("--fecha-simulada", type=date.fromisoformat, help="AAAA-MM-DD")
    parser.add_argument("--sin-fecha-simulada", action="store_true", help="vuelve a la fecha real")
    args = parser.parse_args()
    cargar(args.fecha_simulada, args.sin_fecha_simulada)
