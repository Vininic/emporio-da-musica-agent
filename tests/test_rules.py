from datetime import date, datetime

import pytest

from emporio.domain import hours, shipping
from emporio.domain.returns import Channel, Outcome, Reason, assess

TODAY = date(2026, 3, 25)


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (datetime(2026, 3, 25, 9, 0), True),
        (datetime(2026, 3, 25, 17, 59), True),
        (datetime(2026, 3, 25, 18, 0), False),
        (datetime(2026, 3, 28, 12, 59), True),
        (datetime(2026, 3, 28, 13, 0), False),
        (datetime(2026, 3, 29, 10, 0), False),
        (datetime(2026, 4, 3, 10, 0), False),
        (datetime(2026, 4, 21, 10, 0), False),
    ],
)
def test_business_hours(moment, expected):
    assert hours.is_open(moment) is expected


@pytest.mark.parametrize(
    ("moment", "opening"),
    [
        (datetime(2026, 3, 25, 7, 0), datetime(2026, 3, 25, 9, 0)),
        (datetime(2026, 3, 25, 19, 0), datetime(2026, 3, 26, 9, 0)),
        (datetime(2026, 3, 28, 14, 0), datetime(2026, 3, 30, 9, 0)),
        (datetime(2026, 4, 2, 19, 0), datetime(2026, 4, 4, 9, 0)),
    ],
)
def test_t25_next_opening_skips_sundays_and_holidays(moment, opening):
    assert hours.next_opening(moment) == opening


def test_describe_opening():
    now = datetime(2026, 3, 28, 14, 0)
    assert hours.describe_opening(hours.next_opening(now), now) == "segunda, 30/03, às 09:00"
    late = datetime(2026, 3, 25, 19, 0)
    assert hours.describe_opening(hours.next_opening(late), late) == "amanhã, 26/03, às 09:00"


def test_metro_shipping_threshold():
    assert shipping.estimate("Campo Grande", 49999).fee_cents == 3500
    assert shipping.estimate("Campo Grande", 50000).fee_cents == 0
    assert shipping.estimate("campo grande ", 60000).fee_cents == 0


def test_other_cities_have_no_invented_fee():
    result = shipping.estimate("Dourados", 100000)
    assert result.fee_cents is None
    assert len(result.deadlines) == 3
    assert not result.special_quote


def test_large_instruments_outside_the_metro_need_a_special_quote():
    assert shipping.estimate("Corumbá", 1000000, category_id=3).special_quote


def test_t21_regret_requires_knowing_the_sales_channel():
    result = assess(Reason.REGRET, "delivered", TODAY, date(2026, 2, 3), date(2026, 2, 17))
    assert result.outcome is Outcome.NEEDS_INFO
    assert result.reason_code == "channel_unknown"


def test_t21_regret_past_window_uses_estimated_delivery_and_says_so():
    result = assess(
        Reason.REGRET, "delivered", TODAY, date(2026, 2, 3), date(2026, 2, 17), Channel.ONLINE
    )
    assert result.outcome is Outcome.NOT_ELIGIBLE
    assert result.received_date_is_estimate
    assert result.days_since_reference == 36


def test_t21_regret_within_window_with_reported_date():
    result = assess(
        Reason.REGRET,
        "delivered",
        TODAY,
        date(2026, 2, 3),
        date(2026, 2, 17),
        Channel.ONLINE,
        received_on=date(2026, 3, 20),
    )
    assert result.outcome is Outcome.ELIGIBLE
    assert result.deadline == date(2026, 3, 27)
    assert not result.received_date_is_estimate


def test_store_purchase_has_no_regret_right_only_preference_exchange():
    result = assess(
        Reason.REGRET,
        "delivered",
        TODAY,
        date(2026, 3, 22),
        None,
        Channel.STORE,
        received_on=date(2026, 3, 22),
    )
    assert result.outcome is Outcome.ELIGIBLE
    assert "4.3" in result.policy_sections
    assert result.reason_code == "store_purchase_within_window"


def test_t22_unshipped_order_has_no_cancellation_rule_so_it_is_handed_off():
    for status in ("pending", "confirmed"):
        result = assess(Reason.REGRET, status, TODAY, date(2026, 3, 18), None, Channel.ONLINE)
        assert result.outcome is Outcome.HANDOFF


def test_shipped_order_cannot_be_returned_yet():
    result = assess(
        Reason.REGRET, "shipped", TODAY, date(2026, 2, 15), date(2026, 2, 28), Channel.ONLINE
    )
    assert result.outcome is Outcome.NEEDS_INFO
    assert result.reason_code == "not_delivered_yet"


def test_cancelled_order_cannot_be_returned():
    result = assess(Reason.REGRET, "cancelled", TODAY, date(2026, 1, 28), None, Channel.ONLINE)
    assert result.outcome is Outcome.NOT_ELIGIBLE


def test_t24_defect_has_three_stages():
    early = assess(Reason.DEFECT, "delivered", TODAY, date(2026, 3, 1), date(2026, 3, 10))
    assert early.outcome is Outcome.ELIGIBLE
    assert early.deadline == date(2026, 3, 31)

    warranty = assess(Reason.DEFECT, "delivered", TODAY, date(2026, 2, 3), date(2026, 2, 17))
    assert warranty.outcome is Outcome.WARRANTY
    assert warranty.deadline == date(2026, 5, 18)

    manufacturer = assess(Reason.DEFECT, "delivered", TODAY, date(2025, 10, 15), date(2025, 10, 25))
    assert manufacturer.outcome is Outcome.MANUFACTURER


def test_describe_opening_in_english():
    now = datetime(2026, 3, 28, 14, 0)
    assert hours.describe_opening(hours.next_opening(now), now, "en") == "Monday, Mar 30, at 09:00"
