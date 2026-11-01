import re
from collections.abc import Iterable

from emporio.domain.money import to_cents

MONEY = re.compile(r"R\$\s?(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?")
PERCENT = re.compile(r"(\d{1,3}(?:,\d+)?)\s?%")
PHONE = re.compile(r"\(?\b\d{2}\)?[\s-]?\d{4,5}-\d{4}\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
SECTION = re.compile(r"§\s?(\d+(?:\.\d+)?)")
TICKET_CLAIM = re.compile(
    r"\b(abri|abrindo|vou abrir|vamos abrir|deixe-me abrir|deixa eu abrir|registrei|vou registrar)\b"
    r"[^.?!]{0,40}\b(chamado|solicitação|reclamação|cancelamento|ocorrência)\b",
    re.IGNORECASE,
)


def _money_values(text: str) -> set[int]:
    return {
        to_cents(f"{whole.replace('.', '')}.{cents or '0'}") for whole, cents in MONEY.findall(text)
    }


def _percents(text: str) -> set[str]:
    return {value.replace(",", ".") for value in PERCENT.findall(text)}


def _phones(text: str) -> set[str]:
    return {re.sub(r"\D", "", value) for value in PHONE.findall(text)}


def unsupported_claims(answer: str, sources: Iterable[str], section_ids: set[str]) -> list[str]:
    source = "\n".join(sources)
    problems = []

    known_money = _money_values(source)
    problems += [
        f"valor R$ {cents / 100:.2f}" for cents in _money_values(answer) if cents not in known_money
    ]
    problems += [f"percentual {p}%" for p in _percents(answer) - _percents(source)]
    problems += [f"telefone {p}" for p in _phones(answer) - _phones(source)]
    problems += [f"e-mail {e}" for e in set(EMAIL.findall(answer)) - set(EMAIL.findall(source))]
    problems += [f"seção §{s}" for s in set(SECTION.findall(answer)) - section_ids]
    return sorted(problems)


def unbacked_actions(answer: str, tools_called: Iterable[str]) -> list[str]:
    if TICKET_CLAIM.search(answer) and "open_ticket" not in tools_called:
        return ["disse que abriu ou abriria um chamado sem chamar open_ticket"]
    return []
