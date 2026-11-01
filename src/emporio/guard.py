import re
from collections.abc import Iterable

from emporio.domain.money import to_cents

MONEY = re.compile(r"R\$\s?(\d[\d.,]*\d|\d)")
PERCENT = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s?%")
PHONE = re.compile(r"\(?\b\d{2}\)?[\s-]?\d{4,5}-\d{4}\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
SECTION_REFERENCE = re.compile(r"§|\bse[cç][aã]o\s+\d|\bsection\s+\d", re.IGNORECASE)
TICKET_CLAIM = re.compile(
    r"\b(abri|abrindo|vou abrir|vamos abrir|deixe-me abrir|deixa eu abrir|registrei|vou registrar"
    r"|opened|opening|i'll open|i will open|let me open|i've logged|i logged|i'll log)\b"
    r"[^.?!]{0,40}\b(chamado|solicitação|reclamação|cancelamento|ocorrência"
    r"|ticket|case|complaint|request|cancellation)\b",
    re.IGNORECASE,
)
DECIMALS = re.compile(r"[.,](\d{1,2})$")
MONEY_IN_WORDS = re.compile(r"(\d[\d.]*)\s+reais(?:\s+e\s+(\d{1,2})\s+centavos)?", re.IGNORECASE)


def _to_cents(value: str) -> int:
    decimals = DECIMALS.search(value)
    whole = value[: decimals.start()] if decimals else value
    cents = decimals[1].ljust(2, "0") if decimals else "00"
    return to_cents(f"{re.sub(r'[.,]', '', whole)}.{cents}")


def _money_values(text: str) -> set[int]:
    written = {_to_cents(value) for value in MONEY.findall(text)}
    spoken = {
        int(whole.replace(".", "")) * 100 + int(cents or 0)
        for whole, cents in MONEY_IN_WORDS.findall(text)
    }
    return written | spoken


def _percents(text: str) -> set[str]:
    return {value.replace(",", ".") for value in PERCENT.findall(text)}


def _phones(text: str) -> set[str]:
    return {re.sub(r"\D", "", value) for value in PHONE.findall(text)}


def unsupported_claims(answer: str, sources: Iterable[str]) -> list[str]:
    source = "\n".join(sources)
    problems = []

    known_money = _money_values(source)
    problems += [
        f"R$ {cents / 100:.2f}" for cents in _money_values(answer) if cents not in known_money
    ]
    problems += [f"{p}%" for p in _percents(answer) - _percents(source)]
    problems += [f"phone {p}" for p in _phones(answer) - _phones(source)]
    problems += [f"e-mail {e}" for e in set(EMAIL.findall(answer)) - set(EMAIL.findall(source))]
    if SECTION_REFERENCE.search(answer):
        problems.append("section number written in the answer; use [[fonte:x]]")
    return sorted(problems)


def unbacked_actions(answer: str, tools_called: Iterable[str], message: str) -> list[str]:
    if TICKET_CLAIM.search(answer) and "open_ticket" not in tools_called:
        return [message]
    return []
