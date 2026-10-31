from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from emporio.config import Clock
from emporio.domain import hours, shipping
from emporio.domain.money import brl, to_cents
from emporio.domain.pricing import max_installments
from emporio.domain.returns import Channel, Reason, assess
from emporio.journal import Journal
from emporio.policies import Section
from emporio.retrieval import Document, HybridIndex, tokenize
from emporio.store import Availability, Order, Product, Store, normalize_text

MAX_VERIFICATION_ATTEMPTS = 3
MAX_TICKETS = 3
COMPLAINT_RETURN = "24 horas úteis"
STORE_FACTS = {
    "nome": "Empório da Música",
    "endereco": "Rua 14 de Maio, 3200, Centro, Campo Grande - MS, CEP 79202-333",
    "telefone": "(67) 3341-4444",
    "email": "contato@emporiodamusica.com.br",
    "fundacao": "2008",
    "horarios": "Segunda a sexta, 09:00 às 18:00. Sábado, 09:00 às 13:00. Domingo e feriados, fechado.",
}
ORDER_STATUS = {
    "pending": "aguardando confirmação",
    "confirmed": "confirmado",
    "shipped": "enviado",
    "delivered": "entregue",
    "cancelled": "cancelado",
}
PAYMENT_LABELS = {
    "pix": "PIX",
    "debit": "cartão de débito",
    "boleto": "boleto",
}
SPEC_LABELS = {
    "top": "Tampo",
    "back_sides": "Fundo e laterais",
    "neck": "Braço",
    "strings": "Cordas",
    "scale": "Escala",
    "electronics": "Eletrônica",
    "color": "Cor",
    "body": "Corpo",
    "shells": "Cascos",
    "pieces": "Peças",
    "hardware": "Ferragens",
    "keys": "Teclas",
    "type": "Tipo",
    "polyphony": "Polifonia",
}
SPEC_VALUES = {"no": "não", "yes": "sim"}


