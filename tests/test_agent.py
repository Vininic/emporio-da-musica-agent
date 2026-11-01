import json
from datetime import datetime

import pytest
from openai.types.chat.chat_completion_chunk import (
    ChoiceDeltaToolCall,
    ChoiceDeltaToolCallFunction,
)

from emporio.agent import FALLBACK, Agent, MarkerFilter
from emporio.config import TIMEZONE, Clock
from emporio.guard import unsupported_claims
from emporio.llm import LLMError, TextDelta, ToolCall, ToolCallCollector, ToolCalls
from emporio.runtime import Runtime
from emporio.tools import Session, tool_schemas

OPEN = datetime(2026, 3, 25, 10, 30, tzinfo=TIMEZONE)
CLOSED = datetime(2026, 3, 25, 20, 0, tzinfo=TIMEZONE)


class ScriptedLLM:
    def __init__(self, *rounds):
        self._rounds = list(rounds)
        self.seen = []

    def stream(self, messages, tools):
        self.seen.append(list(messages))
        round_ = self._rounds.pop(0)
        if isinstance(round_, Exception):
            raise round_
        yield from round_


def text(content):
    return [TextDelta(content)]


def call(tool, /, **arguments):
    return [ToolCalls((ToolCall(f"c{tool}", tool, json.dumps(arguments)),))]


def run(llm, *questions, now=OPEN):
    runtime = Runtime(clock=Clock(now))
    session = Session("test")
    agent = Agent(llm, runtime.context(session, None))
    messages = []
    events = []
    for question in questions:
        events += list(agent.run(messages, question))
    return events, messages, session, runtime


def of_type(events, kind):
    return [event for event in events if event["type"] == kind]


def spoken(events):
    return "".join(event["text"] for event in of_type(events, "text"))


def test_tools_have_clean_schemas():
    schemas = tool_schemas()
    assert len(schemas) == 11
    for schema in schemas:
        dumped = json.dumps(schema)
        assert "anyOf" not in dumped
        assert "$ref" not in dumped
        assert "title" not in schema["function"]["parameters"]


def test_price_comes_from_the_tool_and_passes_the_guard():
    llm = ScriptedLLM(call("get_product", name="Takamine GD20"), text("Sai por R$ 2.199,00."))
    events, messages, _, _ = run(llm, "Quanto custa o Takamine GD20?")

    assert spoken(events) == "Sai por R$ 2.199,00."
    assert not of_type(events, "guard")
    tool_message = next(m for m in messages if m["role"] == "tool")
    assert "R$ 2.199,00" in tool_message["content"]


def test_invented_price_triggers_a_correction():
    llm = ScriptedLLM(
        call("get_product", name="Takamine GD20"),
        text("Sai por R$ 1.500,00."),
        text("Sai por R$ 2.199,00."),
    )
    events, messages, _, _ = run(llm, "Quanto custa o Takamine GD20?")

    assert "R$ 1500.00" in of_type(events, "guard")[0]["problems"]
    assert of_type(events, "replace")[0]["text"] == "Sai por R$ 2.199,00."
    assert messages[-1]["content"] == "Sai por R$ 2.199,00."
    assert not any("1.500" in str(m.get("content")) for m in messages)


def test_price_without_any_tool_is_rejected_then_replaced_by_the_fallback():
    llm = ScriptedLLM(text("Custa R$ 999,00."), text("Custa R$ 888,00."))
    events, messages, _, _ = run(llm, "Quanto custa?")

    assert of_type(events, "replace")[0]["text"] == FALLBACK
    assert messages[-1]["content"] == FALLBACK


def test_customer_stated_value_can_be_repeated():
    llm = ScriptedLLM(
        call("get_product", name="Takamine GD20"), text("R$ 1.000,00 não, é R$ 2.199,00.")
    )
    events, _, _, _ = run(llm, "Vi por R$ 1.000,00, confere?")
    assert not of_type(events, "guard")


