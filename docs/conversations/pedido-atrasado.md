# Pedido atrasado

Order tracking without the phone is refused; with it, a late delivery opens a ticket.

Recorded 2026-11-02 19:06.

**Cliente:** Cadê meu pedido 8?

_Tools: lookup_order_

**Amadeus:** Para eu olhar como está a entrega, você me passa o telefone do cadastro, por favor?

**Cliente:** (67) 99654-7821

_Tools: lookup_order, open_ticket_

**Amadeus:** Olhei seu pedido aqui, Ana. O ukulele Kala KA-C Concert Mogno já foi enviado, mas a previsão de entrega era para 28/02/2026 e ele acabou atrasando. 

Abri um chamado para a equipe verificar o que aconteceu com a transportadora, e o retorno vem em até 24 horas úteis.

> Block: order 8: shipped, R$ 349,90
> Block: ticket 1: complaint

**Cliente:** Já era pra ter chegado. Podem ver isso pra mim?

_Tools: open_ticket_

**Amadeus:** Eu entendo perfeitamente, a ansiedade com um instrumento novo na estrada é grande. Reforcei o chamado com a equipe para darem prioridade nisso, e o retorno vem em até 24 horas úteis.

> Block: ticket 2: complaint
