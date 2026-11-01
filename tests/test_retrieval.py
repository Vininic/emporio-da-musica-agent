from datetime import datetime
from pathlib import Path

import numpy as np

from emporio.config import TIMEZONE, Clock
from emporio.domain.money import brl
from emporio.journal import Journal
from emporio.policies import load_sections
from emporio.retrieval import BM25, Document, Embedder, HybridIndex, tokenize
from emporio.runtime import Runtime
from emporio.tools import (
    CartItem,
    GetProductArgs,
    QuotePurchaseArgs,
    SearchPoliciesArgs,
    SearchProductsArgs,
    Session,
    get_product,
    quote_purchase,
    search_policies,
    search_products,
    store_info,
)

ROOT = Path(__file__).resolve().parent.parent


def keyword_context(now=datetime(2026, 3, 25, 10, 30, tzinfo=TIMEZONE)):
    runtime = Runtime(clock=Clock(now), journal=Journal())
    return runtime.context(Session("test"), None)


def test_manual_is_split_into_numbered_sections():
    sections = {s.id: s for s in load_sections(ROOT / "data" / "policies.md")}
    assert len(sections) == 25
    assert "7 (sete) dias corridos" in sections["4.1"].text
    assert "BR4K7M2X9P1BR" in sections["5.3"].text
    assert all(section.text for section in sections.values())


def test_tokenize_folds_accents_and_plurals():
    assert tokenize("Violões de nylon") == ["violao", "nylon"]


def test_bm25_prefers_the_matching_document():
    scores = BM25(["devolução em sete dias", "frete grátis"]).scores("devolucao")
    assert scores[0] > 0 == scores[1]


def test_keyword_search_finds_policy_sections():
    ctx = keyword_context()
    cases = {
        "arrependimento devolução": "4.1",
        "parcelamento parcela mínima": "3.1",
        "código de rastreamento": "5.3",
        "garantia legal": "8.1",
    }
    for query, expected in cases.items():
        result = search_policies(ctx, SearchPoliciesArgs(query=query))
        assert expected in [t["section"] for t in result.data["excerpts"]], query


def fake_embedder(tmp_path, vectors):
    def documents(texts):
        return np.array([vectors["doc"][i] for i in range(len(texts))], dtype=np.float32)

    def query(texts):
        return np.array([vectors["query"]], dtype=np.float32)

    return Embedder(documents, query, "fake", tmp_path)


def test_vectors_find_what_keywords_cannot(tmp_path):
    docs = [Document("a", "Cedro", "madeira"), Document("b", "Mogno", "madeira")]
    index = HybridIndex(docs, fake_embedder(tmp_path, {"doc": [[1, 0], [0, 1]], "query": [0, 1]}))
    assert index.uses_vectors
    assert index.search("som quente", top_k=1)[0].id == "b"


def test_matrix_is_cached_on_disk(tmp_path):
    docs = [Document("a", "x", "y")]
    embedder = fake_embedder(tmp_path, {"doc": [[1, 0]], "query": [1, 0]})
    HybridIndex(docs, embedder)
    embedder.embed_documents = None
    assert HybridIndex(docs, embedder).uses_vectors


def test_broken_embedder_degrades_to_keywords(tmp_path):
    def boom(texts):
        raise RuntimeError("no key")

    docs = [Document("a", "violão", "nylon")]
    index = HybridIndex(docs, Embedder(boom, boom, "broken", tmp_path))
    assert not index.uses_vectors
    assert index.search("violão")[0].id == "a"


def test_query_embedding_failure_degrades_to_keywords(tmp_path):
    def boom(texts):
        raise RuntimeError("quota")

    embedder = fake_embedder(tmp_path, {"doc": [[1, 0]], "query": [1, 0]})
    embedder.embed_query = boom
    index = HybridIndex([Document("a", "violão", "nylon")], embedder)
    assert index.search("violão")[0].id == "a"


def test_t07_search_respects_the_hard_filters():
    result = search_products(
        keyword_context(), SearchProductsArgs(category="violões", max_price=1000)
    )
    assert result.data["total"] == 12
    assert result.block["type"] == "product_list"
    assert all(item["availability"] == "disponivel" for item in result.block["items"])


def test_ranking_never_escapes_the_filters():
    result = search_products(
        keyword_context(),
        SearchProductsArgs(query="martin taylor profissional", category="violões", max_price=800),
    )
    assert all("Martin" not in p["name"] for p in result.data["products"])


