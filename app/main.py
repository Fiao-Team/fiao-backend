"""Punto de arranque de la API.

Para levantarla:  .venv\\Scripts\\python.exe -m uvicorn app.main:app --reload
Documentación automática:  http://localhost:8000/docs

Estructura por capas (como el backend de Spring de Arqui Web):
    controladores/  rutas HTTP           ->  llaman a servicios/
    servicios/      lógica del negocio   ->  usan entidades/ y calculo/
    dto/            datos que entran y salen de cada ruta
    entidades/      tablas de la base de datos
    excepciones/    errores de negocio
    config/         configuración, base de datos, seguridad, sesión y auditoría
    calculo/        módulo financiero puro (pseudocódigo 4.1)
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import app.entidades.todas  # noqa: F401  (carga las 13 tablas antes de la primera consulta)
from app.config.configuracion import get_settings
from app.controladores.acceso import router as acceso_router
from app.controladores.productos import router as productos_router
from app.controladores.tiendas import router as tiendas_router
from app.controladores.ventas import router as ventas_router
from app.excepciones.errores import ErrorNegocio

app = FastAPI(title="Fiao API", version="0.1.0")
app.include_router(acceso_router)
app.include_router(tiendas_router)
app.include_router(productos_router)
app.include_router(ventas_router)

# Permite que el frontend (Angular) llame a esta API desde el navegador.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().lista_cors,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ErrorNegocio)
def manejar_error_negocio(_: Request, error: ErrorNegocio) -> JSONResponse:
    """Convierte un ErrorNegocio en respuesta HTTP (como @ControllerAdvice en Spring).
    Usa la misma forma {"detail": ...} que los errores propios de FastAPI,
    e incluye el objeto "errores" si existe para validación visual de formularios."""
    contenido: dict[str, object] = {"detail": error.mensaje}
    if error.errores:
        contenido["errores"] = error.errores
    return JSONResponse(status_code=error.estado, content=contenido)


@app.get("/salud", tags=["sistema"])
def salud() -> dict[str, str]:
    """Ruta de prueba: si responde, el servidor está funcionando."""
    return {"estado": "ok"}
