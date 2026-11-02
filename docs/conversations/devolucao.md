# Devolução fora do prazo

Non-trivial: identity check, sales channel, a return window computed from the order, and a ticket for what the manual does not settle.

Recorded 2026-11-02 19:06.

**Cliente:** Me arrependi da minha compra, posso devolver meu pedido?

**Amadeus:** Vamos ver. Me passa o número do pedido e o telefone do cadastro?

**Cliente:** Pedido 7, telefone (67) 99789-0123. Comprei pelo site.

_Tools: lookup_order, check_return, search_policies_

**Amadeus:** Olhei seu pedido. Nas compras feitas pelo site você tem até 7 dias corridos após o recebimento para desistir da compra, e pela previsão de entrega isso encerrou em 24/02. Como passou desse prazo, não dá mais para aceitar a devolução por arrependimento.

> Block: order 7: delivered, R$ 159,90
> Block: return, order 7: nao_elegivel, deadline 24/02/2026
> Block: cited: 4.1 Direito de Arrependimento (Compras Online)

**Cliente:** Poxa. Mas recebi com um defeito, faz diferença?

_Tools: check_return, search_policies_

**Amadeus:** Faz diferença. Como o problema é defeito, entra na garantia legal de 90 dias a contar da data em que você recebeu, e o prazo vai até 18/05. Quer que eu abra um chamado para a equipe orientar sobre o atendimento?

> Block: return, order 7: garantia, deadline 18/05/2026
> Block: cited: 8.1 Garantia Legal
