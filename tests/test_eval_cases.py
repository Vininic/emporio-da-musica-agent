import re
from pathlib import Path

import yaml

from emporio.tools import TOOLS_BY_NAME
from evals.run import check, load_cases

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_KEYS = {
    "id",
    "lang",
    "traps",
    "turns",
    "now",
    "tools",
    "any_tools",
    "forbidden",
    "contains",
    "any",
    "absent",
    "blocks",
    "args",
}


def test_cases_are_well_formed():
    cases = load_cases()
    assert len({c["id"] for c in cases}) == len(cases)
    for case in cases:
        assert set(case) <= ALLOWED_KEYS, case["id"]
        assert case["turns"], case["id"]
        for tool in [*case.get("tools", []), *case.get("forbidden", []), *case.get("args", {})]:
            assert tool in TOOLS_BY_NAME, f"{case['id']}: {tool}"
        for pattern in [*case.get("contains", []), *case.get("any", []), *case.get("absent", [])]:
            re.compile(pattern)


def test_every_trap_has_an_eval_case():
    traps = set(re.findall(r"^\| (T\d+) ", (ROOT / "vault/traps.md").read_text("utf-8"), re.M))
    covered = {trap for case in load_cases() for trap in case.get("traps", [])}
    assert traps
    assert traps == covered


def test_check_reports_each_kind_of_failure():
    case = yaml.safe_load(
        """
        id: x
        turns: [a]
        tools: [get_product]
        forbidden: [lookup_order]
        contains: ["2\\\\.199"]
        any: ["foo", "bar"]
        absent: ["secreto"]
        blocks: [product]
        args: {check_return: {canal: loja}}
        """
    )
    observed = {
        "tools": ["lookup_order"],
        "calls": [("check_return", {"canal": "online"})],
        "answers": ["Isso é secreto"],
        "blocks": [],
    }
    assert len(check(case, observed)) == 7


def test_check_passes_and_ignores_accents():
    case = {"id": "x", "contains": ["e-mail", "preferencia"], "blocks": ["quote"]}
    observed = {
        "tools": [],
        "calls": [],
        "answers": ["Troca por Preferência, por E-mail"],
        "blocks": [{"type": "quote", "total": "R$ 10,00"}],
    }
    assert check(case, observed) == []
