# Devolução fora do prazo

Non-trivial: identity check, sales channel, a return window computed from the order, and a ticket for what the manual does not settle.

Recorded 2026-11-01 17:21.

**Cliente:** Me arrependi da minha compra, posso devolver meu pedido?

**Amadeus:** Vamos ver. Me passa o número do pedido e o telefone do cadastro?

**Cliente:** Pedido 7, telefone (67) 99789-0123. Comprei pelo site.

_Tools: lookup_order, check_return, search_policies_

**Amadeus:** Olhei seu pedido. Como você comprou pelo site, o prazo para desistir é de até 7 dias corridos depois de receber, e pela previsão de entrega isso encerrou em 24/02.

> Block: order 7: delivered, R$ 159,90
> Block: return, order 7: nao_elegivel, deadline 24/02/2026
> Block: cited: 4.1 Direito de Arrependimento (Compras Online)

**Cliente:** Poxa. Mas recebi com um defeito, faz diferença?

_Tools: check_return, search_policies_

**Amadeus:** Faz sim. O prazo de 7 dias é só para arrependimento, mas para defeito você tem a garantia legal de 90 dias a partir do recebimento, o que nos dá margem até 18/05. Se o problema for de fabricação e não de uso, a gente resolve. Quer abrir um chamado para a equipe analisar o caso do seu ukulelê?

> Block: return, order 7: garantia, deadline 18/05/2026
> Block: cited: 8.1 Garantia Legal
