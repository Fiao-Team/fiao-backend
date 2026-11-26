"""Lógica de negocio y catálogo de productos por tienda (Fig. 7 y 8).

Reglas:
- Operaciones restringidas estrictamente a la tienda de la sesión (`sesion.tienda_id`).
- Precios > 0 con escala de 2 decimales.
- `precio_lista` debe ser >= `precio_contado`.
- No duplicar producto con mismo nombre en la misma tienda.
- Auditoría registrada en cada ALTA, EDICION, BAJA y REACTIVACION.
"""

from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.auditoria import registrar_auditoria
from app.config.sesion import Sesion
from app.dto.productos import ActualizarProductoDTO, ProductoResumenDTO, RegistrarProductoDTO
from app.entidades.catalogo import Producto
from app.entidades.enums import FormaVentaProducto, Moneda
from app.entidades.tipos import ACTIVO, BAJA
from app.excepciones.errores import ErrorNegocio, NoEncontrado


def _validar_precios(contado: Decimal, lista: Decimal) -> None:
    errores: dict[str, str] = {}
    if contado <= 0:
        errores["precio_contado"] = "El precio al contado debe ser mayor a 0."
    if lista <= 0:
        errores["precio_lista"] = "El precio de lista debe ser mayor a 0."
    if contado > 0 and lista > 0 and lista < contado:
        errores["precio_lista"] = "El precio de lista no puede ser menor al precio al contado."

    if errores:
        raise ErrorNegocio("Errores de validación en el formulario.", errores=errores)


def listar_productos(
    db: Session,
    sesion: Sesion,
    buscar: str | None = None,
    categoria: str | None = None,
    moneda: Moneda | None = None,
    forma_venta: FormaVentaProducto | None = None,
    solo_activos: bool = True,
) -> list[ProductoResumenDTO]:
    """Lista el catálogo de la tienda del usuario actual con filtros opcionales."""
    if sesion.tienda_id is None:
        raise ErrorNegocio("El usuario no administra ninguna tienda.")

    stmt = select(Producto).where(Producto.tienda_id == sesion.tienda_id)

    if solo_activos:
        stmt = stmt.where(Producto.estado == ACTIVO)

    if buscar:
        termino = f"%{buscar.strip()}%"
        stmt = stmt.where(
            (Producto.nombre.ilike(termino))
            | (Producto.marca.ilike(termino))
            | (Producto.proveedor.ilike(termino))
        )

    if categoria:
        stmt = stmt.where(Producto.categoria.ilike(f"%{categoria.strip()}%"))

    if moneda:
        stmt = stmt.where(Producto.moneda == moneda)

    if forma_venta:
        stmt = stmt.where(
            (Producto.forma_venta_credito == forma_venta)
            | (Producto.forma_venta_credito == FormaVentaProducto.AMBAS)
        )

    stmt = stmt.order_by(Producto.nombre)
    productos = db.scalars(stmt).all()
    return [ProductoResumenDTO.model_validate(p) for p in productos]


def obtener_producto(db: Session, sesion: Sesion, producto_id: int) -> ProductoResumenDTO:
    """Obtiene el detalle de un producto garantizando pertenencia a la tienda."""
    if sesion.tienda_id is None:
        raise ErrorNegocio("El usuario no administra ninguna tienda.")

    p = db.scalar(
        select(Producto).where(
            Producto.producto_id == producto_id,
            Producto.tienda_id == sesion.tienda_id,
        )
    )
    if not p:
        raise NoEncontrado(f"Producto {producto_id} no encontrado en su tienda.")
    return ProductoResumenDTO.model_validate(p)


def registrar_producto(
    db: Session,
    sesion: Sesion,
    dto: RegistrarProductoDTO,
    ip_cliente: str | None = None,
) -> ProductoResumenDTO:
    """Registra un nuevo producto en la tienda del negocio (Fig. 8)."""
    if sesion.tienda_id is None:
        raise ErrorNegocio("El usuario no administra ninguna tienda.")

    nombre_limpio = dto.nombre.strip()
    _validar_precios(dto.precio_contado, dto.precio_lista)

    # Validar duplicados de nombre en la misma tienda
    existe = db.scalar(
        select(Producto).where(
            Producto.tienda_id == sesion.tienda_id,
            Producto.nombre.ilike(nombre_limpio),
        )
    )
    if existe:
        raise ErrorNegocio(
            "Ya existe un producto con esa descripción en su tienda.",
            errores={"nombre": "Nombre de producto ya registrado."},
        )

    nuevo = Producto(
        tienda_id=sesion.tienda_id,
        nombre=nombre_limpio,
        descripcion=dto.descripcion.strip() if dto.descripcion else None,
        marca=dto.marca.strip() if dto.marca else None,
        categoria=dto.categoria.strip() if dto.categoria else None,
        proveedor=dto.proveedor.strip() if dto.proveedor else None,
        unidad_medida=dto.unidad_medida.strip(),
        moneda=dto.moneda,
        precio_contado=dto.precio_contado,
        precio_lista=dto.precio_lista,
        forma_venta_credito=dto.forma_venta_credito,
        imagen_url=dto.imagen_url.strip() if dto.imagen_url else None,
        estado=ACTIVO,
    )
    db.add(nuevo)
    db.flush()

    registrar_auditoria(
        db,
        usuario_id=sesion.usuario_id,
        accion="ALTA_PRODUCTO",
        tabla="productos",
        registro_id=nuevo.producto_id,
        ip=ip_cliente,
        datos_nuevos={
            "nombre": nuevo.nombre,
            "moneda": nuevo.moneda.value,
            "precio_contado": str(nuevo.precio_contado),
            "precio_lista": str(nuevo.precio_lista),
            "forma_venta": nuevo.forma_venta_credito.value,
        },
    )
    db.commit()
    return ProductoResumenDTO.model_validate(nuevo)


