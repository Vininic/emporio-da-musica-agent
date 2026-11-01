# Devolução fora do prazo

Non-trivial: identity check, sales channel, a return window computed from the order, and a ticket for what the manual does not settle.

Recorded 2026-11-01 17:10.

**Cliente:** Me arrependi da minha compra, posso devolver meu pedido?

**Amadeus:** Vamos ver. Me passa o número do pedido e o telefone do cadastro?

**Cliente:** Pedido 7, telefone (67) 99789-0123. Comprei pelo site.

_Tools: lookup_order, check_return, search_policies_

**Amadeus:** Olhei seu pedido. Pelo site você tem até 7 dias corridos após receber para desistir, e como a entrega foi prevista para 17/02, esse prazo acabou em 24/02 .

> Block: order 7: delivered, R$ 159,90
> Block: return, order 7: nao_elegivel, deadline 24/02/2026
> Block: cited: 4.1 Direito de Arrependimento (Compras Online)

**Cliente:** Poxa. Mas recebi com um defeito, faz diferença?

_Tools: check_return, search_policies_

**Amadeus:** Faz diferença sim. Passou dos 30 dias para troca direta, mas você está dentro da garantia legal de 90 dias que vai até 18/05 . Me conta qual é o defeito para eu abrir um chamado para a equipe cuidar disso.

> Block: return, order 7: garantia, deadline 18/05/2026
> Block: cited: 8.1 Garantia Legal
