"""Grupo Acceso: usuarios, tiendas y auditoria_sistema."""

from datetime import datetime

from sqlalchemy import text
from sqlalchemy import JSON, BigInteger, CHAR, ForeignKey, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.db import Base
from app.entidades.enums import Moneda, Rol
from app.entidades.tipos import ACTIVO, enum_pg


class Usuario(Base):
    """Credenciales y perfil de acceso."""

    __tablename__ = "usuarios"

    usuario_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String(20), unique=True)
    password_hash: Mapped[str] = mapped_column(String(64))  # bcrypt (60 caracteres)
    email: Mapped[str | None] = mapped_column(String(100), unique=True)
    nombres: Mapped[str] = mapped_column(String(80))
    rol: Mapped[Rol] = mapped_column(enum_pg(Rol, "rol_usuario"), default=Rol.CLIENTE, server_default=text("'CLIENTE'"))
    estado: Mapped[int] = mapped_column(SmallInteger, default=ACTIVO, server_default=text("1"))
    fecha_creacion: Mapped[datetime] = mapped_column(server_default=func.now())

    # Si el usuario es dueño de una tienda o es un cliente (como máximo uno de los dos).
    tienda: Mapped["Tienda | None"] = relationship(back_populates="admin")
    cliente: Mapped["Cliente | None"] = relationship(back_populates="usuario")  # noqa: F821


class Tienda(Base):
    """Comercio afiliado. Su administrador es un usuario con rol ADMIN_NEGOCIO."""

    __tablename__ = "tiendas"

    tienda_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    admin_usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.usuario_id"), unique=True
    )
    nombre_comercial: Mapped[str] = mapped_column(String(60))
    razon_social: Mapped[str | None] = mapped_column(String(150))
    ruc: Mapped[str | None] = mapped_column(String(11), unique=True)
    giro: Mapped[str | None] = mapped_column(String(40))
    direccion: Mapped[str | None] = mapped_column(String(200))
    distrito: Mapped[str | None] = mapped_column(String(60))
    telefono: Mapped[str | None] = mapped_column(CHAR(9))
    dueno_dni: Mapped[str | None] = mapped_column(CHAR(8))  # agregado (Fig. 3)
    moneda_defecto: Mapped[Moneda] = mapped_column(enum_pg(Moneda, "moneda_enum"), default=Moneda.PEN, server_default=text("'PEN'"))
    logo_url: Mapped[str | None] = mapped_column(String(255))
    estado: Mapped[int] = mapped_column(SmallInteger, default=ACTIVO, server_default=text("1"))

    admin: Mapped[Usuario] = relationship(back_populates="tienda")


class AuditoriaSistema(Base):
    """Registro de todas las operaciones (lo exige el enunciado)."""

    __tablename__ = "auditoria_sistema"

    log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Nulo cuando la operación la hace el sistema (corte automático).
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.usuario_id"))
    accion: Mapped[str] = mapped_column(String(50))
    tabla_afectada: Mapped[str] = mapped_column(String(50))
    registro_id: Mapped[int | None] = mapped_column(BigInteger)
    datos_anteriores: Mapped[dict | None] = mapped_column(JSON)
    datos_nuevos: Mapped[dict | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    fecha_hora: Mapped[datetime] = mapped_column(server_default=func.now())
