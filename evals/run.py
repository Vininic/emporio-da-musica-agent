import argparse
import json
import logging
import re
import statistics
import subprocess
import time
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import yaml

from emporio.agent import strip_markers
from emporio.config import TIMEZONE, Clock, provider_from_env
from emporio.i18n import Lang, brl, format_date, text
from emporio.journal import Journal
from emporio.llm import OpenAICompatibleLLM
from emporio.runtime import Runtime
from emporio.store import normalize_text
from emporio.tools import Session

ROOT = Path(__file__).resolve().parent
DEFAULT_NOW = datetime(2026, 3, 25, 10, 30, tzinfo=TIMEZONE)
PAUSE_BETWEEN_CASES = 1.0
RATE_LIMIT_PATIENCE = 120.0
MONEY_KEYS = {"list", "final", "pix", "each", "list_price", "fee"}
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load_cases() -> list[dict]:
    return yaml.safe_load((ROOT / "cases.yaml").read_text(encoding="utf-8"))


def _as_shown(value, lang: Lang, key: str = "", kind: str = ""):
    if isinstance(value, dict):
        inner = value.get("type", kind)
        return {k: _as_shown(v, lang, k, inner) for k, v in value.items()}
    if isinstance(value, list):
        return [_as_shown(item, lang, key, kind) for item in value]
    if isinstance(value, str) and ISO_DATE.match(value):
        return format_date(date.fromisoformat(value), lang)
    if isinstance(value, int) and (
        key in MONEY_KEYS or (key == "total" and kind != "product_list")
    ):
        return text(lang)["free"] if key == "fee" and value == 0 else brl(value, lang)
    return value


def _visible_text(answers: list[str], blocks: list[dict], lang: Lang = "pt") -> str:
    shown = json.dumps(_as_shown(blocks, lang), ensure_ascii=False)
    return normalize_text("\n".join(answers) + "\n" + shown)


def check(case: dict, observed: dict) -> list[str]:
    failures = []
    called = observed["tools"]
    visible = _visible_text(observed["answers"], observed["blocks"], case.get("lang", "pt"))

    failures += [f"tool not called: {tool}" for tool in case.get("tools", []) if tool not in called]
    failures += [f"forbidden tool: {tool}" for tool in case.get("forbidden", []) if tool in called]
    if case.get("any_tools") and not set(case["any_tools"]) & set(called):
        failures.append(f"none of the tools: {case['any_tools']}")

    for pattern in case.get("contains", []):
        if not re.search(pattern, visible):
            failures.append(f"missing: {pattern}")
    if case.get("any") and not any(re.search(pattern, visible) for pattern in case["any"]):
        failures.append(f"none of: {case['any']}")
    for pattern in case.get("absent", []):
        if re.search(pattern, visible):
            failures.append(f"present: {pattern}")

    shown = {block["type"] for block in observed["blocks"]}
    failures += [f"block not shown: {b}" for b in case.get("blocks", []) if b not in shown]

    for tool, expected in case.get("args", {}).items():
        calls = [args for name, args in observed["calls"] if name == tool]
        if not any(all(args.get(k) == v for k, v in expected.items()) for args in calls):
            failures.append(f"{tool} args differ from {expected}: {calls}")

    return failures


