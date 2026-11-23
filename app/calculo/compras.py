"""Compras a fin de mes y en meses (informe 3.3.3 y 3.3.4; pseudocódigo 4.5)."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.calculo.fechas import sumar_meses
from app.calculo.redondeo import dividir, potencia, red_factor, red_monto
from app.calculo.tasas import tep

UNO = Decimal(1)


@dataclass(frozen=True)
class CompraFinDeMes:
    C: Decimal    # monto de la compra (precio de lista)
    d: int        # días entre la compra y la fecha de pago
    tep: Decimal  # tasa efectiva de esos d días
    S: Decimal    # monto al vencimiento
    I: Decimal    # interés compensatorio = S - C


def compra_fin_de_mes(C: Decimal, tea: Decimal, d: int) -> CompraFinDeMes:
    """S = C × (1 + TEPd);  I = S - C."""
    tasa = tep(tea, d)
    S = red_monto(C * (UNO + tasa))
    return CompraFinDeMes(C=C, d=d, tep=tasa, S=S, I=S - C)


@dataclass(frozen=True)
class Cuota:
    k: int                # número de cuota
    vencimiento: date
    saldo_inicial: Decimal
    interes: Decimal      # Ik
    amortizacion: Decimal  # Ak
    cuota: Decimal        # Rk = Ik + Ak
    saldo_final: Decimal


@dataclass(frozen=True)
class Cronograma:
    C: Decimal             # monto de la compra
    dg: int                # días de gracia
    tepg: Decimal          # tasa efectiva de los días de gracia
    C_prima: Decimal       # deuda capitalizada C'
    tem: Decimal           # i, tasa efectiva de 30 días
    frc: Decimal           # factor de recuperación del capital
    R: Decimal             # cuota constante
    cuotas: list[Cuota]

    @property
    def total(self) -> Decimal:
        """Suma de todas las cuotas (monto_total de la transacción)."""
        return sum((c.cuota for c in self.cuotas), Decimal("0.00"))


def frc(i: Decimal, N: int) -> Decimal:
    """FRC = i(1+i)^N / ((1+i)^N - 1), redondeado a 7 decimales."""
    factor = potencia(UNO + i, Decimal(N))
    return red_factor(dividir(i * factor, factor - UNO))


def generar_cronograma(
    C: Decimal, tea: Decimal, dg: int, N: int, fecha_pago: date, dia_pago: int
) -> Cronograma:
    """GenerarCronograma: método francés vencido simple ordinario.

    1. Capitaliza la gracia:  C' = C × (1 + TEP_dg)
    2. i = TEM (meses de 30 días)
    3. R = C' × FRC
    4. Cada cuota: Ik = B × i ; Ak = R - Ik ; la última amortiza todo el saldo.
    La cuota k vence k meses después de la fecha de pago de referencia.
    """
    if N < 1:
        raise ValueError("El número de cuotas debe ser al menos 1")

    tepg = tep(tea, dg)
    C_prima = red_monto(C * (UNO + tepg))
    i = tep(tea, 30)
    factor = frc(i, N)
    R = red_monto(C_prima * factor)

    B = C_prima
    cuotas: list[Cuota] = []
    for k in range(1, N + 1):
        Ik = red_monto(B * i)
        if k < N:
            Ak = R - Ik
            Rk = R
        else:  # última cuota ajustada: deja el saldo en 0.00
            Ak = B
            Rk = Ik + Ak
        cuotas.append(
            Cuota(
                k=k,
                vencimiento=sumar_meses(fecha_pago, k, dia_pago),
                saldo_inicial=B,
                interes=Ik,
                amortizacion=Ak,
                cuota=Rk,
                saldo_final=B - Ak,
            )
        )
        B = B - Ak

    return Cronograma(
        C=C, dg=dg, tepg=tepg, C_prima=C_prima, tem=i, frc=factor, R=R, cuotas=cuotas
    )
