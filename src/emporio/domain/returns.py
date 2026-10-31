from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

REGRET_DAYS = 7
PREFERENCE_DAYS = 7
DEFECT_EXCHANGE_DAYS = 30
LEGAL_WARRANTY_DAYS = 90


class Reason(StrEnum):
    REGRET = "arrependimento"
    DEFECT = "defeito"
    PREFERENCE = "preferencia"


class Channel(StrEnum):
    ONLINE = "online"
    STORE = "loja"
    UNKNOWN = "desconhecido"


class Outcome(StrEnum):
    ELIGIBLE = "elegivel"
    NOT_ELIGIBLE = "nao_elegivel"
    NEEDS_INFO = "precisa_de_informacao"
    HANDOFF = "encaminhar_equipe"
    WARRANTY = "garantia"
    MANUFACTURER = "fabricante"


@dataclass(frozen=True)
class ReturnAssessment:
    outcome: Outcome
    reason_code: str
    policy_sections: tuple[str, ...]
    deadline: date | None = None
    received_date_is_estimate: bool = False
    days_since_reference: int | None = None


def assess(
    reason: Reason,
    status: str,
    today: date,
    order_date: date,
    estimated_delivery: date | None,
    channel: Channel = Channel.UNKNOWN,
    received_on: date | None = None,
) -> ReturnAssessment:
    if status == "cancelled":
        return ReturnAssessment(Outcome.NOT_ELIGIBLE, "order_cancelled", ("4",))
    if status in ("pending", "confirmed"):
        return ReturnAssessment(Outcome.HANDOFF, "not_shipped_no_cancellation_rule", ("4",))
    if status == "shipped" and received_on is None:
        return ReturnAssessment(Outcome.NEEDS_INFO, "not_delivered_yet", ("4.1",))

    received = received_on or estimated_delivery
    is_estimate = received_on is None

    if reason is Reason.DEFECT:
        return _assess_defect(today, order_date, received, is_estimate)
    if received is None:
        return ReturnAssessment(Outcome.NEEDS_INFO, "received_date_unknown", ("4.1",))
    if reason is Reason.REGRET:
        return _assess_regret(today, received, is_estimate, channel)
    return _assess_window(today, received, is_estimate, PREFERENCE_DAYS, "4.3", "preference")


def _assess_regret(
    today: date, received: date, is_estimate: bool, channel: Channel
) -> ReturnAssessment:
    if channel is Channel.UNKNOWN:
        return ReturnAssessment(Outcome.NEEDS_INFO, "channel_unknown", ("4.1",))
    if channel is Channel.STORE:
        return _assess_window(
            today, received, is_estimate, PREFERENCE_DAYS, "4.3", "store_purchase"
        )
    return _assess_window(today, received, is_estimate, REGRET_DAYS, "4.1", "regret")


def _assess_window(
    today: date, received: date, is_estimate: bool, days: int, section: str, label: str
) -> ReturnAssessment:
    deadline = received + timedelta(days=days)
    within = today <= deadline
    return ReturnAssessment(
        Outcome.ELIGIBLE if within else Outcome.NOT_ELIGIBLE,
        f"{label}_{'within' if within else 'past'}_window",
        (section, "4.4"),
        deadline,
        is_estimate,
        (today - received).days,
    )


def _assess_defect(
    today: date, order_date: date, received: date | None, is_estimate: bool
) -> ReturnAssessment:
    exchange_deadline = order_date + timedelta(days=DEFECT_EXCHANGE_DAYS)
    if today <= exchange_deadline:
        return ReturnAssessment(
            Outcome.ELIGIBLE,
            "defect_exchange_window",
            ("4.2",),
            exchange_deadline,
            days_since_reference=(today - order_date).days,
        )

    if received is not None and today <= received + timedelta(days=LEGAL_WARRANTY_DAYS):
        return ReturnAssessment(
            Outcome.WARRANTY,
            "defect_legal_warranty",
            ("4.2", "8.1", "8.3"),
            received + timedelta(days=LEGAL_WARRANTY_DAYS),
            is_estimate,
            (today - received).days,
        )

    return ReturnAssessment(
        Outcome.MANUFACTURER,
        "defect_manufacturer_warranty",
        ("4.2", "8.2", "8.3"),
        received_date_is_estimate=is_estimate,
    )
