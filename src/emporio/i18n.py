from datetime import date
from typing import Literal

Lang = Literal["pt", "en"]
LANGS: tuple[Lang, ...] = ("pt", "en")

CATEGORY_NAMES_EN = {
    1: "Electric guitars",
    2: "Basses",
    3: "Drums and percussion",
    4: "Keyboards and pianos",
    5: "Acoustic guitars",
    6: "Woodwinds",
    7: "Brass",
    8: "Orchestral strings",
    9: "Ukuleles",
}
CATEGORY_ALIASES = {
    1: "guitarra guitar electric",
    2: "baixo bass",
    3: "bateria percussao drum percussion",
    4: "teclado piano sintetizador keyboard synth",
    5: "violao acoustic classical folk",
    6: "sopro madeira flauta clarinete saxofone oboe wind woodwind flute clarinet saxophone",
    7: "metal trompete trombone tuba trompa brass trumpet horn",
    8: "cordas orquestrais violino viola violoncelo contrabaixo violin cello orchestral strings",
    9: "ukulele",
}

SPEC_LABELS = {
    "pt": {
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
    },
    "en": {
        "top": "Top",
        "back_sides": "Back and sides",
        "neck": "Neck",
        "strings": "Strings",
        "scale": "Scale",
        "electronics": "Electronics",
        "color": "Color",
        "body": "Body",
        "shells": "Shells",
        "pieces": "Pieces",
        "hardware": "Hardware",
        "keys": "Keys",
        "type": "Type",
        "polyphony": "Polyphony",
    },
}
SPEC_VALUES = {
    "pt": {"no": "não", "yes": "sim", "steel": "aço"},
    "en": {"no": "no", "yes": "yes", "nylon": "nylon", "aço": "steel"},
}