def run_case(case: dict, runtime_for, provider) -> dict:
    now = case.get("now")
    clock = Clock(datetime.fromisoformat(now).replace(tzinfo=TIMEZONE) if now else DEFAULT_NOW)
    runtime = runtime_for(clock)
    llm = OpenAICompatibleLLM(provider, patience=RATE_LIMIT_PATIENCE)
    agent = runtime.agent(Session(case["id"]), provider, llm, case.get("lang", "pt"))

    observed = {"tools": [], "calls": [], "answers": [], "blocks": []}
    messages: list[dict] = []
    latencies, first_tokens = [], []
    guard_hits, errors = 0, []
    model = None

    for question in case["turns"]:
        started = time.perf_counter()
        waited_before = llm.waited
        first = None
        answer = ""
        emitted: dict[str, dict] = {}
        referenced: list[str] = []
        for event in agent.run(messages, question):
            kind = event["type"]
            if kind == "text":
                first = first or time.perf_counter() - started
                answer += event["text"]
            elif kind == "replace":
                answer = event["text"]
            elif kind == "tool_start":
                observed["tools"].append(event["name"])
                observed["calls"].append((event["name"], event["args"]))
            elif kind == "block":
                emitted[event["id"]] = event["block"]
                if event["id"] == "closed":
                    referenced.append(event["id"])
            elif kind == "block_ref":
                referenced.append(event["id"])
            elif kind == "guard":
                guard_hits += 1
            elif kind == "provider_error":
                errors.append(event["detail"])
            elif kind == "done":
                model = event["model"]
        waited = llm.waited - waited_before
        latencies.append(time.perf_counter() - started - waited)
        first_tokens.append(max((first or latencies[-1]) - waited, 0))
        observed["answers"].append(strip_markers(answer))
        observed["blocks"] += [emitted[i] for i in referenced if i in emitted]

    failures = [f"provider error: {e[:120]}" for e in errors] or check(case, observed)
    return {
        "id": case["id"],
        "passed": not failures,
        "failures": failures,
        "tools": observed["tools"],
        "answers": observed["answers"],
        "guard_hits": guard_hits,
        "provider_failed": bool(errors),
        "latency_s": round(sum(latencies), 2),
        "first_token_s": round(max(first_tokens), 2),
        "model": model,
    }


def _commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT
    )
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="Run on this model only, with no fallback")
    parser.add_argument("--case", action="append", help="Run only these case ids")
    parser.add_argument("--label", default="", help="Note for the history table")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.ERROR)
    provider = provider_from_env()
    if provider is None:
        raise SystemExit("No API key: set GEMINI_API_KEY or OPENROUTER_API_KEY in .env")
    if args.model:
        provider = replace(provider, chat_models=(args.model,), fallback=None)

    shared = Runtime(journal=Journal())

    def runtime_for(clock: Clock) -> Runtime:
        shared.clock = clock
        return shared

    cases = [c for c in load_cases() if not args.case or c["id"] in args.case]
    results = []
    for case in cases:
        result = run_case(case, runtime_for, provider)
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        print(f"{status}  {result['latency_s']:>6.1f}s  {case['id']}", flush=True)
        for failure in result["failures"]:
            print(f"        {failure[:200]}", flush=True)
        time.sleep(PAUSE_BETWEEN_CASES)

    passed = sum(r["passed"] for r in results)
    answered = [r for r in results if not r["provider_failed"]]
    latency = [r["latency_s"] for r in answered] or [0]
    first = [r["first_token_s"] for r in answered] or [0]
    model = args.model or provider.chat_models[0]
    summary = {
        "date": datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M"),
        "commit": _commit(),
        "provider": provider.name,
        "model": model,
        "label": args.label,
        "passed": passed,
        "total": len(results),
        "provider_failures": sum(r["provider_failed"] for r in results),
        "guard_hits": sum(r["guard_hits"] for r in results),
        "latency_median_s": round(statistics.median(latency), 2),
        "first_token_median_s": round(statistics.median(first), 2),
    }
    print(json.dumps(summary, ensure_ascii=False))

    if args.no_save or args.case:
        return

    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    stamp = datetime.now(TIMEZONE).strftime("%Y%m%d-%H%M%S")
    name = re.sub(r"[^a-z0-9.-]+", "-", model.lower())
    path = reports / f"{stamp}-{name}.json"
    path.write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    history = ROOT / "HISTORY.md"
    if not history.exists():
        history.write_text(
            "# Eval history\n\nEvery full run, as measured. Failures stay.\n\n"
            "| Date | Commit | Model | Passed | Provider failures | Guard hits "
            "| Median first token (s) | Median turn (s) | Note |\n"
            "|---|---|---|---|---|---|---|---|---|\n",
            encoding="utf-8",
        )
    with history.open("a", encoding="utf-8") as file:
        file.write(
            f"| {summary['date']} | {summary['commit']} | {model} | {passed}/{len(results)} "
            f"| {summary['provider_failures']} | {summary['guard_hits']} "
            f"| {summary['first_token_median_s']} | {summary['latency_median_s']} "
            f"| {args.label} |\n"
        )


if __name__ == "__main__":
    main()
