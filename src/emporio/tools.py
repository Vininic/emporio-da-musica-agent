import json
import time
from collections import Counter, defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from emporio.config import ROOT, Clock
from emporio.domain import hours, shipping
from emporio.domain.money import to_cents
from emporio.domain.pricing import COMBINED_PAYMENT_ABOVE_CENTS, max_installments
from emporio.domain.returns import Channel, Reason, assess
from emporio.i18n import (
    CATEGORY_ALIASES,
    CATEGORY_NAMES_EN,
    SPEC_LABELS,
    SPEC_VALUES,
    Lang,
    brl,
    format_date,
    text,
)
from emporio.journal import Journal
from emporio.policies import Section
from emporio.retrieval import Document, HybridIndex, tokenize
from emporio.store import Availability, Order, Product, Store, normalize_text, phone_digits

MAX_VERIFICATION_ATTEMPTS = 3
ORDER_ATTEMPT_LIMIT = 5
ORDER_ATTEMPT_WINDOW = 900.0
MANUAL_WHATSAPP = "(67) 3321-4500"
MAX_TICKETS = 3
STORE_FACTS = {
    "name": "Empório da Música",
    "address": "Rua 14 de Maio, 3200, Centro, Campo Grande - MS, 79202-333",
    "phone": "(67) 3341-4444",
    "email": "contato@emporiodamusica.com.br",
    "founded": "2008",
}
STORE_MAP = {"lat": -20.464, "lon": -54.6163}
PRODUCT_IMAGES_FILE = ROOT / "data" / "product_images.json"
PRODUCT_IMAGES = (
    json.loads(PRODUCT_IMAGES_FILE.read_text(encoding="utf-8"))
    if PRODUCT_IMAGES_FILE.exists()
    else {}
)


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


class VerificationAttempts:
    def __init__(self):
        self._failures: dict[int, deque[float]] = defaultdict(deque)

    def _recent(self, order_number: int) -> deque[float]:
        failures = self._failures[order_number]
        while failures and time.monotonic() - failures[0] > ORDER_ATTEMPT_WINDOW:
            failures.popleft()
        return failures

    def locked(self, order_number: int) -> bool:
        return len(self._recent(order_number)) >= ORDER_ATTEMPT_LIMIT

    def record_failure(self, order_number: int) -> None:
        self._recent(order_number).append(time.monotonic())

    def clear(self, order_number: int) -> None:
        self._failures.pop(order_number, None)


@dataclass
class ToolContext:
    store: Store
    catalog_index: HybridIndex
    policy_index: HybridIndex
    sections: dict[str, Section]
    clock: Clock
    journal: Journal
    session: Session
    lang: Lang = "pt"
    attempts: VerificationAttempts = field(default_factory=VerificationAttempts)
    customer_text: str | None = None


def catalog_documents(store: Store) -> list[Document]:
    return [
        Document(
            str(product.id),
            product.name,
            f"{product.category}. {CATEGORY_ALIASES[product.category_id]}. "
            f"{product.description} {_specs_text(product, 'pt')}",
        )
        for product in store.all_products()
    ]


def _category_name(product: Product, lang: Lang) -> str:
    return CATEGORY_NAMES_EN[product.category_id] if lang == "en" else product.category


def _spec_value(value, lang: Lang) -> str:
    return SPEC_VALUES[lang].get(str(value), str(value))


def _specs(product: Product, lang: Lang) -> dict:
    return {
        SPEC_LABELS[lang].get(key, key): _spec_value(value, lang)
        for key, value in product.specs.items()
    }


def _specs_text(product: Product, lang: Lang) -> str:
    return " ".join(f"{key}: {value}." for key, value in _specs(product, lang).items())


def _availability_text(product: Product, lang: Lang) -> str:
    return text(lang)[
        {
            Availability.AVAILABLE: "available",
            Availability.OUT_OF_STOCK: "out_of_stock",
            Availability.DISCONTINUED: "discontinued",
            Availability.COMING_SOON: "coming_soon",
        }[product.availability]
    ]


def _price_view(product: Product, lang: Lang) -> dict:
    quote = product.quote()
    view = {
        "list_price": brl(quote.list_cents, lang),
        "final_price": brl(quote.final_cents, lang),
        "pix_price": brl(quote.pix_cents, lang),
        "pix_discount_applied": quote.pix_discount_applies,
        "installments": text(lang)["installments"].format(
            count=quote.max_installments, each=brl(quote.installment_cents, lang)
        ),
    }
    if quote.promotion is not None:
        view["promotion"] = text(lang)["promotion"].format(
            percent=quote.promotion.percent, name=quote.promotion.name
        )
    return view