TEXT = {
    "pt": {
        "available": "disponível",
        "out_of_stock": "temporariamente indisponível",
        "discontinued": "fora do catálogo",
        "coming_soon": "em breve, ainda não está à venda",
        "installments": "até {count}x de {each} sem juros",
        "promotion": "{percent}% off, {name}",
        "empty_categories_note": "Categoria com 0 itens disponíveis: a loja trabalha com ela, mas não há item no sistema agora. Não diga que a loja não vende; ofereça encaminhar à equipe.",
        "empty_category": "A categoria {name} não tem itens no sistema agora. A loja trabalha com ela: não diga que não vende. Ofereça encaminhar à equipe.",
        "not_found_note": "Nenhum produto com exatamente esse nome. Pergunte qual destes o cliente quer.",
        "promotion_rule": "Promoções não são cumulativas e o desconto de PIX não se aplica sobre elas.",
        "no_such_product": "Produto {id} não existe.",
        "cannot_quote": "{name} está {state} e não pode ser orçado.",
        "short_stock": "Estoque insuficiente de {name}.",
        "metro": "região metropolitana de Campo Grande",
        "outside_metro": "fora da região metropolitana",
        "shipping_rule": "Grátis acima de R$ 500,00. Abaixo disso, R$ 35,00.",
        "free": "grátis",
        "shipping_quote": "calculado pelo CEP, peso e dimensões; a equipe informa o valor. Não invente um valor de frete.",
        "special_shipping": "Instrumento de grande porte pode exigir cotação individual.",
        "motoboy": "Motoboy próprio",
        "business_days": "{range} dias úteis",
        "store_hours": "Segunda a sexta, 09:00 às 18:00. Sábado, 09:00 às 13:00. Domingo e feriados, fechado.",
        "locked": "Limite de tentativas atingido. Não tente de novo. Oriente o cliente a falar com a equipe pelo telefone da loja.",
        "phone_needed": "Falta o telefone do cadastro. Peça ao cliente.",
        "mismatch": "Número do pedido e telefone não conferem. Não diga qual dos dois está errado nem se o pedido existe.",
        "late": "Entrega atrasada. Peça desculpas, informe o atraso sem deduzir a causa e abra um chamado.",
        "needs_verification": "Verifique o pedido com lookup_order, com número e telefone, antes disso.",
        "estimate_base": "previsão de entrega do pedido, pois o sistema não registra o recebimento",
        "ticket_limit": "Limite de chamados desta conversa atingido. Oriente a ligar para a loja.",
        "ticket_return": "em até 24 horas úteis",
        "tool_missing": "Ferramenta {name} não existe.",
        "bad_args": "Argumentos inválidos.",
        "status": {
            "pending": "aguardando confirmação",
            "confirmed": "confirmado",
            "shipped": "enviado",
            "delivered": "entregue",
            "cancelled": "cancelado",
        },
        "payment": {"pix": "PIX", "debit": "cartão de débito", "boleto": "boleto"},
        "credit": "cartão de crédito em {count}",
        "guide": {
            "channel_unknown": "Pergunte se a compra foi online ou na loja física antes de responder.",
            "not_delivered_yet": "O pedido ainda não foi entregue, então o prazo não começou.",
            "received_date_unknown": "Pergunte a data em que o cliente recebeu o produto.",
            "not_shipped_no_cancellation_rule": "O manual não tem regra de cancelamento antes do envio. Não prometa nada: abra um chamado.",
            "order_cancelled": "O pedido já está cancelado, não há o que devolver.",
            "regret_within_window": "Dentro do direito de arrependimento (seção 4.1).",
            "regret_past_window": "Fora do prazo de 7 dias do direito de arrependimento (seção 4.1).",
            "store_purchase_within_window": "Compra na loja física não tem direito de arrependimento (a seção 4.1 vale para online), mas cabe troca por preferência dentro de 7 dias (seção 4.3).",
            "store_purchase_past_window": "Compra na loja física não tem direito de arrependimento, e a troca por preferência (seção 4.3) já passou de 7 dias.",
            "preference_within_window": "Dentro do prazo de troca por preferência (seção 4.3).",
            "preference_past_window": "Fora do prazo de troca por preferência (seção 4.3).",
            "defect_exchange_window": "Dentro dos 30 dias de troca por defeito (seção 4.2).",
            "defect_legal_warranty": "Passou dos 30 dias de troca, mas está na garantia legal de 90 dias (seção 8.1). A loja pode intermediar com o fabricante.",
            "defect_manufacturer_warranty": "Passou da garantia legal. Vale a garantia do fabricante (seção 8.2), com intermediação da loja.",
        },
    },
    "en": {
        "available": "available",
        "out_of_stock": "temporarily unavailable",
        "discontinued": "no longer in the catalog",
        "coming_soon": "coming soon, not on sale yet",
        "installments": "up to {count}x of {each}, interest free",
        "promotion": "{percent}% off, {name}",
        "empty_categories_note": "A category with 0 available items: the store works with it, but no item is in the system right now. Do not say the store does not sell it; offer to pass this to the team.",
        "empty_category": "The {name} category has no items in the system right now. The store works with it: do not say it does not sell them. Offer to pass this to the team.",
        "not_found_note": "No product with exactly that name. Ask which of these the customer means.",
        "promotion_rule": "Promotions do not stack, and the PIX discount does not apply on top of them.",
        "no_such_product": "Product {id} does not exist.",
        "cannot_quote": "{name} is {state} and cannot be quoted.",
        "short_stock": "Not enough stock of {name}.",
        "metro": "Campo Grande metropolitan area",
        "outside_metro": "outside the metropolitan area",
        "shipping_rule": "Free above R$ 500.00. Below that, R$ 35.00.",
        "free": "free",
        "shipping_quote": "calculated from ZIP code, weight and size; the team provides the amount. Do not make up a shipping cost.",
        "special_shipping": "Large instruments may need an individual shipping quote.",
        "motoboy": "Store courier",
        "business_days": "{range} business days",
        "store_hours": "Monday to Friday, 09:00 to 18:00. Saturday, 09:00 to 13:00. Sundays and holidays, closed.",
        "locked": "Attempt limit reached. Do not try again. Tell the customer to reach the team on the store phone.",
        "phone_needed": "The phone on file is missing. Ask the customer for it.",
        "mismatch": "Order number and phone do not match. Do not say which one is wrong or whether the order exists.",
        "late": "Delivery is late. Apologize, state the delay without guessing the cause, and open a ticket.",
        "needs_verification": "Verify the order with lookup_order, using number and phone, first.",
        "estimate_base": "the order's estimated delivery date, since the system does not record receipt",
        "ticket_limit": "Ticket limit for this conversation reached. Tell the customer to call the store.",
        "ticket_return": "within 24 business hours",
        "tool_missing": "Tool {name} does not exist.",
        "bad_args": "Invalid arguments.",
        "status": {
            "pending": "awaiting confirmation",
            "confirmed": "confirmed",
            "shipped": "shipped",
            "delivered": "delivered",
            "cancelled": "cancelled",
        },
        "payment": {"pix": "PIX", "debit": "debit card", "boleto": "boleto"},
        "credit": "credit card in {count} installments",
        "guide": {
            "channel_unknown": "Ask whether the purchase was online or in the physical store before answering.",
            "not_delivered_yet": "The order has not been delivered yet, so the period has not started.",
            "received_date_unknown": "Ask the date the customer received the product.",
            "not_shipped_no_cancellation_rule": "The manual has no rule for cancelling before shipment. Promise nothing: open a ticket.",
            "order_cancelled": "The order is already cancelled, there is nothing to return.",
            "regret_within_window": "Within the right of withdrawal (section 4.1).",
            "regret_past_window": "Past the 7-day right of withdrawal (section 4.1).",
            "store_purchase_within_window": "In-store purchases have no right of withdrawal (section 4.1 covers online), but a preference exchange applies within 7 days (section 4.3).",
            "store_purchase_past_window": "In-store purchases have no right of withdrawal, and the preference exchange (section 4.3) is past its 7 days.",
            "preference_within_window": "Within the preference exchange period (section 4.3).",
            "preference_past_window": "Past the preference exchange period (section 4.3).",
            "defect_exchange_window": "Within the 30-day defect exchange (section 4.2).",
            "defect_legal_warranty": "Past the 30-day exchange but within the 90-day legal warranty (section 8.1). The store can mediate with the manufacturer.",
            "defect_manufacturer_warranty": "Past the legal warranty. The manufacturer's warranty applies (section 8.2), with the store mediating.",
        },
    },
}

