"""Carga las 13 entidades para que SQLAlchemy y Alembic las conozcan.

Lo importan main.py (al arrancar la app), alembic/env.py y las pruebas.
"""

from app.entidades.acceso import AuditoriaSistema, Tienda, Usuario
from app.entidades.catalogo import Cliente, Producto
from app.entidades.cobro import DetalleListadoPago, ListadoPago, Pago
from app.entidades.configuracion import ParametrosSistema, TasaMaximaBcrp
from app.entidades.venta import DetalleTransaccion, PlanPago, Transaccion

__all__ = [
    "AuditoriaSistema", "Cliente", "DetalleListadoPago", "DetalleTransaccion",
    "ListadoPago", "Pago", "ParametrosSistema", "PlanPago", "Producto",
    "TasaMaximaBcrp", "Tienda", "Transaccion", "Usuario",
]
