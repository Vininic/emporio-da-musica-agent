# Devolução fora do prazo

Non-trivial: identity check, sales channel, a return window computed from the order, and a ticket for what the manual does not settle.

Recorded 2026-10-31 18:49.

**Cliente:** Me arrependi da minha compra, posso devolver meu pedido?

**Amadeus:** Para verificar a devolução por arrependimento, preciso do número do pedido e do telefone cadastrado. Me informe esses dois dados, por favor.

**Cliente:** Pedido 7, telefone (67) 99789-0123. Comprei pelo site.

_Tools: lookup_order, check_return, search_policies_

**Amadeus:** O pedido 7 passou do prazo de 7 dias corridos (§4.1), calculado a partir da previsão de entrega. O limite era 24/02/2026.

> Block: order 7: entregue, R$ 159,90
> Block: return, order 7: nao_elegivel, §4.1, §4.4
> Block: cited: §4.1 Direito de Arrependimento (Compras Online), §7.3 Situações Especiais, §8.2 Garantia do Fabricante

**Cliente:** Poxa. Mas recebi com um defeito, faz diferença?

_Tools: check_return, search_policies_

**Amadeus:** Faz diferença. Como passou de 30 dias mas está dentro dos 90 dias da garantia legal (§8.1), ainda podemos ajudar com o defeito (§4.2). A Empório da Música intermedia esse processo com o fabricante. 

Quer que eu abra um chamado para nossa equipe cuidar disso?

> Block: return, order 7: garantia, §4.2, §8.1, §8.3
> Block: cited: §8.1 Garantia Legal, §8.2 Garantia do Fabricante, §4.2 Trocas por Defeito
