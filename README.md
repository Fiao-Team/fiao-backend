# Fiao — Backend

API de **Fiao**, la app que reemplaza el "cuaderno de fiados" de los negocios de barrio
(SI642 Finanzas e Ingeniería Económica, UPC 2026-20, Grupo 4).

**Tecnologías:** Python 3.14 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL · pytest

---

## 1. Requisitos

Instala esto una sola vez en tu computadora:

| Programa | Para qué | Cómo comprobar que está |
|---|---|---|
| **Python 3.14** ([python.org](https://www.python.org/downloads/)) | Correr la API | `py --version` |
| **PostgreSQL** (con pgAdmin) ([postgresql.org](https://www.postgresql.org/download/windows/)) | Base de datos | Abre pgAdmin |
| **Git** | Bajar y subir el código | `git --version` |

> Al instalar PostgreSQL, **anota la contraseña** que pongas al usuario `postgres`: la necesitarás en el paso 4.

Los comandos de esta guía son para **PowerShell** (Windows).

---

## 2. Bajar el código

```powershell
git clone https://github.com/Fiao-Team/fiao-backend.git
cd fiao-backend
git checkout develop
```

---

## 3. Crear el entorno de Python e instalar las librerías

El entorno virtual (`.venv`) guarda las librerías solo para este proyecto.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

> En esta guía siempre se usa `.\.venv\Scripts\python.exe` para que se use el Python del proyecto,
> sin necesidad de "activar" el entorno.

---

## 4. Crear tu archivo `.env`

El `.env` guarda tus contraseñas y configuración. **Nunca se sube a GitHub** (está en `.gitignore`).
Cada integrante tiene el suyo.

```powershell
Copy-Item .env.example .env
```

Abre `.env` con VS Code o el Bloc de notas y cambia:

| Variable | Qué poner |
|---|---|
| `DATABASE_URL` | Reemplaza `TU_CLAVE` por la contraseña de tu usuario `postgres`. Si tu puerto no es 5432, cámbialo también. |
| `JWT_SECRET` | Un texto largo y aleatorio. Genéralo con el comando de abajo y pégalo. |
| `ADMIN_PASSWORD_INICIAL` | La contraseña que tendrá el usuario `admin` en TU base (mínimo 8 caracteres). |
| `ZONA_HORARIA`, `CORS_ORIGENES` | Déjalos como están. |

Para generar el `JWT_SECRET`:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

> Si tu contraseña de PostgreSQL tiene símbolos como `@ : / # %`, hay que escribirlos codificados en
> `DATABASE_URL` (ej. `@` → `%40`). Lo más fácil es usar una contraseña sin esos símbolos.

---

## 5. Crear la base de datos

1. Abre **pgAdmin** y entra a tu servidor.
2. Clic derecho en **Databases → Create → Database…**
3. En *Database* escribe `fiao` y presiona **Save**.

Luego crea las tablas y los datos iniciales con Alembic:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Esto crea las 13 tablas, los parámetros del sistema, las tasas máximas del BCRP y el usuario `admin`
(con la contraseña de `ADMIN_PASSWORD_INICIAL`). Para ver en qué versión está tu base:

```powershell
.\.venv\Scripts\python.exe -m alembic current
```

> Cada vez que bajes cambios (`git pull`), vuelve a correr `alembic upgrade head` por si hay migraciones nuevas.

---

## 6. Levantar la API

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

- Prueba que funciona: http://localhost:8000/salud → `{"estado":"ok"}`
- Documentación interactiva: **http://localhost:8000/docs** (ahí puedes probar `POST /auth/login` con `admin`).
- Para apagarla: `Ctrl + C`.

---

## 6.1. Cargar datos de prueba (opcional, solo desarrollo)

Mientras no existan las pantallas de tiendas, clientes y productos, este script crea
**Bodega Don Pepe**, su dueño y los clientes de los Juegos 1, 2 y 3 con productos de los mockups.
Primero agrega a tu `.env` la línea `DEMO_PASSWORD=...` (mínimo 8 caracteres).

```powershell
.\.venv\Scripts\python.exe -m scripts.datos_demo
```

| Usuario | Rol | Datos |
|---|---|---|
| `donpepe` | Administrador del negocio | Bodega Don Pepe |
| `rosa` | Cliente | Juego 1: soles, 30 % efectiva anual, límite 500 |
| `carlos` | Cliente | Juego 2: soles, 30 % nominal anual cap. mensual, límite 700 |
| `luis` | Cliente | Juego 3: dólares, 2 % efectiva mensual, límite 300 |

Todos usan la contraseña de `DEMO_PASSWORD`. Si lo corres otra vez, no duplica nada.

Para reproducir los juegos del informe, fija la **fecha simulada** del sistema:

```powershell
.\.venv\Scripts\python.exe -m scripts.datos_demo --fecha-simulada 2026-09-15
.\.venv\Scripts\python.exe -m scripts.datos_demo --sin-fecha-simulada
```

---

## 7. Correr las pruebas

| Comando | Qué prueba | ¿Necesita PostgreSQL? |
|---|---|---|
| `.\.venv\Scripts\python.exe -m pytest tests/calculo` | Cálculo financiero (Juegos 1, 2 y 3, casos de borde) | **No** (ni siquiera el `.env`) |
| `.\.venv\Scripts\python.exe -m pytest tests/api` | Rutas, inicio de sesión, RelojSistema | Sí |
| `.\.venv\Scripts\python.exe -m pytest` | Todo | Sí |

- Las pruebas de `tests/api` usan una base aparte llamada **`fiao_test`**, que se crea sola. Tu base `fiao` no se toca.
- El **Juego 3** está marcado como `pendiente_profesor` (depende de que el profesor confirme el conteo de días reales). Para correr todo sin él:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest -m "not pendiente_profesor"
  ```

---

## 8. Cómo está organizado el código

Por capas, igual que un backend de Spring:

```
app/
  main.py          arranque de la API
  controladores/   rutas HTTP: reciben la petición y llaman al servicio
  servicios/       lógica del negocio (y reloj_sistema.py: la única fuente de "hoy")
  dto/             datos que entran y salen de cada ruta
  entidades/       tablas de la base de datos (una clase por tabla)
  excepciones/     ErrorNegocio: errores de las reglas del negocio
  config/          configuración (.env), base de datos, seguridad, sesión y auditoría
  calculo/         cálculo financiero puro (tasas, fin de mes, método francés, mora)
alembic/versions/  migraciones: scripts que crean y cambian la base
scripts/           datos_demo.py: datos de prueba para el navegador (solo desarrollo)
tests/
  calculo/         pruebas del cálculo (sin base de datos)
  api/             pruebas de las rutas (con base fiao_test)
```

Para agregar un módulo (ej. tiendas): `controladores/tiendas.py` + `servicios/tiendas.py` + `dto/tiendas.py`
y sus pruebas en `tests/api/test_tiendas.py`.

---

## 9. Problemas comunes

| Mensaje | Solución |
|---|---|
| `Field required ... database_url` | No tienes `.env` o está en otra carpeta. Hazlo en la raíz de `fiao-backend` (paso 4). |
| `password authentication failed for user "postgres"` | La contraseña en `DATABASE_URL` no es la de tu PostgreSQL. |
| `database "fiao" does not exist` | Crea la base `fiao` en pgAdmin (paso 5). |
| `Falta ADMIN_PASSWORD_INICIAL en el archivo .env` | Agrega esa línea al `.env` (mínimo 8 caracteres) y vuelve a correr `alembic upgrade head`. |
| `Python was not found` | Usa `py` en vez de `python`, o instala Python 3.14. |
| El login dice "Usuario o contraseña incorrectos" con `admin` | La contraseña es la de `ADMIN_PASSWORD_INICIAL` **de cuando corriste la migración**. Cambiarla después en el `.env` no cambia la de la base. |

---

## 10. Cómo trabajamos con Git

- `main`: versión estable (entregas). `develop`: integración (rama por defecto).
- Cada cambio va en su rama, creada desde `develop`:
  ```powershell
  git checkout develop
  git pull
  git checkout -b feature/nombre-del-modulo
  ```
- Al terminar: `git push -u origin feature/nombre-del-modulo` y abre un **Pull Request hacia `develop`** en GitHub.
- Antes de abrir el Pull Request, corre todas las pruebas y verifica que pasen.
