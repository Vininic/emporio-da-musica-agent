import { html, useState } from "/static/vendor/preact-htm.js";
import { day, money } from "/static/i18n.js";
import { Card, Icon, Meter } from "/static/ui.js";

const CATEGORY_ICONS = { 1: "guitar", 2: "guitar", 3: "drum", 4: "piano", 5: "guitar", 6: "wind", 7: "wind", 8: "music", 9: "guitar" };
const ORDER_FLOW = ["pending", "confirmed", "shipped", "delivered"];
const VERDICT_TONE = { elegivel: "good", garantia: "good", nao_elegivel: "bad", precisa_de_informacao: "warn", encaminhar_equipe: "warn", fabricante: "warn" };
const VERDICT_ICON = { elegivel: "badge-check", garantia: "shield-check", nao_elegivel: "circle-alert", precisa_de_informacao: "info", encaminhar_equipe: "ticket", fabricante: "shield-check" };
const WINDOW_DAYS = { regret: 7, store_purchase: 7, preference: 7, defect_exchange: 30, defect_legal: 90 };

function windowFor(code) {
  if (code.startsWith("regret")) return WINDOW_DAYS.regret;
  if (code.startsWith("store_purchase")) return WINDOW_DAYS.store_purchase;
  if (code.startsWith("preference")) return WINDOW_DAYS.preference;
  if (code === "defect_exchange_window") return WINDOW_DAYS.defect_exchange;
  if (code === "defect_legal_warranty") return WINDOW_DAYS.defect_legal;
  return null;
}

function Price({ price, lang, words }) {
  const promo = price.promo_percent != null;
  return html`<div class="price">
    ${promo ? html`<div class="price-was"><s>${money(price.list, lang)}</s><span class="promo">-${price.promo_percent}%</span></div>` : null}
    <div class="price-now">${money(price.final, lang)}</div>
    <div class="price-lines">
      ${price.pix_applies ? html`<div><${Icon} name="qr-code" size=${12} /> ${money(price.pix, lang)} ${words.pix}</div>` : null}
      <div><${Icon} name="credit-card" size=${12} /> ${words.installments(price.count, money(price.each, lang))}</div>
    </div>
  </div>`;
}

function ProductImage({ item, words }) {
  const [failed, setFailed] = useState(false);
  const icon = CATEGORY_ICONS[item.category_id] ?? "music";
  if (!item.image || failed) return html`<div class="product-image empty"><${Icon} name=${icon} size=${26} /></div>`;
  return html`<div class="product-image">
    <img src=${item.image.url} alt=${item.name} title=${words.imageSource} loading="lazy" referrerpolicy="no-referrer" onError=${() => setFailed(true)} />
  </div>`;
}

function ProductCard({ item, lang, words, onAsk, solo = false }) {
  const available = item.availability === "disponivel";
  const low = available && item.stock <= 3;
  return html`<article class="product ${available ? "" : "unavailable"} ${solo ? "solo" : ""}">
    <${ProductImage} item=${item} words=${words} />
    <div class="product-top">
      <span class="product-category">${item.category}</span>
      ${low ? html`<span class="low">${words.lastUnits(item.stock)}</span>` : null}
    </div>
    <h4>${item.name}</h4>
    ${available
      ? html`<${Price} price=${item.price} lang=${lang} words=${words} />`
      : html`<div class="unavailable-note"><${Icon} name="circle-alert" size=${13} /> ${words.availability[item.availability]}</div>`}
    ${solo && item.specs
      ? html`<dl class="specs">${Object.entries(item.specs).map(([key, value]) => html`<dt>${key}</dt><dd>${value}</dd>`)}</dl>`
      : null}
    ${available && !solo
      ? html`<div class="product-actions">
          <button type="button" class="btn" onClick=${() => onAsk(words.askDetails(item.name))}>${words.details}</button>
          <button type="button" class="btn" onClick=${() => onAsk(words.askQuote(item.name))}>${words.quote}</button>
        </div>`
      : null}
    ${available && solo
      ? html`<div class="product-actions">
          <button type="button" class="btn" onClick=${() => onAsk(words.askQuote(item.name))}><${Icon} name="receipt" size=${13} /> ${words.quote}</button>
          <span class="stock-note">${words.inStock(item.stock)}</span>
        </div>`
      : null}
  </article>`;
}

