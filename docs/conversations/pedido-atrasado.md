# Pedido atrasado

Order tracking without the phone is refused; with it, a late delivery opens a ticket.

Recorded 2026-11-01 17:21.

**Cliente:** Cadê meu pedido 8?

_Tools: lookup_order_

**Amadeus:** Para eu olhar o pedido 8, me passa o telefone do cadastro?

**Cliente:** (67) 99654-7821

_Tools: lookup_order, open_ticket_

**Amadeus:** O pedido 8 está com atraso na entrega. Já abri um chamado para a equipe verificar o que aconteceu com a transportadora, e o retorno vem em até 24 horas úteis.

> Block: order 8: shipped, R$ 349,90
> Block: ticket 1: complaint

**Cliente:** Já era pra ter chegado. Podem ver isso pra mim?

**Amadeus:** O chamado já está aberto com a equipe, Ana. Assim que tivermos a posição da transportadora, eles entram em contato com você em até 24 horas úteis.