def actualizar_producto(
    db: Session,
    sesion: Sesion,
    producto_id: int,
    dto: ActualizarProductoDTO,
    ip_cliente: str | None = None,
) -> ProductoResumenDTO:
    """Edita los datos de un producto de la tienda."""
    if sesion.tienda_id is None:
        raise ErrorNegocio("El usuario no administra ninguna tienda.")

    p = db.scalar(
        select(Producto).where(
            Producto.producto_id == producto_id,
            Producto.tienda_id == sesion.tienda_id,
        )
    )
    if not p:
        raise NoEncontrado(f"Producto {producto_id} no encontrado en su tienda.")

    nombre_limpio = dto.nombre.strip()
    _validar_precios(dto.precio_contado, dto.precio_lista)

    # Validar nombre duplicado en otro producto de la misma tienda
    otro = db.scalar(
        select(Producto).where(
            Producto.tienda_id == sesion.tienda_id,
            Producto.nombre.ilike(nombre_limpio),
            Producto.producto_id != producto_id,
        )
    )
    if otro:
        raise ErrorNegocio(
            "Ya existe otro producto con esa descripción en su tienda.",
            errores={"nombre": "Nombre de producto ya registrado."},
        )

    valores_anteriores = {
        "nombre": p.nombre,
        "precio_contado": str(p.precio_contado),
        "precio_lista": str(p.precio_lista),
        "forma_venta": p.forma_venta_credito.value,
    }

    p.nombre = nombre_limpio
    p.descripcion = dto.descripcion.strip() if dto.descripcion else None
    p.marca = dto.marca.strip() if dto.marca else None
    p.categoria = dto.categoria.strip() if dto.categoria else None
    p.proveedor = dto.proveedor.strip() if dto.proveedor else None
    p.unidad_medida = dto.unidad_medida.strip()
    p.moneda = dto.moneda
    p.precio_contado = dto.precio_contado
    p.precio_lista = dto.precio_lista
    p.forma_venta_credito = dto.forma_venta_credito
    p.imagen_url = dto.imagen_url.strip() if dto.imagen_url else None

    db.flush()
    registrar_auditoria(
        db,
        usuario_id=sesion.usuario_id,
        accion="EDICION_PRODUCTO",
        tabla="productos",
        registro_id=p.producto_id,
        ip=ip_cliente,
        datos_anteriores=valores_anteriores,
        datos_nuevos={
            "nombre": p.nombre,
            "precio_contado": str(p.precio_contado),
            "precio_lista": str(p.precio_lista),
            "forma_venta": p.forma_venta_credito.value,
        },
    )
    db.commit()
    return ProductoResumenDTO.model_validate(p)


def dar_de_baja_producto(
    db: Session,
    sesion: Sesion,
    producto_id: int,
    ip_cliente: str | None = None,
) -> ProductoResumenDTO:
    """Baja lógica de un producto de la tienda (`estado = 0`)."""
    if sesion.tienda_id is None:
        raise ErrorNegocio("El usuario no administra ninguna tienda.")

    p = db.scalar(
        select(Producto).where(
            Producto.producto_id == producto_id,
            Producto.tienda_id == sesion.tienda_id,
        )
    )
    if not p:
        raise NoEncontrado(f"Producto {producto_id} no encontrado en su tienda.")

    if p.estado == BAJA:
        return ProductoResumenDTO.model_validate(p)

    p.estado = BAJA
    db.flush()
    registrar_auditoria(
        db,
        usuario_id=sesion.usuario_id,
        accion="BAJA_PRODUCTO",
        tabla="productos",
        registro_id=p.producto_id,
        ip=ip_cliente,
        datos_nuevos={"estado": BAJA},
    )
    db.commit()
    return ProductoResumenDTO.model_validate(p)


def reactivar_producto(
    db: Session,
    sesion: Sesion,
    producto_id: int,
    ip_cliente: str | None = None,
) -> ProductoResumenDTO:
    """Reactiva un producto inactivo (`estado = 1`)."""
    if sesion.tienda_id is None:
        raise ErrorNegocio("El usuario no administra ninguna tienda.")

    p = db.scalar(
        select(Producto).where(
            Producto.producto_id == producto_id,
            Producto.tienda_id == sesion.tienda_id,
        )
    )
    if not p:
        raise NoEncontrado(f"Producto {producto_id} no encontrado en su tienda.")

    p.estado = ACTIVO
    db.flush()
    registrar_auditoria(
        db,
        usuario_id=sesion.usuario_id,
        accion="REACTIVACION_PRODUCTO",
        tabla="productos",
        registro_id=p.producto_id,
        ip=ip_cliente,
        datos_nuevos={"estado": ACTIVO},
    )
    db.commit()
    return ProductoResumenDTO.model_validate(p)
