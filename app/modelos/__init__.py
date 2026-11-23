"""Modelos: una clase por tabla de fiao_corregido.dbml.

Se importan todos aquí para que SQLAlchemy y Alembic los conozcan.
"""

from app.modelos.acceso import AuditoriaSistema, Tienda, Usuario
from app.modelos.catalogo import Cliente, Producto
from app.modelos.cobro import DetalleListadoPago, ListadoPago, Pago
from app.modelos.configuracion import ParametrosSistema, TasaMaximaBcrp
from app.modelos.venta import DetalleTransaccion, PlanPago, Transaccion

__all__ = [
    "AuditoriaSistema", "Cliente", "DetalleListadoPago", "DetalleTransaccion",
    "ListadoPago", "Pago", "ParametrosSistema", "PlanPago", "Producto",
    "TasaMaximaBcrp", "Tienda", "Transaccion", "Usuario",
]