@dataclass
class Session:
    conversation_id: str = ""
    verified_orders: list[int] = field(default_factory=list)
    failed_verifications: int = 0
    tickets_opened: int = 0
    next_block: int = 1

    def to_dict(self) -> dict:
        return {
            "conversation_id": self.conversation_id,
            "verified_orders": self.verified_orders,
            "failed_verifications": self.failed_verifications,
            "tickets_opened": self.tickets_opened,
            "next_block": self.next_block,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        return cls(**data)


@dataclass
class ToolResult:
    data: dict
    block: dict | None = None


@dataclass
class ToolContext:
    store: Store
    catalog_index: HybridIndex
    policy_index: HybridIndex
    sections: dict[str, Section]
    clock: Clock
    journal: Journal
    session: Session


def catalog_documents(store: Store) -> list[Document]:
    return [
        Document(
            str(product.id),
            product.name,
            f"{product.category}. {product.description} {_specs_text(product)}",
        )
        for product in store.all_products()
    ]


def _specs_text(product: Product) -> str:
    return " ".join(
        f"{SPEC_LABELS.get(key, key)}: {SPEC_VALUES.get(str(value), value)}."
        for key, value in product.specs.items()
    )


def _availability_text(product: Product) -> str:
    return {
        Availability.AVAILABLE: "disponível",
        Availability.OUT_OF_STOCK: "temporariamente indisponível",
        Availability.DISCONTINUED: "fora do catálogo",
        Availability.COMING_SOON: "em breve, ainda não está à venda",
    }[product.availability]


def _price_view(product: Product) -> dict:
    quote = product.quote()
    view = {
        "preco_tabela": brl(quote.list_cents),
        "preco_final": brl(quote.final_cents),
        "preco_pix": brl(quote.pix_cents),
        "desconto_pix_aplicado": quote.pix_discount_applies,
        "parcelamento": f"até {quote.max_installments}x de {brl(quote.installment_cents)} sem juros",
    }
    if quote.promotion is not None:
        view["promocao"] = f"{quote.promotion.percent}% off, {quote.promotion.name}"
    return view


def _product_summary(product: Product) -> dict:
    summary = {
        "id": product.id,
        "nome": product.name,
        "categoria": product.category,
        "situacao": _availability_text(product),
    }
    if product.availability is Availability.AVAILABLE:
        summary.update(_price_view(product))
    elif product.availability is Availability.OUT_OF_STOCK:
        summary["preco_tabela"] = brl(product.price_cents)
    return summary


def _product_detail(product: Product) -> dict:
    detail = _product_summary(product)
    detail["descricao"] = product.description
    detail["especificacoes"] = {
        SPEC_LABELS.get(key, key): SPEC_VALUES.get(str(value), value)
        for key, value in product.specs.items()
    }
    if product.availability is Availability.AVAILABLE:
        detail["estoque"] = product.stock
    if product.expired_promotions:
        detail["promocoes_encerradas"] = [
            f"{promotion.name} ({promotion.percent}%)" for promotion in product.expired_promotions
        ]
    return detail


def _product_block(product: Product) -> dict:
    block = {
        "type": "product",
        "id": product.id,
        "name": product.name,
        "category": product.category,
        "availability": product.availability.value,
        "availability_label": _availability_text(product),
    }
    if product.availability is Availability.AVAILABLE:
        block["price"] = _price_view(product)
    elif product.availability is Availability.OUT_OF_STOCK:
        block["price"] = {"preco_tabela": brl(product.price_cents)}
    return block


def _alternatives(ctx: ToolContext, product: Product, limit: int = 3) -> list[Product]:
    candidates = ctx.store.filter_products(category_id=product.category_id)
    allowed = {str(candidate.id) for candidate in candidates if candidate.id != product.id}
    by_id = {str(candidate.id): candidate for candidate in candidates}
    hits = ctx.catalog_index.search(
        f"{product.name} {product.description}", top_k=max(limit * 3, 9), allowed=allowed
    )
    ranked = [by_id[hit.id] for hit in hits]
    ranked.sort(key=lambda p: abs(p.price_cents - product.price_cents))
    return ranked[:limit]


class CatalogOverviewArgs(BaseModel):
    pass


def catalog_overview(ctx: ToolContext, args: CatalogOverviewArgs) -> ToolResult:
    categories = [
        {"categoria": c["name"], "descricao": c["description"], "itens_disponiveis": c["available"]}
        for c in ctx.store.categories()
    ]
    return ToolResult(
        {
            "categorias": categories,
            "nota": (
                "Categoria com 0 itens disponíveis: a loja trabalha com a categoria, mas não há item "
                "no sistema agora. Não diga que a loja não vende; ofereça encaminhar à equipe."
            ),
        }
    )


class SearchProductsArgs(BaseModel):
    consulta: str | None = Field(
        None, description="Descrição livre do que o cliente procura, ex.: som quente para iniciante"
    )
    categoria: str | None = Field(None, description="Nome da categoria, ex.: Violões, Guitarras")
    preco_maximo: float | None = Field(None, description="Preço máximo em reais")
    preco_minimo: float | None = Field(None, description="Preço mínimo em reais")
    cordas: Literal["nylon", "aço"] | None = Field(None, description="Tipo de corda")
    eletrico: bool | None = Field(None, description="Tem captação/eletrônica")
    incluir_indisponiveis: bool = Field(False, description="Incluir esgotados e fora de catálogo")
    limite: int = Field(12, ge=1, le=20)


def _category_id(ctx: ToolContext, name: str | None) -> tuple[int | None, dict | None]:
    if not name:
        return None, None
    wanted = set(tokenize(name))
    for category in ctx.store.categories():
        if wanted & set(tokenize(category["name"])):
            return category["id"], category
    return None, None


def search_products(ctx: ToolContext, args: SearchProductsArgs) -> ToolResult:
    category_id, category = _category_id(ctx, args.categoria)
    if category is not None and not category["available"]:
        return ToolResult(
            {
                "total": 0,
                "produtos": [],
                "nota": (
                    f"A categoria {category['name']} não tem itens no sistema agora. A loja trabalha "
                    "com ela: não diga que não vende. Ofereça encaminhar à equipe."
                ),
            }
        )

    products = ctx.store.filter_products(
        category_id=category_id,
        max_price_cents=None if args.preco_maximo is None else to_cents(args.preco_maximo),
        min_price_cents=None if args.preco_minimo is None else to_cents(args.preco_minimo),
        strings=args.cordas,
        electric=args.eletrico,
        only_available=not args.incluir_indisponiveis,
    )

    trace = None
    if args.consulta and products:
        by_id = {str(product.id): product for product in products}
        hits = ctx.catalog_index.search(args.consulta, top_k=len(by_id), allowed=set(by_id))
        ranked = [by_id[hit.id] for hit in hits]
        ranked += [product for product in products if product not in ranked]
        products = ranked
        trace = {
            "modo": "híbrido" if ctx.catalog_index.uses_vectors else "palavras-chave",
            "top": [{"id": hit.id, "score": hit.score} for hit in hits[:5]],
        }

    shown = products[: args.limite]
    data = {
        "total": len(products),
        "exibidos": len(shown),
        "produtos": [_product_summary(product) for product in shown],
    }
    if trace is not None:
        data["_busca"] = trace
    block = None
    if shown:
        block = {
            "type": "product_list",
            "total": len(products),
            "items": [_product_block(product) for product in shown],
        }
    return ToolResult(data, block)


class GetProductArgs(BaseModel):
    nome: str = Field(description="Nome ou modelo do produto, ex.: Takamine GD20")


def _match_products(ctx: ToolContext, name: str) -> tuple[Product | None, list[Product]]:
    products = ctx.store.all_products()
    wanted = normalize_text(name)
    for product in products:
        if normalize_text(product.name) == wanted:
            return product, []

    wanted_tokens = set(tokenize(name))
    scored = []
    for product in products:
        tokens = set(tokenize(product.name))
        overlap = len(wanted_tokens & tokens)
        if overlap:
            scored.append((overlap, product))
    scored.sort(key=lambda pair: -pair[0])

    if scored:
        best = scored[0][0]
        top = [product for overlap, product in scored if overlap == best]
        if best == len(wanted_tokens) and len(top) == 1:
            return top[0], []
        return None, top[:5]

    by_id = {str(product.id): product for product in products}
    return None, [by_id[hit.id] for hit in ctx.catalog_index.search(name, top_k=3)]


def get_product(ctx: ToolContext, args: GetProductArgs) -> ToolResult:
    product, candidates = _match_products(ctx, args.nome)
    if product is None:
        return ToolResult(
            {
                "encontrado": False,
                "nota": "Nenhum produto com exatamente esse nome. Pergunte qual destes o cliente quer.",
                "parecidos": [_product_summary(candidate) for candidate in candidates],
            }
        )

    data = {"encontrado": True, "produto": _product_detail(product)}
    if product.availability is not Availability.AVAILABLE:
        alternatives = _alternatives(ctx, product)
        data["alternativas"] = [_product_summary(alternative) for alternative in alternatives]
        block = {
            "type": "product_list",
            "total": len(alternatives) + 1,
            "items": [_product_block(product), *(_product_block(p) for p in alternatives)],
        }
        return ToolResult(data, block)
    return ToolResult(data, _product_block(product))


class ListPromotionsArgs(BaseModel):
    pass


def list_promotions(ctx: ToolContext, args: ListPromotionsArgs) -> ToolResult:
    products = [
        p for p in ctx.store.active_promotions() if p.availability is Availability.AVAILABLE
    ]
    return ToolResult(
        {
            "promocoes_ativas": [_product_summary(product) for product in products],
            "regra": "Promoções não são cumulativas e o desconto de PIX não se aplica sobre elas.",
        },
        {
            "type": "product_list",
            "total": len(products),
            "items": [_product_block(product) for product in products],
        },
    )


class CartItem(BaseModel):
    produto_id: int
    quantidade: int = Field(1, ge=1, le=50)


class QuotePurchaseArgs(BaseModel):
    itens: list[CartItem] = Field(min_length=1, max_length=10)
    cidade: str | None = Field(None, description="Cidade de entrega, para incluir o frete")


def quote_purchase(ctx: ToolContext, args: QuotePurchaseArgs) -> ToolResult:
    lines, final, pix, list_total = [], 0, 0, 0
    category_id = None
    for item in args.itens:
        product = ctx.store.product(item.produto_id)
        if product is None:
            return ToolResult({"erro": f"Produto {item.produto_id} não existe."})
        if product.availability is not Availability.AVAILABLE:
            return ToolResult(
                {
                    "erro": f"{product.name} está {_availability_text(product)} e não pode ser orçado."
                }
            )
        if item.quantidade > product.stock:
            return ToolResult(
                {"erro": f"Estoque insuficiente de {product.name}.", "disponivel": product.stock}
            )
        quote = product.quote(item.quantidade)
        final += quote.final_cents
        pix += quote.pix_cents
        list_total += quote.list_cents
        category_id = (
            category_id
            if category_id in shipping.LARGE_INSTRUMENT_CATEGORIES
            else product.category_id
        )
        lines.append(
            {
                "produto": product.name,
                "quantidade": item.quantidade,
                "preco_tabela": brl(quote.list_cents),
                "preco_final": brl(quote.final_cents),
                "promocao": f"{quote.promotion.percent}% off, {quote.promotion.name}"
                if quote.promotion
                else None,
            }
        )

    count = max_installments(final)
    data = {
        "itens": lines,
        "total_tabela": brl(list_total),
        "total_cartao_debito_boleto": brl(final),
        "total_pix": brl(pix),
        "parcelamento": f"até {count}x de {brl(round(final / count))} sem juros",
        "pagamento_combinado_permitido": final > 200_000,
    }
    if args.cidade:
        data["frete"] = _shipping_view(args.cidade, final, category_id)
    return ToolResult(data, {"type": "quote", **data})


class EstimateShippingArgs(BaseModel):
    cidade: str
    valor_pedido: float | None = Field(None, description="Valor do pedido em reais, se conhecido")


def _shipping_view(city: str, total_cents: int | None, category_id: int | None) -> dict:
    result = shipping.estimate(city, total_cents or 0, category_id)
    view = {
        "regiao": "região metropolitana de Campo Grande"
        if result.region == "metropolitana"
        else "fora da região metropolitana",
        "opcoes": [{"modalidade": name, "prazo": term} for name, term in result.deadlines],
    }
    if result.region == "metropolitana":
        view["regra"] = "Grátis acima de R$ 500,00. Abaixo disso, R$ 35,00."
        if total_cents is not None:
            view["valor_frete"] = "grátis" if result.fee_cents == 0 else brl(result.fee_cents)
    else:
        view["valor_frete"] = (
            "calculado pelo CEP, peso e dimensões; a equipe informa o valor. "
            "Não invente um valor de frete."
        )
    if result.special_quote:
        view["frete_especial"] = "Instrumento de grande porte pode exigir cotação individual."
    return view


def estimate_shipping(ctx: ToolContext, args: EstimateShippingArgs) -> ToolResult:
    total = None if args.valor_pedido is None else to_cents(args.valor_pedido)
    return ToolResult(_shipping_view(args.cidade, total, None))


class SearchPoliciesArgs(BaseModel):
    consulta: str = Field(description="O que precisa saber das políticas da loja")


def search_policies(ctx: ToolContext, args: SearchPoliciesArgs) -> ToolResult:
    hits = ctx.policy_index.search(args.consulta, top_k=3)
    sections = [ctx.sections[hit.id] for hit in hits]
    return ToolResult(
        {
            "trechos": [
                {"secao": f"§{s.id}", "titulo": s.title, "texto": s.text} for s in sections
            ],
            "_busca": {
                "modo": "híbrido" if ctx.policy_index.uses_vectors else "palavras-chave",
                "top": [{"id": hit.id, "score": hit.score} for hit in hits],
            },
        },
        {
            "type": "policy",
            "sections": [{"id": s.id, "title": s.title} for s in sections],
        },
    )


class StoreInfoArgs(BaseModel):
    pass


def store_info(ctx: ToolContext, args: StoreInfoArgs) -> ToolResult:
    now = ctx.clock.now()
    data = {**STORE_FACTS, "aberta_agora": hours.is_open(now)}
    if not hours.is_open(now):
        data["abre"] = hours.describe_opening(hours.next_opening(now), now)
    return ToolResult(data, {"type": "store", **data})


class LookupOrderArgs(BaseModel):
    numero_pedido: int
    telefone: str = Field(description="Telefone do cadastro, informado pelo cliente")


def _payment_label(method: str) -> str:
    if method.startswith("credit_"):
        return f"cartão de crédito em {method.removeprefix('credit_')}"
    return PAYMENT_LABELS.get(method, method)


def _order_view(order: Order, today: date) -> dict:
    view = {
        "numero": order.id,
        "cliente": order.customer_first_name,
        "data_pedido": _format_date(order.order_date),
        "situacao": ORDER_STATUS.get(order.status, order.status),
        "total": brl(order.total_cents),
        "pagamento": _payment_label(order.payment_method),
        "itens": [f"{item.quantity}x {item.product_name}" for item in order.items],
    }
    if order.tracking_code:
        view["rastreamento"] = order.tracking_code
    if order.estimated_delivery:
        view["previsao_entrega"] = _format_date(order.estimated_delivery)
        if order.status == "shipped":
            delay = (today - date.fromisoformat(order.estimated_delivery)).days
            if delay > 0:
                view["atraso_dias"] = delay
                view["nota"] = "Entrega atrasada. Peça desculpas e ofereça abrir um chamado."
    if order.notes:
        view["observacao"] = order.notes
    return view


def _format_date(value: str) -> str:
    return datetime.fromisoformat(value).strftime("%d/%m/%Y")


def lookup_order(ctx: ToolContext, args: LookupOrderArgs) -> ToolResult:
    session = ctx.session
    if session.failed_verifications >= MAX_VERIFICATION_ATTEMPTS:
        return ToolResult(
            {
                "verificado": False,
                "bloqueado": True,
                "nota": (
                    "Limite de tentativas atingido. Não tente de novo. Oriente o cliente a falar "
                    "com a equipe pelo telefone da loja."
                ),
            }
        )

    order = ctx.store.verified_order(args.numero_pedido, args.telefone)
    if order is None:
        session.failed_verifications += 1
        return ToolResult(
            {
                "verificado": False,
                "nota": (
                    "Número do pedido e telefone não conferem. Não diga qual dos dois está errado "
                    "nem se o pedido existe."
                ),
            }
        )

    if order.id not in session.verified_orders:
        session.verified_orders.append(order.id)
    view = _order_view(order, ctx.clock.today())
    return ToolResult(
        {"verificado": True, "pedido": view}, {"type": "order", **view, "status": order.status}
    )


class CheckReturnArgs(BaseModel):
    numero_pedido: int = Field(description="Pedido já verificado com lookup_order nesta conversa")
    motivo: Literal["arrependimento", "defeito", "preferencia"]
    canal: Literal["online", "loja", "desconhecido"] = "desconhecido"
    data_recebimento: str | None = Field(
        None, description="Data em que o cliente recebeu, AAAA-MM-DD, se ele informou"
    )


OUTCOME_GUIDE = {
    "channel_unknown": "Pergunte se a compra foi online ou na loja física antes de responder.",
    "not_delivered_yet": "O pedido ainda não foi entregue, então o prazo não começou.",
    "received_date_unknown": "Pergunte a data em que o cliente recebeu o produto.",
    "not_shipped_no_cancellation_rule": (
        "O manual não tem regra de cancelamento antes do envio. Não prometa nada: abra um chamado."
    ),
    "order_cancelled": "O pedido já está cancelado, não há o que devolver.",
    "regret_within_window": "Dentro do direito de arrependimento (§4.1).",
    "regret_past_window": "Fora do prazo de 7 dias do direito de arrependimento (§4.1).",
    "store_purchase_within_window": (
        "Compra na loja física não tem direito de arrependimento (§4.1 vale para online), mas cabe "
        "troca por preferência dentro de 7 dias (§4.3)."
    ),
    "store_purchase_past_window": (
        "Compra na loja física não tem direito de arrependimento, e a troca por preferência (§4.3) "
        "já passou de 7 dias."
    ),
    "preference_within_window": "Dentro do prazo de troca por preferência (§4.3).",
    "preference_past_window": "Fora do prazo de troca por preferência (§4.3).",
    "defect_exchange_window": "Dentro dos 30 dias de troca por defeito (§4.2).",
    "defect_legal_warranty": (
        "Passou dos 30 dias de troca, mas está na garantia legal de 90 dias (§8.1). "
        "A loja pode intermediar com o fabricante."
    ),
    "defect_manufacturer_warranty": (
        "Passou da garantia legal. Vale a garantia do fabricante (§8.2), com intermediação da loja."
    ),
}


def check_return(ctx: ToolContext, args: CheckReturnArgs) -> ToolResult:
    if args.numero_pedido not in ctx.session.verified_orders:
        return ToolResult(
            {
                "verificado": False,
                "nota": "Verifique o pedido com lookup_order, com número e telefone, antes disso.",
            }
        )

    order = ctx.store.order_for_verified_session(args.numero_pedido)
    received = date.fromisoformat(args.data_recebimento) if args.data_recebimento else None
    result = assess(
        Reason(args.motivo),
        order.status,
        ctx.clock.today(),
        date.fromisoformat(order.order_date),
        date.fromisoformat(order.estimated_delivery) if order.estimated_delivery else None,
        Channel(args.canal),
        received,
    )
    view = {
        "pedido": order.id,
        "resultado": result.outcome.value,
        "orientacao": OUTCOME_GUIDE[result.reason_code],
        "secoes": [f"§{section}" for section in result.policy_sections],
        "codigo": result.reason_code,
    }
    if result.deadline is not None:
        view["prazo_ate"] = result.deadline.strftime("%d/%m/%Y")
    if result.days_since_reference is not None:
        view["dias_passados"] = result.days_since_reference
    if result.received_date_is_estimate:
        view["data_base"] = (
            "previsão de entrega do pedido, pois o sistema não registra o recebimento"
        )
    return ToolResult(view, {"type": "return", **view})


class OpenTicketArgs(BaseModel):
    tipo: Literal["reclamacao", "cancelamento", "cotacao_frete", "produto", "garantia", "outro"]
    resumo: str = Field(max_length=500)
    contato: str | None = Field(None, description="Nome e telefone, se o cliente informou")


def open_ticket(ctx: ToolContext, args: OpenTicketArgs) -> ToolResult:
    session = ctx.session
    if session.tickets_opened >= MAX_TICKETS:
        return ToolResult(
            {"erro": "Limite de chamados desta conversa atingido. Oriente a ligar para a loja."}
        )
    session.tickets_opened += 1
    ticket_id = ctx.journal.open_ticket(
        session.conversation_id, args.tipo, args.resumo, args.contato, ctx.clock.now()
    )
    data = {"chamado": ticket_id, "tipo": args.tipo, "retorno": f"em até {COMPLAINT_RETURN}"}
    return ToolResult(data, {"type": "ticket", **data, "resumo": args.resumo})


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args: type[BaseModel]
    run: Callable[[ToolContext, BaseModel], ToolResult]


TOOLS = (
    Tool(
        "search_products",
        "Busca instrumentos no catálogo. Use para qualquer pergunta sobre opções, faixa de preço ou "
        "recomendação. Já traz só o que está à venda, com preço final, PIX e parcelamento.",
        SearchProductsArgs,
        search_products,
    ),
    Tool(
        "get_product",
        "Detalhes de um produto pelo nome: preço, disponibilidade, promoção vigente, promoções "
        "encerradas, especificações e alternativas quando indisponível.",
        GetProductArgs,
        get_product,
    ),
    Tool(
        "list_promotions",
        "Promoções ativas agora. Use quando perguntarem sobre ofertas.",
        ListPromotionsArgs,
        list_promotions,
    ),
    Tool(
        "quote_purchase",
        "Calcula o total de uma compra (um ou mais itens) por forma de pagamento, com parcelas e "
        "frete se houver cidade. Toda conta de compra passa por aqui.",
        QuotePurchaseArgs,
        quote_purchase,
    ),
    Tool(
        "estimate_shipping",
        "Prazos e regra de frete para uma cidade.",
        EstimateShippingArgs,
        estimate_shipping,
    ),
    Tool(
        "catalog_overview",
        "Categorias da loja e quantos itens há em cada uma.",
        CatalogOverviewArgs,
        catalog_overview,
    ),
    Tool(
        "search_policies",
        "Busca no manual da loja: trocas, devoluções, garantia, pagamento, frete, promoções, "
        "privacidade. Traz o texto com o número da seção para citar.",
        SearchPoliciesArgs,
        search_policies,
    ),
    Tool(
        "store_info",
        "Endereço, telefone, e-mail, horários e se a loja está aberta agora.",
        StoreInfoArgs,
        store_info,
    ),
    Tool(
        "lookup_order",
        "Consulta um pedido. Exige número do pedido E telefone do cadastro informados pelo cliente. "
        "Nunca chame com dados que o cliente não deu.",
        LookupOrderArgs,
        lookup_order,
    ),
    Tool(
        "check_return",
        "Avalia devolução ou troca de um pedido já verificado. Calcula prazos e elegibilidade.",
        CheckReturnArgs,
        check_return,
    ),
    Tool(
        "open_ticket",
        "Abre chamado para a equipe humana: reclamação, cancelamento, cotação de frete, item sem "
        "cadastro, ou qualquer caso que o manual não resolve.",
        OpenTicketArgs,
        open_ticket,
    ),
)
TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}


