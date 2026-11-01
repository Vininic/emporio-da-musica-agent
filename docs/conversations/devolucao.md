# Devolução fora do prazo

Non-trivial: identity check, sales channel, a return window computed from the order, and a ticket for what the manual does not settle.

Recorded 2026-10-31 19:56.

**Cliente:** Me arrependi da minha compra, posso devolver meu pedido?

**Amadeus:** Para verificar a devolução por arrependimento, preciso do número do pedido e do telefone cadastrado.

**Cliente:** Pedido 7, telefone (67) 99789-0123. Comprei pelo site.

_Tools: lookup_order, check_return, search_policies_

**Amadeus:** O prazo para devolução por arrependimento é de 7 dias corridos após o recebimento, conforme a seção §4.1 das políticas da loja. Como a previsão de entrega foi em 17/02/2026, o prazo encerrou em 24/02/2026.

> Block: return, order 7: nao_elegivel, §4.1, §4.4
> Block: cited: §4.1 Direito de Arrependimento (Compras Online)

**Cliente:** Poxa. Mas recebi com um defeito, faz diferença?

_Tools: check_return, search_policies_

**Amadeus:** Faz diferença. O prazo de troca imediata por defeito na loja é de 30 dias (§4.2), mas o produto está coberto pela garantia legal de 90 dias (§8.1), válida até 18/05/2026. A loja pode intermediar o processo com o fabricante. 



Posso abrir um chamado para a equipe cuidar disso para você?

> Block: return, order 7: garantia, §4.2, §8.1, §8.3
> Block: cited: §4.2 Trocas por Defeito, §8.1 Garantia Legal