def test_t19_lookup_gate_is_in_the_code():
    llm = ScriptedLLM(
        call("lookup_order", order_number=1, phone="(67) 00000-0000"),
        text("Não conferem."),
    )
    events, messages, session, _ = run(llm, "pedido 1")

    tool_message = next(m for m in messages if m["role"] == "tool")
    assert "Pedro" not in tool_message["content"]
    assert "R$" not in tool_message["content"]
    assert session.verified_orders == []
    assert session.failed_verifications == 1


def test_t19_check_return_refuses_an_unverified_order():
    llm = ScriptedLLM(
        call("check_return", order_number=1, reason="regret", channel="online"),
        text("Preciso verificar."),
    )
    _, messages, _, _ = run(llm, "devolver pedido 1")
    assert '"verified": false' in next(m for m in messages if m["role"] == "tool")["content"]


def test_t19_lookups_lock_after_three_failures():
    bad = call("lookup_order", order_number=1, phone="1")
    llm = ScriptedLLM(bad, bad, bad, bad, text("Fala com a equipe."))
    _, messages, _, _ = run(llm, "pedido")
    last_tool = [m for m in messages if m["role"] == "tool"][-1]
    assert '"locked": true' in last_tool["content"]


def test_verified_lookup_then_return_assessment():
    llm = ScriptedLLM(
        call("lookup_order", order_number=1, phone="(67) 98432-1098"),
        call("check_return", order_number=1, reason="regret", channel="online"),
        text("Passou do prazo."),
    )
    events, messages, session, _ = run(llm, "pedido 1")

    assert session.verified_orders == [1]
    last_tool = [m for m in messages if m["role"] == "tool"][-1]
    assert "nao_elegivel" in last_tool["content"]
    assert {b["block"]["type"] for b in of_type(events, "block")} == {"order", "return"}


def test_phone_never_reaches_the_trace():
    llm = ScriptedLLM(call("lookup_order", order_number=1, phone="(67) 98432-1098"), text("Achei."))
    events, _, _, _ = run(llm, "pedido 1")
    assert "98432" not in json.dumps(of_type(events, "tool_start"))


def test_tool_errors_go_back_to_the_model_instead_of_crashing():
    llm = ScriptedLLM(
        call("nope"), call("get_product", wrong="x"), text("Vou tentar de outro jeito.")
    )
    events, messages, _, _ = run(llm, "oi")
    contents = [m["content"] for m in messages if m["role"] == "tool"]
    assert "não existe" in contents[0]
    assert "Argumentos inválidos" in contents[1]
    assert of_type(events, "done")


def test_tool_loop_is_bounded():
    llm = ScriptedLLM(*[call("catalog_overview") for _ in range(10)])
    events, _, _, _ = run(llm, "loop")
    assert of_type(events, "replace")[-1]["text"] == FALLBACK


def test_block_markers_become_placement_events():
    llm = ScriptedLLM(
        call("get_product", name="Takamine GD20"),
        [TextDelta("Olha ele:\n[[blo"), TextDelta("co:b1]]\nHonesto.")],
    )
    events, _, _, _ = run(llm, "Takamine GD20")

    assert "[[" not in spoken(events)
    assert of_type(events, "block_ref") == [{"type": "block_ref", "id": "b1"}]
    assert not [e for e in of_type(events, "block_ref") if e["id"] != "b1"]


def test_unreferenced_block_is_appended_so_the_customer_still_sees_it():
    llm = ScriptedLLM(call("get_product", name="Takamine GD20"), text("Sai por R$ 2.199,00."))
    events, _, _, _ = run(llm, "Takamine GD20")
    assert of_type(events, "block_ref") == [{"type": "block_ref", "id": "b1"}]


def test_t25_closed_store_shows_when_it_reopens_on_the_first_turn_only():
    llm = ScriptedLLM(text("Oi."), text("Oi de novo."))
    events, _, _, _ = run(llm, "oi", "oi", now=CLOSED)
    closed = [b for b in of_type(events, "block") if b["block"]["type"] == "closed"]
    assert len(closed) == 1
    assert closed[0]["block"]["opens"] == "amanhã, 26/03, às 09:00"


def test_provider_failure_is_a_message_not_a_crash_and_does_not_poison_history():
    llm = ScriptedLLM(LLMError("503"), text("Voltei."))
    events, messages, _, _ = run(llm, "oi", "oi de novo")
    assert of_type(events, "provider_error")
    assert messages[-1]["content"] == "Voltei."


