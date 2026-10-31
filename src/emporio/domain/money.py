from decimal import ROUND_HALF_UP, Decimal


def to_cents(value: str | int | float | Decimal) -> int:
    amount = Decimal(str(value)) * 100
    return int(amount.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def percent_of(cents: int, percent: int | Decimal) -> int:
    amount = Decimal(cents) * Decimal(str(percent)) / 100
    return int(amount.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def brl(cents: int) -> str:
    reais, centavos = divmod(abs(cents), 100)
    sign = "-" if cents < 0 else ""
    return f"{sign}R$ {reais:,}".replace(",", ".") + f",{centavos:02d}"