def _price_block(product: Product) -> dict:
    quote = product.quote()
    return {
        "list": quote.list_cents,
        "final": quote.final_cents,
        "pix": quote.pix_cents,
        "pix_applies": quote.pix_discount_applies,
        "count": quote.max_installments,
        "each": quote.installment_cents,
        "promo_percent": quote.promotion.percent if quote.promotion else None,
        "promo_name": quote.promotion.name if quote.promotion else None,
    }


def _product_summary(product: Product, lang: Lang) -> dict:
    summary = {
        "id": product.id,
        "name": product.name,
        "category": _category_name(product, lang),
        "status": _availability_text(product, lang),
    }
    if product.availability is Availability.AVAILABLE:
        summary.update(_price_view(product, lang))
    elif product.availability is Availability.OUT_OF_STOCK:
        summary["list_price"] = brl(product.price_cents, lang)
    return summary


def _product_detail(product: Product, lang: Lang) -> dict:
    detail = _product_summary(product, lang)
    detail["description"] = product.description
    detail["specs"] = _specs(product, lang)
    if product.availability is Availability.AVAILABLE:
        detail["stock"] = product.stock
    if product.expired_promotions:
        detail["expired_promotions"] = [
            f"{promotion.name} ({promotion.percent}%)" for promotion in product.expired_promotions
        ]
    return detail


def _product_block(product: Product, lang: Lang, with_specs: bool = False) -> dict:
    block = {
        "type": "product",
        "id": product.id,
        "name": product.name,
        "category_id": product.category_id,
        "category": _category_name(product, lang),
        "availability": product.availability.value,
        "stock": product.stock if product.availability is Availability.AVAILABLE else 0,
    }
    if product.availability is Availability.AVAILABLE:
        block["price"] = _price_block(product)
    elif product.availability is Availability.OUT_OF_STOCK:
        block["list_price"] = product.price_cents
    if with_specs:
        block["specs"] = _specs(product, lang)
    image = PRODUCT_IMAGES.get(str(product.id))
    if image:
        block["image"] = {
            "url": image["url"],
            "source": image["source"],
            "illustrative": image.get("illustrative", False),
        }
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
    categories = []
    for category in ctx.store.categories():
        name = CATEGORY_NAMES_EN[category["id"]] if ctx.lang == "en" else category["name"]
        categories.append({"category": name, "available_items": category["available"]})
    return ToolResult({"categories": categories, "note": text(ctx.lang)["empty_categories_note"]})


class SearchProductsArgs(BaseModel):
    query: str | None = Field(
        None,
        description="What the customer is looking for, in free text, e.g. warm tone for a beginner",
    )
    category: str | None = Field(
        None, description="Category, e.g. violões, guitarras, ukuleles, flauta"
    )
    max_price: float | None = Field(None, description="Maximum price in reais")
    min_price: float | None = Field(None, description="Minimum price in reais")
    strings: Literal["nylon", "aço"] | None = Field(None, description="String type")
    electric: bool | None = Field(None, description="Has a pickup or electronics")
    include_unavailable: bool = Field(False, description="Include sold out and discontinued items")
    limit: int = Field(12, ge=1, le=20)


def _category(ctx: ToolContext, name: str | None) -> dict | None:
    if not name:
        return None
    wanted = set(tokenize(name))
    for category in ctx.store.categories():
        aliases = set(tokenize(f"{category['name']} {CATEGORY_ALIASES[category['id']]}"))
        if wanted & aliases:
            return category
    return None


def _named_unavailable(ctx: ToolContext, query: str) -> Product | None:
    wanted = set(tokenize(query))
    for product in ctx.store.all_products():
        if product.availability is Availability.AVAILABLE:
            continue
        brand, *rest = tokenize(product.name)
        models = [token for token in rest if any(char.isdigit() for char in token)]
        if models and brand in wanted and wanted.issuperset(models):
            return product
    return None