def test_ticket_is_persisted():
    llm = ScriptedLLM(
        call("open_ticket", kind="complaint", summary="Chegou amassado", contact="Ana"),
        text("Registrei."),
    )
    _, _, _, runtime = run(llm, "chegou amassado")
    assert runtime.journal.tickets()[0]["summary"] == "Chegou amassado"


@pytest.mark.parametrize(
    "chunks",
    [["abc"], ["a[", "b"], ["[[bl", "oco:b1]]x"], ["x[[gesto:no]]"], ["preço [nota] fim"]],
)
def test_marker_filter_never_loses_text(chunks):
    marker_filter = MarkerFilter()
    pieces = [piece for chunk in chunks for piece in marker_filter.feed(chunk)]
    pieces += list(marker_filter.flush())
    joined = "".join(value for kind, value in pieces if kind == "text")
    assert joined == "".join(chunks).replace("[[bloco:b1]]", "").replace("[[gesto:no]]", "")


def test_guard_ignores_equal_values_written_differently():
    assert unsupported_claims("R$ 2.199", ['"R$ 2.199,00"']) == []
    assert unsupported_claims("R$ 2,199.00", ['"R$ 2.199,00"']) == []


def test_guard_catches_invented_contact_details_and_section_numbers():
    problems = unsupported_claims("Liga (67) 3333-3333, escreve a@b.com, veja §4.1 e 15%", ["nada"])
    assert len(problems) == 4


def test_section_numbers_in_the_text_trigger_a_correction():
    llm = ScriptedLLM(text("Conforme a seção 4.1, são 7 dias."), text("São 7 dias."))
    events, _, _, _ = run(llm, "devolver?")
    assert of_type(events, "guard")
    assert of_type(events, "replace")[0]["text"] == "São 7 dias."


def test_english_turn_uses_english_tool_text_and_fallback():
    runtime = Runtime(clock=Clock(OPEN))
    llm = ScriptedLLM(call("get_product", name="Takamine GD20"), text("It costs R$ 2,199.00."))
    agent = Agent(llm, runtime.context(Session("test"), None, "en"))
    messages = []
    events = list(agent.run(messages, "How much is the Takamine GD20?"))

    assert not of_type(events, "guard")
    tool = next(m for m in messages if m["role"] == "tool")["content"]
    assert "R$ 2,199.00" in tool
    assert "available" in tool
    assert "Dreadnought" in tool


def _delta(call_id, index, name, arguments):
    return ChoiceDeltaToolCall(
        id=call_id,
        index=index if index is not None else 0,
        type="function",
        function=ChoiceDeltaToolCallFunction(name=name, arguments=arguments),
    ).model_copy(update={"index": index})


def test_parallel_calls_without_an_index_stay_separate():
    collector = ToolCallCollector()
    collector.add(_delta("a", None, "get_product", '{"nome":"x"}'))
    collector.add(_delta("b", None, "list_promotions", "{}"))
    assert [(c.id, c.name, c.arguments) for c in collector.calls] == [
        ("a", "get_product", '{"nome":"x"}'),
        ("b", "list_promotions", "{}"),
    ]


def test_arguments_split_across_chunks_are_joined():
    collector = ToolCallCollector()
    collector.add(_delta("a", 0, "get_product", '{"nome"'))
    collector.add(_delta(None, 0, None, ':"x"}'))
    assert [c.arguments for c in collector.calls] == ['{"nome":"x"}']


def test_parallel_tool_calls_all_run_and_keep_their_results():
    llm = ScriptedLLM(
        [
            ToolCalls(
                (
                    ToolCall("a", "get_product", '{"name": "Takamine GD20"}'),
                    ToolCall("b", "list_promotions", "{}"),
                )
            )
        ],
        text("Sai por R$ 2.199,00."),
    )
    _, messages, _, _ = run(llm, "Tem promoção do Takamine GD20?")
    assert [m["tool_call_id"] for m in messages if m["role"] == "tool"] == ["a", "b"]


