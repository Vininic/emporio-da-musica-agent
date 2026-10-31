# Devolução fora do prazo

Non-trivial: identity check, sales channel, a return window computed from the order, and a ticket for what the manual does not settle.

Recorded 2026-10-31 18:47.

**Cliente:** Me arrependi da minha compra, posso devolver meu pedido?

**Amadeus:** Para verificar a devolução por arrependimento, preciso do número do pedido e do telefone cadastrado.

**Cliente:** Pedido 7, telefone (67) 99789-0123. Comprei pelo site.

_Tools: lookup_order, check_return, search_policies_

**Amadeus:** O prazo para devolução por arrependimento é de até 7 dias corridos após o recebimento (§4.1). Como o seu pedido foi entregue com base na previsão de 17/02/2026, esse prazo expirou em 24/02/2026.

> Block: order 7: entregue, R$ 159,90
> Block: return, order 7: nao_elegivel, §4.1, §4.4
> Block: cited: §4.1 Direito de Arrependimento (Compras Online), §4.3 Trocas por Preferência, §4.4 Itens Não Elegíveis para Troca

**Cliente:** Poxa. Mas recebi com um defeito, faz diferença?

_Tools: check_return, search_policies_

**Amadeus:** Passou do prazo de 30 dias para troca direta, mas você está dentro da garantia legal de 90 dias, que vai até 18/05/2026 (§8.1). A loja pode intermediar o atendimento com o fabricante.

Quer que eu abra um chamado para a assistência técnica?

> Block: return, order 7: garantia, §4.2, §8.1, §8.3
> Block: cited: §8.1 Garantia Legal, §8.2 Garantia do Fabricante, §8.3 O que Não Cobre a Garantia