def search_products(ctx: ToolContext, args: SearchProductsArgs) -> ToolResult:
    named = _named_unavailable(ctx, args.query) if args.query else None
    if named is not None:
        return get_product(ctx, GetProductArgs(name=named.name))

    category = _category(ctx, args.category)
    if category is not None and not category["available"]:
        name = CATEGORY_NAMES_EN[category["id"]] if ctx.lang == "en" else category["name"]
        return ToolResult(
            {"total": 0, "products": [], "note": text(ctx.lang)["empty_category"].format(name=name)}
        )

    products = ctx.store.filter_products(
        category_id=category["id"] if category else None,
        max_price_cents=None if args.max_price is None else to_cents(args.max_price),
        min_price_cents=None if args.min_price is None else to_cents(args.min_price),
        strings=args.strings,
        electric=args.electric,
        only_available=not args.include_unavailable,
    )

    trace = None
    if args.query and products:
        by_id = {str(product.id): product for product in products}
        hits = ctx.catalog_index.search(args.query, top_k=len(by_id), allowed=set(by_id))
        ranked = [by_id[hit.id] for hit in hits]
        products = ranked + [product for product in products if product not in ranked]
        trace = {
            "mode": "hybrid" if ctx.catalog_index.uses_vectors else "keyword",
            "top": [{"id": hit.id, "score": hit.score} for hit in hits[:5]],
        }

    shown = products[: args.limit]
    data = {
        "total": len(products),
        "shown": len(shown),
        "products": [_product_summary(product, ctx.lang) for product in shown],
    }
    if trace is not None:
        data["_search"] = trace
    block = None
    if shown:
        block = {
            "type": "product_list",
            "total": len(products),
            "items": [_product_block(product, ctx.lang) for product in shown],
        }
    return ToolResult(data, block)


class GetProductArgs(BaseModel):
    name: str = Field(description="Product name or model, e.g. Takamine GD20")


def _match_products(ctx: ToolContext, name: str) -> tuple[Product | None, list[Product]]:
    products = ctx.store.all_products()
    wanted = normalize_text(name)
    for product in products:
        if normalize_text(product.name) == wanted:
            return product, []

    wanted_tokens = set(tokenize(name))
    scored = []
    for product in products:
        overlap = len(wanted_tokens & set(tokenize(product.name)))
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
    product, candidates = _match_products(ctx, args.name)
    if product is None:
        return ToolResult(
            {
                "found": False,
                "note": text(ctx.lang)["not_found_note"],
                "similar": [_product_summary(candidate, ctx.lang) for candidate in candidates],
            }
        )

    data = {"found": True, "product": _product_detail(product, ctx.lang)}
    if product.availability is not Availability.AVAILABLE:
        alternatives = _alternatives(ctx, product)
        data["alternatives"] = [_product_summary(item, ctx.lang) for item in alternatives]
        block = {
            "type": "product_list",
            "total": len(alternatives) + 1,
            "items": [_product_block(item, ctx.lang) for item in (product, *alternatives)],
        }
        return ToolResult(data, block)
    return ToolResult(data, _product_block(product, ctx.lang, with_specs=True))


class ListPromotionsArgs(BaseModel):
    pass


def list_promotions(ctx: ToolContext, args: ListPromotionsArgs) -> ToolResult:
    products = [
        p for p in ctx.store.active_promotions() if p.availability is Availability.AVAILABLE
    ]
    return ToolResult(
        {
            "active_promotions": [_product_summary(product, ctx.lang) for product in products],
            "rule": text(ctx.lang)["promotion_rule"],
        },
        {
            "type": "product_list",
            "total": len(products),
            "items": [_product_block(product, ctx.lang) for product in products],
        },
    )


class CartItem(BaseModel):
    product_id: int
    quantity: int = Field(1, ge=1, le=50)


class QuotePurchaseArgs(BaseModel):
    items: list[CartItem] = Field(min_length=1, max_length=10)
    city: str | None = Field(None, description="Delivery city, to include shipping")