def test_promising_a_ticket_without_opening_one_triggers_a_correction():
    llm = ScriptedLLM(
        text("Vou abrir um chamado agora mesmo."),
        call("open_ticket", kind="complaint", summary="Chegou quebrado"),
        text("Abri o chamado. Retorno em até 24 horas úteis."),
    )
    events, _, _, runtime = run(llm, "chegou quebrado")

    assert "open_ticket" in of_type(events, "guard")[0]["problems"][0]
    assert of_type(events, "replace")[0]["text"].startswith("Abri o chamado")
    assert runtime.journal.tickets()


def test_offering_a_ticket_is_not_a_promise():
    llm = ScriptedLLM(text("Posso abrir um chamado, quer?"))
    events, _, _, _ = run(llm, "oi")
    assert not of_type(events, "guard")


def test_empty_answer_after_a_tool_is_retried():
    llm = ScriptedLLM(call("store_info"), text(""), text("Abrimos às 09:00."))
    events, messages, _, _ = run(llm, "abrem que horas?")
    assert of_type(events, "replace")[0]["text"] == "Abrimos às 09:00."
    assert messages[-1]["content"] == "Abrimos às 09:00."


def test_policy_chips_show_only_what_the_answer_cites():
    llm = ScriptedLLM(
        call("search_policies", query="arrependimento devolução"),
        text("São 7 dias depois de receber.\n[[fonte:4.1]]"),
    )
    events, _, _, _ = run(llm, "posso devolver?")

    final_blocks = [b for b in of_type(events, "block") if b["block"]["type"] == "policy"]
    assert [s["id"] for s in final_blocks[-1]["block"]["sections"]] == ["4.1"]
    assert of_type(events, "block_ref")[-1]["id"] == final_blocks[-1]["id"]


def test_policy_chips_are_dropped_when_nothing_is_cited():
    llm = ScriptedLLM(call("search_policies", query="frete"), text("Depende da cidade."))
    events, _, _, _ = run(llm, "frete?")
    assert not of_type(events, "block_ref")


def test_ticket_contact_never_reaches_the_trace():
    llm = ScriptedLLM(
        call("open_ticket", kind="other", summary="x", contact="Ana (67) 99654-7821"),
        text("Abri o chamado."),
    )
    events, _, _, _ = run(llm, "oi")
    assert "99654" not in json.dumps(of_type(events, "tool_start"))


def test_marker_with_several_items_never_reaches_the_customer():
    events, *_ = run(
        ScriptedLLM(
            call("search_policies", query="parcelamento"),
            text("Dá em 4x [[fonte:3.1, bloco:b1]]."),
        ),
        "Parcela?",
    )
    assert "[[" not in spoken(events)
    assert all("[[" not in event["text"] for event in of_type(events, "replace"))


def test_order_block_shows_even_when_the_answer_only_places_another_block():
    events, *_ = run(
        ScriptedLLM(
            call("lookup_order", order_number=8, phone="(67) 99654-7821"),
            call("open_ticket", kind="complaint", summary="Atraso no pedido 8"),
            text("Está atrasado. Abri um chamado. [[bloco:b2]]"),
        ),
        "Cadê meu pedido 8? (67) 99654-7821",
    )
    shown = {event["id"] for event in of_type(events, "block_ref")}
    blocks = {event["id"]: event["block"]["type"] for event in of_type(events, "block")}
    assert {blocks[block_id] for block_id in shown} >= {"order", "ticket"}


def test_searching_a_discontinued_model_by_name_reports_it_instead_of_nothing():
    events, messages, *_ = run(
        ScriptedLLM(call("search_products", query="Ibanez Bass 2X"), text("Saiu de linha.")),
        "Tem o Ibanez Bass 2X?",
    )
    tool_message = next(m for m in messages if m["role"] == "tool")
    assert '"found": true' in tool_message["content"].lower()
    assert of_type(events, "block")[0]["block"]["type"] == "product_list"


def test_lookup_without_a_phone_does_not_burn_an_attempt():
    _, _, session, _ = run(
        ScriptedLLM(call("lookup_order", order_number=1, phone=""), text("Qual o telefone?")),
        "Status do pedido 1?",
    )
    assert session.failed_verifications == 0
