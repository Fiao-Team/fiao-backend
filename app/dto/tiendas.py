"""DTO de tiendas (Fig. 2 a 5): datos que entran y salen de las rutas /tiendas."""

from pydantic import BaseModel

from app.entidades.enums import Moneda


class TiendaItem(BaseModel):
    """Una tienda en el listado o detalle (Fig. 2)."""

    tienda_id: int
    nombre_comercial: str
    razon_social: str | None
    ruc: str | None
    giro: str | None
    direccion: str | None
    distrito: str | None
    telefono: str | None
    dueno_dni: str | None
    dueno_nombres: str
    dueno_email: str | None
    dueno_username: str
    moneda_defecto: Moneda
    logo_url: str | None
    estado: int
    clientes_count: int


class TiendaResumen(BaseModel):
    """Tarjetas KPI superiores de la pantalla de tiendas (Fig. 2)."""

    total: int
    activas: int
    inactivas: int


class TiendaListadoSalida(BaseModel):
    """Respuesta completa del listado de tiendas (Fig. 2)."""

    resumen: TiendaResumen
    giros: list[str]
    tiendas: list[TiendaItem]


class TiendaCrearEntrada(BaseModel):
    """Datos del formulario 'Registrar nueva tienda' (Fig. 3 y 4)."""

    nombre_comercial: str
    ruc: str
    direccion: str
    distrito: str
    telefono: str
    giro: str
    dueno_nombres: str
    dueno_dni: str
    dueno_email: str
    username: str
    password: str
    razon_social: str | None = None
    moneda_defecto: Moneda = Moneda.PEN
    logo_url: str | None = None


class TiendaActualizarEntrada(BaseModel):
    """Datos para editar una tienda y su dueño (acción Editar de la Fig. 2)."""

    nombre_comercial: str
    ruc: str
    direccion: str
    distrito: str
    telefono: str
    giro: str
    dueno_nombres: str
    dueno_dni: str
    dueno_email: str
    razon_social: str | None = None
    moneda_defecto: Moneda = Moneda.PEN
    logo_url: str | None = None