def quote_purchase(ctx: ToolContext, args: QuotePurchaseArgs) -> ToolResult:
    words = text(ctx.lang)
    lines, block_lines = [], []
    final, pix, list_total = 0, 0, 0
    category_id = None
    wanted = Counter()
    for item in args.items:
        wanted[item.product_id] += item.quantity
    for item in args.items:
        product = ctx.store.product(item.product_id)
        if product is None:
            return ToolResult({"error": words["no_such_product"].format(id=item.product_id)})
        if product.availability is not Availability.AVAILABLE:
            state = _availability_text(product, ctx.lang)
            return ToolResult(
                {"error": words["cannot_quote"].format(name=product.name, state=state)}
            )
        if wanted[item.product_id] > product.stock:
            return ToolResult(
                {
                    "error": words["short_stock"].format(name=product.name),
                    "available": product.stock,
                }
            )
        quote = product.quote(item.quantity)
        final += quote.final_cents
        pix += quote.pix_cents
        list_total += quote.list_cents
        if category_id not in shipping.LARGE_INSTRUMENT_CATEGORIES:
            category_id = product.category_id
        promotion = (
            words["promotion"].format(percent=quote.promotion.percent, name=quote.promotion.name)
            if quote.promotion
            else None
        )
        lines.append(
            {
                "product": product.name,
                "quantity": item.quantity,
                "list_price": brl(quote.list_cents, ctx.lang),
                "final_price": brl(quote.final_cents, ctx.lang),
                "promotion": promotion,
            }
        )
        block_lines.append(
            {
                "name": product.name,
                "quantity": item.quantity,
                "final": quote.final_cents,
                "promo_percent": quote.promotion.percent if quote.promotion else None,
            }
        )

    count = max_installments(final)
    each = round(final / count)
    data = {
        "items": lines,
        "list_total": brl(list_total, ctx.lang),
        "total_card_debit_boleto": brl(final, ctx.lang),
        "total_pix": brl(pix, ctx.lang),
        "installments": words["installments"].format(count=count, each=brl(each, ctx.lang)),
        "combined_payment_allowed": final > COMBINED_PAYMENT_ABOVE_CENTS,
    }
    block = {
        "type": "quote",
        "lines": block_lines,
        "final": final,
        "pix": pix,
        "count": count,
        "each": each,
    }
    if args.city:
        view, shipping_block = _shipping(ctx.lang, args.city, final, category_id)
        data["shipping"] = view
        block["shipping"] = shipping_block
    return ToolResult(data, block)


class EstimateShippingArgs(BaseModel):
    city: str
    order_value: float | None = Field(None, description="Order value in reais, if known")


def _shipping(lang: Lang, city: str, total_cents: int | None, category_id: int | None):
    words = text(lang)
    result = shipping.estimate(city, total_cents or 0, category_id)
    metro = result.region == "metropolitana"
    options = []
    for name, term in result.deadlines:
        label = words["motoboy"] if metro else name
        days = term.replace(" dias úteis", "").replace(" a ", "-" if lang == "en" else " a ")
        options.append({"carrier": label, "term": words["business_days"].format(range=days)})

    view = {"region": words["metro"] if metro else words["outside_metro"], "options": options}
    block = {"city": city, "metro": metro, "options": options, "special": result.special_quote}
    if metro:
        view["rule"] = words["shipping_rule"]
        if total_cents is not None:
            view["cost"] = words["free"] if result.fee_cents == 0 else brl(result.fee_cents, lang)
            block["fee"] = result.fee_cents
    else:
        view["cost"] = words["shipping_quote"]
    if result.special_quote:
        view["special_shipping"] = words["special_shipping"]
    return view, block


def estimate_shipping(ctx: ToolContext, args: EstimateShippingArgs) -> ToolResult:
    total = None if args.order_value is None else to_cents(args.order_value)
    view, _ = _shipping(ctx.lang, args.city, total, None)
    return ToolResult(view)


class SearchPoliciesArgs(BaseModel):
    query: str = Field(description="What you need to know from the store's policies")


def search_policies(ctx: ToolContext, args: SearchPoliciesArgs) -> ToolResult:
    hits = ctx.policy_index.search(args.query, top_k=3)
    sections = [ctx.sections[hit.id] for hit in hits]

    def public_text(section: Section) -> str:
        return section.text.replace(MANUAL_WHATSAPP, STORE_FACTS["phone"])

    return ToolResult(
        {
            "excerpts": [
                {"section": s.id, "title": s.title, "text": public_text(s)} for s in sections
            ],
            "_search": {
                "mode": "hybrid" if ctx.policy_index.uses_vectors else "keyword",
                "top": [{"id": hit.id, "score": hit.score} for hit in hits],
            },
        },
        {
            "type": "policy",
            "sections": [{"id": s.id, "title": s.title, "text": public_text(s)} for s in sections],
        },
    )


class StoreInfoArgs(BaseModel):
    pass


def store_view(now: datetime, lang: Lang) -> dict:
    is_open = hours.is_open(now)
    data = {**STORE_FACTS, "hours": text(lang)["store_hours"], "open_now": is_open}
    if not is_open:
        data["opens"] = hours.describe_opening(hours.next_opening(now), now, lang)
    return data


def store_block(now: datetime, lang: Lang) -> dict:
    return {
        "type": "store",
        **store_view(now, lang),
        "schedule": hours.week_schedule(now, lang),
        "holidays": hours.next_holidays(now),
        "map": STORE_MAP,
    }


