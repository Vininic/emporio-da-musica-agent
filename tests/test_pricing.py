import pytest

from emporio.domain.money import brl, to_cents
from emporio.domain.pricing import Promotion, max_installments, quote


@pytest.mark.parametrize(
    ("cents", "text"),
    [(219900, "R$ 2.199,00"), (79990, "R$ 799,90"), (1874690, "R$ 18.746,90"), (5, "R$ 0,05")],
)
def test_brl(cents, text):
    assert brl(cents) == text


def test_to_cents_is_exact_for_float_like_strings():
    assert to_cents("799.9") == 79990
    assert to_cents("11499") == 1149900


def test_pix_takes_5_percent_off_list_price():
    result = quote(219900)
    assert result.final_cents == 219900
    assert result.pix_cents == 208905
    assert result.pix_discount_applies


def test_t13_pix_is_not_cumulative_with_promotion():
    result = quote(54900, Promotion(20, "Desconto Exclusivo"))
    assert result.list_cents == 54900
    assert result.final_cents == 43920
    assert result.pix_cents == 43920
    assert not result.pix_discount_applies


@pytest.mark.parametrize(
    ("total", "expected"),
    [
        (4000, 1),
        (10000, 2),
        (15000, 3),
        (30000, 3),
        (32000, 4),
        (40000, 5),
        (48000, 6),
        (60000, 6),
        (70000, 7),
        (120000, 12),
        (1149900, 12),
    ],
)
def test_t03_installment_tiers(total, expected):
    assert max_installments(total) == expected


def test_installments_are_computed_on_the_promotional_price():
    result = quote(54900, Promotion(20, "Desconto Exclusivo"))
    assert result.max_installments == 5
    assert result.installment_cents == 8784


def test_combined_payment_only_above_two_thousand():
    assert not quote(200000).combined_payment_allowed
    assert quote(200001).combined_payment_allowed


def test_quantity_multiplies_before_discounts():
    result = quote(35900, Promotion(10, "Oferta Especial"), quantity=2)
    assert result.list_cents == 71800
    assert result.final_cents == 64620
