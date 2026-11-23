"""Fechas de corte y de pago (pseudocódigo 4.1)."""

from dataclasses import dataclass
from datetime import date, datetime, time

from app.calculo.fechas import fecha_con_dia, sumar_meses


@dataclass(frozen=True)
class Ciclo:
    """Resultado de FechaPagoDelCiclo."""

    corte: datetime          # fecha y hora del corte que le toca a la compra
    fecha_pago: date         # fecha de pago pactada de ese corte
    posterior_al_corte: bool  # True si la compra se hizo después del corte de su mes


def fecha_pago_de_corte(corte: date, dia_corte: int, dia_pago: int) -> date:
    """FechaPagoDeCorte: fecha de pago que corresponde a un corte.
    Si el día de pago es menor o igual que el de corte, el pago cae
    en el mes siguiente al corte."""
    fecha_pago = fecha_con_dia(corte.year, corte.month, dia_pago)
    if dia_pago <= dia_corte:
        fecha_pago = sumar_meses(fecha_pago, 1, dia_pago)
    return fecha_pago


def fecha_pago_del_ciclo(
    fecha_hora: datetime, dia_corte: int, hora_corte: time, dia_pago: int
) -> Ciclo:
    """FechaPagoDelCiclo: corte y fecha de pago que le tocan a una compra.

    La compra pasa al corte siguiente solo si es POSTERIOR a la fecha y hora
    de corte (fechaHora > corte). Una compra justo a la hora de corte entra
    en ese corte.

    La hora se compara al minuto (formato HH:mm de la Tabla 5): una compra a
    las 23:59:40 cuenta como 23:59.
    """
    fecha_hora = fecha_hora.replace(second=0, microsecond=0)

    dia = fecha_con_dia(fecha_hora.year, fecha_hora.month, dia_corte)
    corte = datetime.combine(dia, hora_corte)
    posterior = False
    if fecha_hora > corte:
        dia = sumar_meses(dia, 1, dia_corte)
        corte = datetime.combine(dia, hora_corte)
        posterior = True

    return Ciclo(
        corte=corte,
        fecha_pago=fecha_pago_de_corte(corte.date(), dia_corte, dia_pago),
        posterior_al_corte=posterior,
    )
