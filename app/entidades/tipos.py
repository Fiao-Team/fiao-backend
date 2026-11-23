"""Tipos de columna reutilizables, para escribirlos igual en todas las tablas."""

from enum import Enum as PyEnum

from sqlalchemy import Enum, Numeric

# Montos: decimal(12,2). Tasas en %: decimal(10,7).
MONTO = Numeric(12, 2)
TASA = Numeric(10, 7)

# Estado de las bajas lógicas (smallint en el DBML).
ACTIVO = 1
BAJA = 0


def enum_pg(clase: type[PyEnum], nombre: str) -> Enum:
    """Enum de PostgreSQL con el mismo nombre que en el DBML (la migración lo crea)."""
    return Enum(clase, name=nombre, values_callable=lambda e: [x.value for x in e])
