# Devolução fora do prazo

Non-trivial: identity check, sales channel, a return window computed from the order, and a ticket for what the manual does not settle.

Recorded 2026-11-01 19:06.

**Cliente:** Me arrependi da minha compra, posso devolver meu pedido?

**Amadeus:** Para eu ver como está a situação do seu pedido e te orientar, preciso que você me passe o número do pedido e o telefone que está no cadastro. Com isso, eu consigo checar o que dá para fazer.

**Cliente:** Pedido 7, telefone (67) 99789-0123. Comprei pelo site.

_Tools: lookup_order, check_return_

**Amadeus:** Olhei aqui no sistema, Letícia. Pelo site, o prazo para desistir da compra por arrependimento é de 7 dias após o recebimento, e como a entrega foi prevista para 17/02, esse prazo encerrou no dia 24/02.

Como já passou desse período, não consigo seguir com a devolução automática. Se você ainda quiser conversar sobre isso, posso abrir um chamado para a equipe avaliar, mas não consigo garantir nada por aqui. Quer que eu abra?

> Block: order 7: delivered, R$ 159,90
> Block: return, order 7: nao_elegivel, deadline 24/02/2026

**Cliente:** Poxa. Mas recebi com um defeito, faz diferença?

_Tools: check_return_

**Amadeus:** Faz diferença, sim. Como passou dos 30 dias, a gente entra na garantia legal de 90 dias. A loja pode intermediar esse contato com o fabricante para resolver o problema do defeito.

Quer que eu abra um chamado agora para a nossa equipe cuidar disso para você?

> Block: return, order 7: garantia, deadline 18/05/2026
