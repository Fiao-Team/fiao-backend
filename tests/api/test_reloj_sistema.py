"""RelojSistema: fecha real en hora de Lima o fecha simulada con la hora real."""

from datetime import UTC, date, datetime

from app.entidades.configuracion import ParametrosSistema
from app.servicios.reloj_sistema import RelojSistema

# 23/11/2026 03:30 en UTC = 22/11/2026 22:30 en Lima (UTC-5)
MADRUGADA_UTC = datetime(2026, 11, 23, 3, 30, tzinfo=UTC)


def reloj(db, momento=MADRUGADA_UTC):
    return RelojSistema(db, hora_real=lambda: momento)


def fijar_fecha_simulada(db, fecha):
    db.add(ParametrosSistema(parametro_id=1, fecha_simulada=fecha))
    db.flush()


def test_sin_fila_de_parametros_usa_la_fecha_real_de_lima(db):
    r = reloj(db)
    assert r.fecha_simulada() is None
    assert r.ahora() == datetime(2026, 11, 22, 22, 30)
    assert r.hoy() == date(2026, 11, 22)  # en Lima todavía es 22, aunque en UTC ya es 23


def test_fecha_simulada_vacia_usa_la_fecha_real(db):
    fijar_fecha_simulada(db, None)
    assert reloj(db).hoy() == date(2026, 11, 22)


def test_con_fecha_simulada_usa_esa_fecha_con_la_hora_real(db):
    fijar_fecha_simulada(db, date(2026, 9, 20))
    r = reloj(db)
    assert r.fecha_simulada() == date(2026, 9, 20)
    assert r.ahora() == datetime(2026, 9, 20, 22, 30)
    assert r.hoy() == date(2026, 9, 20)


def test_ahora_no_lleva_zona_horaria(db):
    # Los timestamp de la base se guardan sin zona (hora de Lima)
    assert reloj(db).ahora().tzinfo is None


def test_reloj_por_defecto_usa_la_hora_real(db):
    hoy_real = datetime.now(UTC).astimezone().date()
    # Sin inyectar la hora: debe devolver una fecha cercana a la real (Lima puede estar un día atrás)
    assert abs((RelojSistema(db).hoy() - hoy_real).days) <= 1