def _clean_schema(node):
    if isinstance(node, dict):
        options = node.get("anyOf")
        if options:
            concrete = [option for option in options if option.get("type") != "null"]
            merged = {key: value for key, value in node.items() if key != "anyOf"}
            merged.update(concrete[0])
            node = merged
        return {key: _clean_schema(value) for key, value in node.items() if key != "title"}
    if isinstance(node, list):
        return [_clean_schema(item) for item in node]
    return node


def _inline_refs(node, definitions):
    if isinstance(node, dict):
        if "$ref" in node:
            return _inline_refs(definitions[node["$ref"].split("/")[-1]], definitions)
        return {
            key: _inline_refs(value, definitions) for key, value in node.items() if key != "$defs"
        }
    if isinstance(node, list):
        return [_inline_refs(item, definitions) for item in node]
    return node


def tool_schemas() -> list[dict]:
    schemas = []
    for tool in TOOLS:
        schema = tool.args.model_json_schema()
        schema = _clean_schema(_inline_refs(schema, schema.get("$defs", {})))
        schema.setdefault("properties", {})
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": schema,
                },
            }
        )
    return schemas


def run_tool(ctx: ToolContext, name: str, raw_args: dict) -> ToolResult:
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        return ToolResult({"erro": f"Ferramenta {name} não existe."})
    try:
        args = tool.args.model_validate(raw_args)
    except ValidationError as error:
        problems = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors()]
        return ToolResult({"erro": "Argumentos inválidos.", "detalhes": problems})
    try:
        return tool.run(ctx, args)
    except ValueError as error:
        return ToolResult({"erro": str(error)})
