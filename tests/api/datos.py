"""Datos de prueba reutilizables: tiendas, clientes de los Juegos y productos de los mockups.

Todo se crea dentro de la transacción de la prueba y se deshace al terminar.
"""

from datetime import datetime, time
from decimal import Decimal as D
from zoneinfo import ZoneInfo

from app.config.seguridad import hash_password
from app.entidades.acceso import Tienda, Usuario
from app.entidades.catalogo import Cliente, Producto
from app.entidades.enums import (
    CapitalizacionDias, FormaVentaProducto, Moneda, PeriodoDias, Rol, TipoTasa,
)
from app.main import app
from app.servicios.reloj_sistema import RelojSistema, obtener_reloj

CLAVE = "clave-de-prueba"
LIMA = ZoneInfo("America/Lima")

_hash_cache: dict[str, str] = {}


def _hash(clave: str) -> str:
    # bcrypt es lento a propósito: se calcula una sola vez para todas las pruebas.
    if clave not in _hash_cache:
        _hash_cache[clave] = hash_password(clave)
    return _hash_cache[clave]


def crear_usuario(db, username: str, rol: Rol, nombres: str = "Prueba") -> Usuario:
    u = Usuario(username=username, password_hash=_hash(CLAVE), nombres=nombres, rol=rol)
    db.add(u)
    db.flush()
    return u


def crear_tienda(db, username: str, nombre: str, ruc: str) -> Tienda:
    dueno = crear_usuario(db, username, Rol.ADMIN_NEGOCIO, f"Dueño {nombre}")
    t = Tienda(admin_usuario_id=dueno.usuario_id, nombre_comercial=nombre, ruc=ruc)
    db.add(t)
    db.flush()
    return t


def crear_cliente(db, tienda: Tienda, dni: str, nombres: str, **condiciones) -> Cliente:
    datos = dict(
        telefono="987654321", direccion="Av. Los Olivos 245", moneda=Moneda.PEN,
        limite_credito=D("500.00"), plazo_max_meses=6, dia_corte=20, hora_corte=time(23, 59),
        dia_pago=26, tipo_tasa_comp=TipoTasa.EFECTIVA, tasa_compensatoria=D("30"),
        periodo_tasa_comp=PeriodoDias.ANUAL, tipo_tasa_mora=TipoTasa.EFECTIVA,
        tasa_moratoria=D("5"), periodo_tasa_mora=PeriodoDias.ANUAL,
    )
    datos.update(condiciones)
    c = Cliente(tienda_id=tienda.tienda_id, dni=dni, nombres_apellidos=nombres, **datos)
    db.add(c)
    db.flush()
    return c


def crear_rosa(db, tienda: Tienda) -> Cliente:
    """Juego 1: 30 % efectiva anual, mora 5 % efectiva anual, límite 500, corte 20, pago 26."""
    return crear_cliente(db, tienda, "72819436", "Rosa Díaz")


def crear_carlos(db, tienda: Tienda) -> Cliente:
    """Juego 2: 30 % y 5 % nominales anuales con capitalización mensual, límite 700."""
    return crear_cliente(
        db, tienda, "41928653", "Carlos Mendoza", limite_credito=D("700.00"),
        tipo_tasa_comp=TipoTasa.NOMINAL, capitalizacion_comp=CapitalizacionDias.MENSUAL,
        tipo_tasa_mora=TipoTasa.NOMINAL, capitalizacion_mora=CapitalizacionDias.MENSUAL,
    )


# nombre, precio de lista, forma de venta (productos de las Fig. 7 y 14)
PRODUCTOS_PEN = {
    "arroz": ("Arroz Costeño 5 kg", "24.00", FormaVentaProducto.FIN_DE_MES),
    "aceite": ("Aceite vegetal 1 L", "11.20", FormaVentaProducto.FIN_DE_MES),
    "azucar": ("Azúcar rubia 1 kg", "4.60", FormaVentaProducto.FIN_DE_MES),
    "leche": ("Leche evaporada", "4.90", FormaVentaProducto.FIN_DE_MES),
    "fideos": ("Fideos 500 g", "4.70", FormaVentaProducto.FIN_DE_MES),
    "detergente": ("Detergente 800 g", "10.50", FormaVentaProducto.FIN_DE_MES),
    "gaseosa": ("Gaseosa 3 L", "13.00", FormaVentaProducto.FIN_DE_MES),
    "licuadora": ("Licuadora Oster", "210.00", FormaVentaProducto.AMBAS),
}


def crear_productos(db, tienda: Tienda) -> dict[str, Producto]:
    productos = {}
    for clave, (nombre, precio, forma) in PRODUCTOS_PEN.items():
        p = Producto(
            tienda_id=tienda.tienda_id, nombre=nombre, moneda=Moneda.PEN,
            precio_contado=D(precio), precio_lista=D(precio), forma_venta_credito=forma,
        )
        db.add(p)
        productos[clave] = p
    plancha = Producto(
        tienda_id=tienda.tienda_id, nombre="Plancha", moneda=Moneda.USD,
        precio_contado=D("120.00"), precio_lista=D("120.00"),
        forma_venta_credito=FormaVentaProducto.EN_MESES,
    )
    db.add(plancha)
    productos["plancha_usd"] = plancha
    db.flush()
    return productos


def fijar_momento(db, momento_lima: datetime) -> None:
    """Congela el reloj del sistema en una fecha y hora de Lima para las rutas."""
    real = momento_lima.replace(tzinfo=LIMA)
    app.dependency_overrides[obtener_reloj] = lambda: RelojSistema(db, hora_real=lambda: real)


def token(client, username: str) -> dict[str, str]:
    r = client.post("/auth/login", json={"username": username, "password": CLAVE})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