function ProductList({ block, lang, words, onAsk }) {
  return html`<div class="product-list">
    <div class="list-note">${words.options(block.items.length, block.total)}</div>
    <div class="product-rail" tabindex="0">
      ${block.items.map((item) => html`<${ProductCard} key=${item.id} item=${item} lang=${lang} words=${words} onAsk=${onAsk} />`)}
    </div>
  </div>`;
}

function Copyable({ text }) {
  const [done, setDone] = useState(false);
  return html`<button
    type="button"
    class="copyable"
    onClick=${() => {
      navigator.clipboard?.writeText(text);
      setDone(true);
      setTimeout(() => setDone(false), 1400);
    }}
  >${text} <${Icon} name=${done ? "check" : "copy"} size=${12} /></button>`;
}

function Order({ block, lang, words }) {
  const cancelled = block.status === "cancelled";
  const reached = ORDER_FLOW.indexOf(block.status);
  const payment = block.payment.startsWith("credit_") ? words.credit(block.payment.slice(7)) : words.paymentNames[block.payment] ?? block.payment;
  return html`<${Card} icon="package" title=${`${words.order} #${block.number}`}>
    ${cancelled
      ? html`<div class="note bad"><${Icon} name="circle-alert" size=${14} /> ${words.cancelled}${block.note ? `: ${block.note}` : ""}</div>`
      : html`<ol class="steps">
          ${words.steps.map(
            ([icon, label], index) => html`<li class="${index <= reached ? "done" : ""} ${index === reached ? "current" : ""}">
              <span><${Icon} name=${icon} size=${14} /></span>${label}
            </li>`,
          )}
        </ol>`}
    <dl class="rows">
      ${block.items.map((item) => html`<dt>${words.item}</dt><dd>${item}</dd>`)}
      <dt>${words.payment}</dt><dd>${payment}</dd>
      ${block.eta ? html`<dt>${words.eta}</dt><dd>${day(block.eta, lang)}</dd>` : null}
      ${block.tracking ? html`<dt>${words.tracking}</dt><dd><${Copyable} text=${block.tracking} /></dd>` : null}
      <dt>${words.total}</dt><dd class="strong">${money(block.total, lang)}</dd>
    </dl>
    ${block.days_late ? html`<div class="note warn"><${Icon} name="clock" size=${14} /> ${words.late(block.days_late)}</div>` : null}
  <//>`;
}

function Return({ block, lang, words }) {
  const limit = windowFor(block.code);
  const tone = VERDICT_TONE[block.outcome] ?? "warn";
  return html`<${Card} icon="undo-2" title=${`${words.returnTitle} #${block.order}`}>
    <div class="verdict ${tone}"><${Icon} name=${VERDICT_ICON[block.outcome] ?? "info"} size=${16} /> ${words.verdicts[block.outcome]}</div>
    <dl class="rows">
      ${block.deadline ? html`<dt>${words.deadline}</dt><dd>${day(block.deadline, lang)}</dd>` : null}
      ${block.days_passed != null ? html`<dt>${words.daysPassed}</dt><dd>${block.days_passed}${limit ? ` / ${limit}` : ""}</dd>` : null}
    </dl>
    ${limit && block.days_passed != null
      ? html`<${Meter} share=${block.days_passed / limit} over=${block.days_passed > limit} />`
      : null}
    ${block.estimated ? html`<p class="sub">${words.estimated}</p>` : null}
  <//>`;
}

function Quote({ block, lang, words }) {
  const shipping = block.shipping;
  const cost = shipping ? (shipping.fee === 0 ? words.free : shipping.fee ? money(shipping.fee, lang) : words.shippingQuote) : null;
  return html`<${Card} icon="receipt" title=${words.quoteTitle}>
    <dl class="receipt">
      ${block.lines.map(
        (line) => html`<dt>${line.quantity}x ${line.name}${line.promo_percent ? html` <span class="promo">-${line.promo_percent}%</span>` : null}</dt><dd>${money(line.final, lang)}</dd>`,
      )}
      ${shipping ? html`<dt>${words.shipping} (${shipping.city})</dt><dd>${cost}</dd>` : null}
    </dl>
    <dl class="rows totals">
      <dt>${words.cardTotal}</dt><dd>${money(block.final, lang)}</dd>
      <dt>${words.split}</dt><dd>${words.installments(block.count, money(block.each, lang))}</dd>
      <dt>${words.pixTotal}</dt><dd class="strong">${money(block.pix, lang)}</dd>
    </dl>
  <//>`;
}

