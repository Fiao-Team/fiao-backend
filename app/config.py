"""Configuración de la app.

Los valores se leen de variables de entorno (o del archivo .env, que NO se
sube a GitHub). Así las contraseñas nunca quedan escritas en el código.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Ejemplo: postgresql+psycopg://usuario:clave@localhost:5432/fiao
    database_url: str

    # Clave para firmar los tokens de inicio de sesión (JWT). Debe ser larga y secreta.
    jwt_secret: str
    jwt_minutos_expiracion: int = 480  # 8 horas

    # Zona horaria del negocio: la hora de corte se compara en hora de Lima.
    zona_horaria: str = "America/Lima"

    # Direcciones desde las que el frontend puede llamar a la API, separadas por comas.
    cors_origenes: str = "http://localhost:4200"

    # Contraseña del usuario "admin" que crea la migración 0002 (solo se usa una vez).
    admin_password_inicial: str | None = None

    @property
    def lista_cors(self) -> list[str]:
        return [o.strip() for o in self.cors_origenes.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuración (se lee una sola vez)."""
    return Settings()