def test_t05_empty_category_says_so():
    result = search_products(keyword_context(), SearchProductsArgs(category="Cordas Orquestrais"))
    assert result.data["total"] == 0
    assert "não diga que não vende" in result.data["note"]


def test_t11_expired_promotion_is_listed_as_expired_and_price_is_current():
    result = get_product(keyword_context(), GetProductArgs(name="Takamine GD20"))
    product = result.data["product"]
    assert product["final_price"] == "R$ 2.199,00"
    assert "promotion" not in product
    assert product["expired_promotions"] == ["Oferta Especial (12%)"]


def test_t12_unavailable_product_comes_with_available_alternatives():
    result = get_product(keyword_context(), GetProductArgs(name="Giannini GF-3D"))
    assert result.data["product"]["status"] == "temporariamente indisponível"
    assert len(result.data["alternatives"]) == 3
    assert all(a["status"] == "disponível" for a in result.data["alternatives"])


def test_t08_discontinued_shows_no_price_to_sell():
    result = get_product(keyword_context(), GetProductArgs(name="Ibanez Bass 2X"))
    assert result.data["product"]["status"] == "fora do catálogo"
    assert "final_price" not in result.data["product"]


def test_ambiguous_name_asks_instead_of_guessing():
    result = get_product(keyword_context(), GetProductArgs(name="Takamine"))
    assert not result.data["found"]
    assert len(result.data["similar"]) > 1


def test_t14_promotional_price_carries_original_and_percent():
    result = get_product(keyword_context(), GetProductArgs(name="Ohana CK-20"))
    product = result.data["product"]
    assert product["list_price"] == brl(54900)
    assert product["final_price"] == brl(43920)
    assert product["promotion"] == "20% off, Desconto Exclusivo"
    assert not product["pix_discount_applied"]


def test_cart_mixes_promotional_and_regular_items():
    result = quote_purchase(
        keyword_context(),
        QuotePurchaseArgs(
            items=[CartItem(product_id=121), CartItem(product_id=95, quantity=2)],
            city="Campo Grande",
        ),
    )
    assert result.data["total_card_debit_boleto"] == brl(43920 + 439800)
    assert result.data["total_pix"] == brl(43920 + 417810)
    assert result.data["shipping"]["cost"] == "grátis"


def test_cart_refuses_unavailable_and_over_stock():
    ctx = keyword_context()
    assert "error" in quote_purchase(ctx, QuotePurchaseArgs(items=[CartItem(product_id=96)])).data
    over = quote_purchase(ctx, QuotePurchaseArgs(items=[CartItem(product_id=93, quantity=3)]))
    assert over.data["available"] == 2


def test_t01_store_phone_is_a_fixed_fact():
    data = store_info(keyword_context(), None).data
    assert data["phone"] == "(67) 3341-4444"
    assert data["open_now"] is True


def test_t25_store_info_when_closed():
    ctx = keyword_context(datetime(2026, 3, 28, 14, 0, tzinfo=TIMEZONE))
    data = store_info(ctx, None).data
    assert data["open_now"] is False
    assert data["opens"] == "segunda, 30/03, às 09:00"


def test_english_manual_has_the_same_sections():
    pt = {s.id for s in load_sections(ROOT / "data" / "policies.md")}
    en = {s.id for s in load_sections(ROOT / "data" / "policies.en.md")}
    assert pt == en


def test_company_details_section_is_not_searchable():
    ctx = keyword_context()
    result = search_policies(ctx, SearchPoliciesArgs(query="CNPJ razão social"))
    assert "1.2" not in [t["section"] for t in result.data["excerpts"]]


def test_english_context_formats_money_and_labels():
    runtime = Runtime(
        clock=Clock(datetime(2026, 3, 25, 10, 30, tzinfo=TIMEZONE)), journal=Journal()
    )
    ctx = runtime.context(Session("test"), None, "en")
    result = get_product(ctx, GetProductArgs(name="Ohana CK-20"))
    product = result.data["product"]
    assert product["final_price"] == "R$ 439.20"
    assert product["category"] == "Ukuleles"
    assert "interest free" in product["installments"]
    assert product["status"] == "available"
    assert result.block["price"]["final"] == 43920


def test_blocks_carry_numbers_not_formatted_text():
    result = get_product(keyword_context(), GetProductArgs(name="Takamine GD20"))
    price = result.block["price"]
    assert price == {
        "list": 219900,
        "final": 219900,
        "pix": 208905,
        "pix_applies": True,
        "count": 12,
        "each": 18325,
        "promo_percent": None,
        "promo_name": None,
    }
    assert result.block["specs"]
