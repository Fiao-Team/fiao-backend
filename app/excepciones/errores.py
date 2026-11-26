"""Errores de negocio (como `excepciones/` en Spring).

Los servicios lanzan `ErrorNegocio` cuando una regla no se cumple
(ej. "La contraseña actual no es correcta"). No saben nada de HTTP:
el manejador de main.py lo convierte en respuesta, como un
@ControllerAdvice de Spring.
"""


class ErrorNegocio(Exception):
    """Una regla del negocio no se cumplió.

    Soporta ambas firmas:
    - ErrorNegocio(400, "Mensaje")
    - ErrorNegocio("Mensaje", estado=400, errores={...})
    """

    def __init__(self, *args, **kwargs):
        if len(args) == 2 and isinstance(args[0], int) and isinstance(args[1], str):
            estado = args[0]
            mensaje = args[1]
        elif len(args) >= 1 and isinstance(args[0], str):
            mensaje = args[0]
            estado = kwargs.get("estado", 400)
        else:
            estado = kwargs.get("estado", 400)
            mensaje = kwargs.get("mensaje", "Error de regla de negocio")

        super().__init__(mensaje)
        self.estado = estado
        self.mensaje = mensaje
        self.errores = kwargs.get("errores", {})


class NoEncontrado(ErrorNegocio):
    def __init__(self, mensaje: str = "Recurso no encontrado"):
        super().__init__(mensaje, estado=404)


class NoAutorizado(ErrorNegocio):
    def __init__(self, mensaje: str = "No autorizado"):
        super().__init__(mensaje, estado=401)


class AccesoDenegado(ErrorNegocio):
    def __init__(self, mensaje: str = "Acceso denegado"):
        super().__init__(mensaje, estado=403)
