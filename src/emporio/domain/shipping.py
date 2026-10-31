from dataclasses import dataclass

FREE_SHIPPING_ABOVE_CENTS = 50_000
METRO_FEE_CENTS = 3_500
METRO_CITIES = {"campo grande"}
LARGE_INSTRUMENT_CATEGORIES = {3, 4}
CARRIERS = (
    ("PAC (Correios)", "5 a 12 dias úteis"),
    ("SEDEX (Correios)", "2 a 5 dias úteis"),
    ("Jadlog (.package)", "3 a 8 dias úteis"),
)


@dataclass(frozen=True)
class ShippingEstimate:
    region: str
    fee_cents: int | None
    deadlines: tuple[tuple[str, str], ...]
    special_quote: bool


def estimate(city: str, total_cents: int, category_id: int | None = None) -> ShippingEstimate:
    special = category_id in LARGE_INSTRUMENT_CATEGORIES

    if city.strip().casefold() in METRO_CITIES:
        fee = METRO_FEE_CENTS if total_cents < FREE_SHIPPING_ABOVE_CENTS else 0
        return ShippingEstimate(
            region="metropolitana",
            fee_cents=fee,
            deadlines=(("Motoboy próprio", "1 a 3 dias úteis"),),
            special_quote=False,
        )

    return ShippingEstimate(
        region="outras", fee_cents=None, deadlines=CARRIERS, special_quote=special
    )