def store_info(ctx: ToolContext, args: StoreInfoArgs) -> ToolResult:
    now = ctx.clock.now()
    return ToolResult(store_view(now, ctx.lang), store_block(now, ctx.lang))


class LookupOrderArgs(BaseModel):
    order_number: int
    phone: str = Field(description="Phone on file, as given by the customer")


def _payment_label(method: str, lang: Lang) -> str:
    words = text(lang)
    if method.startswith("credit_"):
        return words["credit"].format(count=method.removeprefix("credit_"))
    return words["payment"].get(method, method)


def _order_view(order: Order, today: date, lang: Lang) -> tuple[dict, dict]:
    words = text(lang)
    view = {
        "number": order.id,
        "customer": order.customer_first_name,
        "order_date": format_date(date.fromisoformat(order.order_date), lang),
        "status": words["status"].get(order.status, order.status),
        "total": brl(order.total_cents, lang),
        "payment": _payment_label(order.payment_method, lang),
        "items": [f"{item.quantity}x {item.product_name}" for item in order.items],
    }
    block = {
        "type": "order",
        "number": order.id,
        "order_date": order.order_date,
        "status": order.status,
        "total": order.total_cents,
        "payment": order.payment_method,
        "items": view["items"],
        "tracking": order.tracking_code,
        "eta": order.estimated_delivery,
        "note": order.notes if lang == "pt" else None,
    }
    if order.tracking_code:
        view["tracking_code"] = order.tracking_code
    if order.estimated_delivery:
        view["estimated_delivery"] = format_date(date.fromisoformat(order.estimated_delivery), lang)
        if order.status == "shipped":
            delay = (today - date.fromisoformat(order.estimated_delivery)).days
            if delay > 0:
                view["days_late"] = delay
                view["note"] = words["late"]
                block["days_late"] = delay
    if order.notes:
        view["record_note"] = order.notes
    return view, block


def lookup_order(ctx: ToolContext, args: LookupOrderArgs) -> ToolResult:
    session = ctx.session
    words = text(ctx.lang)
    locked = session.failed_verifications >= MAX_VERIFICATION_ATTEMPTS
    if locked or ctx.attempts.locked(args.order_number):
        return ToolResult({"verified": False, "locked": True, "note": words["locked"]})

    digits = phone_digits(args.phone)
    told = ctx.customer_text is None or digits[-8:] in phone_digits(ctx.customer_text)
    if not digits or not told:
        return ToolResult({"verified": False, "note": words["phone_needed"]})

    order = ctx.store.verified_order(args.order_number, args.phone)
    if order is None:
        session.failed_verifications += 1
        ctx.attempts.record_failure(args.order_number)
        return ToolResult({"verified": False, "note": words["mismatch"]})

    ctx.attempts.clear(args.order_number)
    if order.id not in session.verified_orders:
        session.verified_orders.append(order.id)
    view, block = _order_view(order, ctx.clock.today(), ctx.lang)
    return ToolResult({"verified": True, "order": view}, block)


class CheckReturnArgs(BaseModel):
    order_number: int = Field(
        description="Order already verified with lookup_order in this conversation"
    )
    reason: Literal["regret", "defect", "preference"]
    channel: Literal["online", "store", "unknown"] = "unknown"
    received_on: str | None = Field(
        None, description="Date the customer received it, YYYY-MM-DD, if given"
    )


REASONS = {"regret": Reason.REGRET, "defect": Reason.DEFECT, "preference": Reason.PREFERENCE}
CHANNELS = {"online": Channel.ONLINE, "store": Channel.STORE, "unknown": Channel.UNKNOWN}


