import pytest

from emporio.language import detect_language


@pytest.mark.parametrize(
    "message",
    [
        "Do you have ukuleles?",
        "How much is the Takamine GD20?",
        "Order 7, phone (67) 99789-0123. I bought it on the website.",
        "Where is the store and when do you open?",
    ],
)
def test_english_message_switches_a_portuguese_chat(message):
    assert detect_language(message, "pt") == "en"


@pytest.mark.parametrize(
    "message",
    [
        "Vocês têm ukulele?",
        "Quanto custa o Takamine GD20?",
        "Pedido 7, telefone (67) 99789-0123. Comprei pelo site.",
        "Cadê meu pedido?",
    ],
)
def test_portuguese_message_switches_an_english_chat(message):
    assert detect_language(message, "en") == "pt"


@pytest.mark.parametrize(
    "message", ["oi", "ok", "Takamine GD20", "(67) 99654-7821", "Yamaha C40 please"]
)
def test_short_or_ambiguous_message_keeps_the_chat_language(message):
    assert detect_language(message, "pt") == "pt"
    assert detect_language(message, "en") == "en"


def test_everyday_portuguese_does_not_flip_to_english():
    assert detect_language("tô atrás do preço do Takamine GD20", "pt") == "pt"