function Ticket({ block, words }) {
  return html`<${Card} icon="ticket" title=${`${words.ticket} #${block.ticket}`}>
    <div class="verdict good"><${Icon} name="ticket" size=${16} /> ${words.ticketKinds[block.kind] ?? block.kind}</div>
    <p class="ticket-summary">${block.summary}</p>
    <p class="sub"><${Icon} name="clock" size=${12} /> ${words.response}</p>
  <//>`;
}

export function StoreCard({ block, lang, words }) {
  const { lat, lon } = block.map;
  const box = `${lon - 0.007},${lat - 0.004},${lon + 0.007},${lat + 0.004}`;
  const directions = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(block.address)}`;
  return html`<div class="store-card">
    <div class="verdict ${block.open_now ? "good" : "warn"}">
      <${Icon} name="clock" size=${15} /> ${block.open_now ? words.openNow : words.closedNow}
      ${block.opens ? html`<span class="verdict-note">${words.opensAt(block.opens)}</span>` : null}
    </div>
    <dl class="rows week">
      ${block.schedule.map(
        (row) => html`<dt class=${row.today ? "today" : ""}>${row.day}</dt><dd class=${row.today ? "today" : ""}>${row.opens ? `${row.opens} - ${row.closes}` : words.closedDay}</dd>`,
      )}
    </dl>
    <p class="sub">${words.holidays}: ${block.holidays.map((iso) => day(iso, lang)).join(", ")}</p>
    <ul class="contact">
      <li><${Icon} name="map-pin" size=${14} /> ${block.address}</li>
      <li><${Icon} name="phone" size=${14} /> <a href=${`tel:${block.phone.replace(/\D/g, "")}`}>${block.phone}</a></li>
      <li><${Icon} name="mail" size=${14} /> <a href=${`mailto:${block.email}`}>${block.email}</a></li>
    </ul>
    <iframe class="store-map" title=${words.mapNote} loading="lazy" referrerpolicy="no-referrer" src=${`https://www.openstreetmap.org/export/embed.html?bbox=${box}&layer=mapnik`}></iframe>
    <div class="map-foot">
      <span>${words.mapNote}</span>
      <a class="btn" href=${directions} target="_blank" rel="noreferrer"><${Icon} name="map-pin" size=${13} /> ${words.directions}</a>
    </div>
  </div>`;
}

function Store({ block, lang, words }) {
  return html`<${Card} icon="store" title=${words.store}><${StoreCard} block=${block} lang=${lang} words=${words} /><//>`;
}

function Policy({ block, words }) {
  const [open, setOpen] = useState(null);
  const section = block.sections.find((item) => item.id === open);
  return html`<div class="sources">
    <div class="source-chips">
      <span class="source-label"><${Icon} name="book-open" size=${13} /> ${words.source}</span>
      ${block.sections.map(
        (item) => html`<button type="button" class="chip ${open === item.id ? "on" : ""}" onClick=${() => setOpen(open === item.id ? null : item.id)}>${item.title}<${Icon} name="chevron-down" size=${12} /></button>`,
      )}
    </div>
    ${section ? html`<blockquote>${section.text}</blockquote>` : null}
  </div>`;
}

export function Block({ block, lang, words, onAsk }) {
  if (!block) return null;
  const props = { block, lang, words: words.block, onAsk };
  const views = {
    product: () => html`<${ProductCard} item=${block} lang=${lang} words=${words.block} onAsk=${onAsk} solo />`,
    product_list: () => html`<${ProductList} ...${props} />`,
    order: () => html`<${Order} ...${props} />`,
    return: () => html`<${Return} ...${props} />`,
    quote: () => html`<${Quote} ...${props} />`,
    ticket: () => html`<${Ticket} ...${props} />`,
    store: () => html`<${Store} ...${props} />`,
    policy: () => html`<${Policy} ...${props} />`,
    closed: () => html`<div class="notice"><${Icon} name="moon" size=${14} /> ${words.block.closedNotice(block.opens)}</div>`,
  };
  const view = views[block.type];
  return view ? html`<div class="block">${view()}</div>` : null;
}