def check_return(ctx: ToolContext, args: CheckReturnArgs) -> ToolResult:
    words = text(ctx.lang)
    if args.order_number not in ctx.session.verified_orders:
        return ToolResult({"verified": False, "note": words["needs_verification"]})

    order = ctx.store.order_for_verified_session(args.order_number)
    received = date.fromisoformat(args.received_on) if args.received_on else None
    ordered = date.fromisoformat(order.order_date)
    if received is not None and not ordered <= received <= ctx.clock.today():
        return ToolResult({"note": words["bad_received_date"]})
    result = assess(
        REASONS[args.reason],
        order.status,
        ctx.clock.today(),
        date.fromisoformat(order.order_date),
        date.fromisoformat(order.estimated_delivery) if order.estimated_delivery else None,
        CHANNELS[args.channel],
        received,
    )
    view = {
        "order": order.id,
        "outcome": result.outcome.value,
        "guidance": words["guide"][result.reason_code],
        "sections": list(result.policy_sections),
    }
    block = {
        "type": "return",
        "order": order.id,
        "outcome": result.outcome.value,
        "code": result.reason_code,
        "sections": list(result.policy_sections),
        "deadline": result.deadline.isoformat() if result.deadline else None,
        "days_passed": result.days_since_reference,
        "estimated": result.received_date_is_estimate,
    }
    if result.deadline is not None:
        view["deadline"] = format_date(result.deadline, ctx.lang)
    if result.days_since_reference is not None:
        view["days_passed"] = result.days_since_reference
    if result.received_date_is_estimate:
        view["counted_from"] = words["estimate_base"]
    return ToolResult(view, block)


class OpenTicketArgs(BaseModel):
    kind: Literal["complaint", "cancellation", "shipping_quote", "product", "warranty", "other"]
    summary: str = Field(max_length=500)
    contact: str | None = Field(None, description="Name and phone, if the customer gave them")


def open_ticket(ctx: ToolContext, args: OpenTicketArgs) -> ToolResult:
    session = ctx.session
    words = text(ctx.lang)
    if session.tickets_opened >= MAX_TICKETS:
        return ToolResult({"error": words["ticket_limit"]})
    session.tickets_opened += 1
    ticket_id = ctx.journal.open_ticket(
        session.conversation_id, args.kind, args.summary, args.contact, ctx.clock.now()
    )
    data = {"ticket": ticket_id, "kind": args.kind, "response_time": words["ticket_return"]}
    return ToolResult(
        data, {"type": "ticket", "ticket": ticket_id, "kind": args.kind, "summary": args.summary}
    )


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args: type[BaseModel]
    run: Callable[[ToolContext, BaseModel], ToolResult]


TOOLS = (
    Tool(
        "search_products",
        "Search the instrument catalog. Use for any question about options, price range or recommendations. Returns only what is on sale, with final price, PIX and installments. For a specific model named by the customer, use get_product.",
        SearchProductsArgs,
        search_products,
    ),
    Tool(
        "get_product",
        "Details of a product by name: price, availability, current promotion, expired promotions, specs, and alternatives when unavailable. Call this before saying a named model is not sold.",
        GetProductArgs,
        get_product,
    ),
    Tool(
        "list_promotions",
        "Promotions active now. Use when asked about deals.",
        ListPromotionsArgs,
        list_promotions,
    ),
    Tool(
        "quote_purchase",
        "Total of a purchase of one or more items by payment method, with installments, and shipping when a city is given. Every purchase calculation goes through here.",
        QuotePurchaseArgs,
        quote_purchase,
    ),
    Tool(
        "estimate_shipping",
        "Delivery times and shipping rule for a city.",
        EstimateShippingArgs,
        estimate_shipping,
    ),
    Tool(
        "catalog_overview",
        "The store's categories and how many items each has.",
        CatalogOverviewArgs,
        catalog_overview,
    ),
    Tool(
        "search_policies",
        "Search the store manual: exchanges, returns, warranty, payment, shipping, promotions, privacy. Returns the text with its section number.",
        SearchPoliciesArgs,
        search_policies,
    ),
    Tool(
        "store_info",
        "Address, phone, e-mail, hours, and whether the store is open now.",
        StoreInfoArgs,
        store_info,
    ),
    Tool(
        "lookup_order",
        "Look up an order. Requires the order number AND the phone on file, both given by the customer. Never call with data the customer did not give.",
        LookupOrderArgs,
        lookup_order,
    ),
    Tool(
        "check_return",
        "Assess a return or exchange for an order already verified. Computes deadlines and eligibility.",
        CheckReturnArgs,
        check_return,
    ),
    Tool(
        "open_ticket",
        "Open a ticket for the human team: complaint, cancellation, shipping quote, item not in the system, or anything the manual does not settle.",
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
    words = text(ctx.lang)
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        return ToolResult({"error": words["tool_missing"].format(name=name)})
    try:
        args = tool.args.model_validate(raw_args)
    except ValidationError as error:
        problems = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors()]
        return ToolResult({"error": words["bad_args"], "details": problems})
    try:
        return tool.run(ctx, args)
    except ValueError as error:
        return ToolResult({"error": str(error)})
    except (ArithmeticError, OverflowError, TypeError):
        return ToolResult({"error": words["bad_args"]})
