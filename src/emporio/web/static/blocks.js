import { html, useState } from "/static/vendor/preact-htm.js";

const ORDER_STEPS = [
  ["pending", "Recebido"],
  ["confirmed", "Confirmado"],
  ["shipped", "Enviado"],
  ["delivered", "Entregue"],
];
const VERDICTS = {
  elegivel: ["yes", "Dentro do prazo"],
  nao_elegivel: ["no", "Fora do prazo"],
  precisa_de_informacao: ["ask", "Falta uma informação"],
  encaminhar_equipe: ["ask", "A equipe precisa avaliar"],
  garantia: ["yes", "Coberto pela garantia legal"],
  fabricante: ["ask", "Garantia do fabricante"],
};
const TICKET_KINDS = {
  reclamacao: "Reclamação",
  cancelamento: "Pedido de cancelamento",
  cotacao_frete: "Cotação de frete",
  produto: "Consulta de produto",
  garantia: "Garantia",
  outro: "Atendimento",
};

function Prices({ price }) {
  if (!price) return null;
  const hasPromo = Boolean(price.promocao);
  return html`<div class="prices">
    ${hasPromo
      ? html`<div class="price-was">${price.preco_tabela}<span class="badge">${price.promocao.split(",")[0]}</span></div>`
      : null}
    <div class="price-now">${price.preco_final ?? price.preco_tabela}</div>
    ${price.parcelamento
      ? html`<div class="price-lines">
          ${price.desconto_pix_aplicado ? html`<div>${price.preco_pix} no PIX</div>` : null}
          <div>${price.parcelamento}</div>
        </div>`
      : null}
  </div>`;
}

function ProductCard({ item, solo, onAsk }) {
  const available = item.availability === "disponivel";
  const body = html`
    <div class="kind">${item.category}</div>
    <div class="name">${item.name}</div>
    ${!available ? html`<div class="tag out">${item.availability_label}</div>` : null}
    ${available ? html`<${Prices} price=${item.price} />` : null}
  `;
  const classes = `product ${solo ? "solo" : ""} ${available ? "" : "unavailable"}`;
  if (solo || !available) return html`<div class=${classes}>${body}</div>`;
  return html`<button class=${classes} onClick=${() => onAsk(`Me fala mais do ${item.name}`)}>${body}</button>`;
}

function ProductList({ block, onAsk }) {
  return html`<div>
    ${block.total > block.items.length
      ? html`<div class="rail-note">${block.items.length} de ${block.total} opções</div>`
      : null}
    <div class="rail-scroll" tabindex="0">
      ${block.items.map((item) => html`<${ProductCard} key=${item.id} item=${item} onAsk=${onAsk} />`)}
    </div>
  </div>`;
}

function Copy({ text }) {
  const [copied, setCopied] = useState(false);
  return html`<button
    class="copy"
    onClick=${() => {
      navigator.clipboard?.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }}
  >${copied ? "Copiado" : text}</button>`;
}

function Order({ block }) {
  const cancelled = block.status === "cancelled";
  const reached = ORDER_STEPS.findIndex(([status]) => status === block.status);
  return html`<div class="sheet">
    <h3>Pedido ${block.numero}</h3>
    <div class="sub">${block.data_pedido}, ${block.pagamento}</div>
    ${cancelled
      ? html`<div class="warn">Cancelado${block.observacao ? `: ${block.observacao}` : ""}</div>`
      : html`<ol class="steps">
          ${ORDER_STEPS.map(
            ([, label], index) => html`<li class="${index <= reached ? "done" : ""} ${index === reached ? "current" : ""}">${label}</li>`,
          )}
        </ol>`}
    <dl class="rows">
      ${block.itens.map((item) => html`<dt>Item</dt><dd>${item}</dd>`)}
      ${block.previsao_entrega ? html`<dt>Previsão</dt><dd>${block.previsao_entrega}</dd>` : null}
      ${block.rastreamento ? html`<dt>Rastreio</dt><dd><${Copy} text=${block.rastreamento} /></dd>` : null}
      <dt>Total</dt><dd class="money">${block.total}</dd>
    </dl>
    ${block.atraso_dias ? html`<div class="warn">Entrega atrasada ${block.atraso_dias} dias</div>` : null}
  </div>`;
}

