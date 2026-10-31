from dataclasses import dataclass
from decimal import Decimal

from emporio.domain.money import percent_of

PIX_DISCOUNT_PERCENT = 5
COMBINED_PAYMENT_ABOVE_CENTS = 200_000
INSTALLMENT_MINIMUMS = (
    (range(1, 4), 5_000),
    (range(4, 7), 8_000),
    (range(7, 13), 10_000),
)


@dataclass(frozen=True)
class Promotion:
    percent: int
    name: str


@dataclass(frozen=True)
class Quote:
    list_cents: int
    final_cents: int
    pix_cents: int
    promotion: Promotion | None
    max_installments: int
    installment_cents: int
    combined_payment_allowed: bool

    @property
    def pix_discount_applies(self) -> bool:
        return self.promotion is None


def _minimum_for(count: int) -> int:
    for counts, minimum in INSTALLMENT_MINIMUMS:
        if count in counts:
            return minimum
    raise ValueError(f"installments out of range: {count}")


def max_installments(total_cents: int) -> int:
    for count in range(12, 1, -1):
        if total_cents >= _minimum_for(count) * count:
            return count
    return 1


def _installment_value(total_cents: int, count: int) -> int:
    return percent_of(total_cents, Decimal(100) / count)


def quote(list_cents: int, promotion: Promotion | None = None, quantity: int = 1) -> Quote:
    if quantity < 1:
        raise ValueError("quantity must be positive")

    subtotal = list_cents * quantity
    if promotion is None:
        final = subtotal
        pix = subtotal - percent_of(subtotal, PIX_DISCOUNT_PERCENT)
    else:
        final = subtotal - percent_of(subtotal, promotion.percent)
        pix = final

    count = max_installments(final)
    return Quote(
        list_cents=subtotal,
        final_cents=final,
        pix_cents=pix,
        promotion=promotion,
        max_installments=count,
        installment_cents=_installment_value(final, count),
        combined_payment_allowed=final > COMBINED_PAYMENT_ABOVE_CENTS,
    )
