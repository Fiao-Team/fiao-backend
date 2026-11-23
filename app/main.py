"""Punto de arranque de la API.

Para levantarla:  .venv\\Scripts\\python.exe -m uvicorn app.main:app --reload
Documentación automática:  http://localhost:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.acceso.router import router as acceso_router
from app.config import get_settings

app = FastAPI(title="Fiao API", version="0.1.0")
app.include_router(acceso_router)

# Permite que el frontend (Angular) llame a esta API desde el navegador.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().lista_cors,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/salud", tags=["sistema"])
def salud() -> dict[str, str]:
    """Ruta de prueba: si responde, el servidor está funcionando."""
    return {"estado": "ok"}
