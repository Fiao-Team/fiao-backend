"""Errores de negocio (como `excepciones/` en Spring).

Los servicios lanzan `ErrorNegocio` cuando una regla no se cumple
(ej. "La contraseña actual no es correcta"). No saben nada de HTTP:
el manejador de main.py lo convierte en respuesta, como un
@ControllerAdvice de Spring.
"""


class ErrorNegocio(Exception):
    """Una regla del negocio no se cumplió.

    estado:  código HTTP que recibirá el frontend (400, 401, 403, 404...).
    mensaje: texto que verá el usuario.
    """

    def __init__(self, estado: int, mensaje: str):
        super().__init__(mensaje)
        self.estado = estado
        self.mensaje = mensaje