function Return({ block }) {
  const [tone, label] = VERDICTS[block.resultado] ?? ["ask", block.resultado];
  return html`<div class="sheet">
    <div class="verdict ${tone}"><b>${label}</b><span class="sub">Pedido ${block.pedido}</span></div>
    <dl class="rows">
      ${block.prazo_ate ? html`<dt>Prazo até</dt><dd>${block.prazo_ate}</dd>` : null}
      ${block.dias_passados != null ? html`<dt>Dias passados</dt><dd>${block.dias_passados}</dd>` : null}
    </dl>
    ${block.data_base ? html`<div class="sub" style="margin-top:8px">Contado a partir da ${block.data_base}.</div>` : null}
    <div class="cites" style="margin-top:10px">
      ${block.secoes.map((section) => html`<span class="cite">${section}</span>`)}
    </div>
  </div>`;
}

function Quote({ block }) {
  return html`<div class="sheet">
    <h3>Orçamento</h3>
    <dl class="rows">
      ${block.itens.map(
        (item) => html`<dt>${item.quantidade}x ${item.produto}${item.promocao ? ` (${item.promocao.split(",")[0]})` : ""}</dt><dd>${item.preco_final}</dd>`,
      )}
      <dt>Cartão, débito ou boleto</dt><dd>${block.total_cartao_debito_boleto}</dd>
      <dt>PIX</dt><dd class="money">${block.total_pix}</dd>
      <dt>Parcelamento</dt><dd>${block.parcelamento}</dd>
      ${block.frete?.valor_frete ? html`<dt>Frete</dt><dd>${block.frete.valor_frete}</dd>` : null}
      ${block.frete?.opcoes?.map((option) => html`<dt>${option.modalidade}</dt><dd>${option.prazo}</dd>`)}
    </dl>
  </div>`;
}

function Ticket({ block }) {
  return html`<div class="sheet">
    <h3>Chamado ${block.chamado}</h3>
    <div class="sub">${TICKET_KINDS[block.tipo] ?? block.tipo}, retorno ${block.retorno}</div>
    <div style="margin-top:8px;font-size:14px">${block.resumo}</div>
  </div>`;
}

function Store({ block }) {
  return html`<div class="sheet">
    <h3>${block.nome}</h3>
    <dl class="rows">
      <dt>Endereço</dt><dd>${block.endereco}</dd>
      <dt>Telefone</dt><dd>${block.telefone}</dd>
      <dt>E-mail</dt><dd>${block.email}</dd>
      <dt>Horários</dt><dd>${block.horarios}</dd>
    </dl>
  </div>`;
}

function Policy({ block }) {
  return html`<div class="cites">
    ${block.sections.map((section) => html`<span class="cite" key=${section.id}>§${section.id} ${section.title}</span>`)}
  </div>`;
}

export function Block({ block, onAsk }) {
  if (!block) return null;
  const content = {
    product: () => html`<${ProductCard} item=${block} solo onAsk=${onAsk} />`,
    product_list: () => html`<${ProductList} block=${block} onAsk=${onAsk} />`,
    order: () => html`<${Order} block=${block} />`,
    return: () => html`<${Return} block=${block} />`,
    quote: () => html`<${Quote} block=${block} />`,
    ticket: () => html`<${Ticket} block=${block} />`,
    store: () => html`<${Store} block=${block} />`,
    policy: () => html`<${Policy} block=${block} />`,
    closed: () => html`<div class="notice">A equipe volta ${block.abre}. Eu sigo atendendo.</div>`,
  }[block.type];
  return content ? html`<div class="block">${content()}</div>` : null;
}
