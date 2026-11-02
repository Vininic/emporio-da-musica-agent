import { html, useEffect, useRef, useState } from "/static/vendor/preact-htm.js";
import { ICONS } from "/static/vendor/lucide.js";

export function Icon({ name, size = 15, class: className = "" }) {
  return html`<svg
    class="icon ${className}"
    width=${size}
    height=${size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    dangerouslySetInnerHTML=${{ __html: ICONS[name] ?? "" }}
  ></svg>`;
}

export function IconButton({ icon, label, onClick, pressed, class: className = "", size = 15 }) {
  return html`<button
    type="button"
    class="icon-button ${className}"
    title=${label}
    aria-label=${label}
    aria-pressed=${pressed}
    onClick=${onClick}
  ><${Icon} name=${icon} size=${size} /></button>`;
}

export function Card({ icon, title, aside, children }) {
  return html`<section class="card">
    <header class="card-head"><${Icon} name=${icon} size=${14} /><span>${title}</span>${aside ? html`<span class="card-aside">${aside}</span>` : null}</header>
    <div class="card-body">${children}</div>
  </section>`;
}

export function Toggle({ options, value, onChange, label }) {
  const index = options.findIndex((option) => option.value === value);
  return html`<div class="seg" role="group" aria-label=${label} style=${`--count:${options.length}`}>
    <span class="seg-slide" style=${`transform:translateX(${index * 100}%)`}></span>
    ${options.map(
      (option) => html`<button
        type="button"
        class=${option.value === value ? "on" : ""}
        aria-pressed=${option.value === value}
        onClick=${() => onChange(option.value)}
      >${option.label}</button>`,
    )}
  </div>`;
}

export function Meter({ share, over = false }) {
  return html`<span class="meter ${over ? "over" : ""}" aria-hidden="true"><i style=${`width:${Math.min(100, Math.round(share * 100))}%`}></i></span>`;
}

function inline(text) {
  const parts = [];
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    const token = match[0];
    parts.push(token.startsWith("**") ? html`<strong>${token.slice(2, -2)}</strong>` : html`<code>${token.slice(1, -1)}</code>`);
    last = match.index + token.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export function Markdown({ text, caret = false }) {
  const paragraphs = text.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
  const nodes = paragraphs.map((paragraph, index) => {
    const lines = paragraph.split("\n");
    const end = caret && index === paragraphs.length - 1 ? html`<span class="caret"></span>` : null;
    if (lines.every((line) => /^\s*([-*]|\d+\.)\s/.test(line))) {
      return html`<ul>${lines.map((line) => html`<li>${inline(line.replace(/^\s*([-*]|\d+\.)\s/, ""))}</li>`)}${end}</ul>`;
    }
    return html`<p>${lines.map((line, i) => html`${i ? html`<br />` : null}${inline(line)}`)}${end}</p>`;
  });
  return html`<div class="prose">${nodes.length ? nodes : caret ? html`<p><span class="caret"></span></p>` : null}</div>`;
}

export function useReveal(target, active) {
  const [shown, setShown] = useState(active ? "" : target);
  const latest = useRef(target);
  latest.current = target;

  useEffect(() => {
    if (!active) return undefined;
    let frame;
    let last = performance.now();
    const tick = (now) => {
      const elapsed = now - last;
      last = now;
      setShown((current) => {
        const full = latest.current;
        if (!full.startsWith(current)) return full;
        const behind = full.length - current.length;
        if (behind <= 0) return current;
        const rate = Math.max(70, behind * 2.4);
        return full.slice(0, current.length + Math.max(1, Math.round((rate * elapsed) / 1000)));
      });
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [active]);

  return active ? shown : target;
}