AGENT_TEXT = {
    "pt": {
        "fallback": "Não consegui confirmar isso no sistema e prefiro não chutar. A equipe da loja resolve pelo telefone (67) 3341-4444.",
        "provider_down": "Estou sem acesso ao sistema neste momento. Tenta de novo em instantes, ou fala com a equipe pelo telefone (67) 3341-4444.",
        "bad_key": "A chave de API foi recusada. Confira em Configurações.",
        "correction": "[verificação interna, não é mensagem do cliente] Problemas na sua última resposta: {problems}. Consulte a ferramenta certa, execute a ação ou retire a afirmação, e reescreva a resposta inteira ao cliente sem mencionar esta verificação.",
        "empty": "resposta vazia",
        "ticket_claim": "disse que abriu ou abriria um chamado sem chamar open_ticket",
    },
    "en": {
        "fallback": "I could not confirm that in the system and would rather not guess. The store team can sort it out on (67) 3341-4444.",
        "provider_down": "I cannot reach the system right now. Try again in a moment, or call the team on (67) 3341-4444.",
        "bad_key": "The API key was rejected. Check it in Settings.",
        "correction": "[internal check, not a customer message] Problems in your last answer: {problems}. Use the right tool, take the action, or remove the claim, and rewrite the whole answer to the customer without mentioning this check.",
        "empty": "empty answer",
        "ticket_claim": "said a ticket was or would be opened without calling open_ticket",
    },
}


def text(lang: Lang) -> dict:
    return TEXT[lang]


def brl(cents: int, lang: Lang = "pt") -> str:
    reais, centavos = divmod(abs(cents), 100)
    sign = "-" if cents < 0 else ""
    grouped = f"{reais:,}"
    if lang == "pt":
        return f"{sign}R$ {grouped.replace(',', '.')},{centavos:02d}"
    return f"{sign}R$ {grouped}.{centavos:02d}"


def format_date(day: date, lang: Lang = "pt") -> str:
    return day.strftime("%d/%m/%Y" if lang == "pt" else "%b %d, %Y")
