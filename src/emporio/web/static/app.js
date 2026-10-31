import { h, render, useEffect, useLayoutEffect, useRef, useState, html } from "/static/vendor/preact-htm.js";
import { Block } from "/static/blocks.js";
import { applyEvent, newBotTurn, turnsFromHistory } from "/static/state.js";

const SUGGESTIONS = [
  "Quais violões até R$ 1000?",
  "Quanto custa o Takamine GD20?",
  "Me arrependi da compra, posso devolver?",
  "Quais promoções vocês têm agora?",
  "Qual o endereço da loja?",
];
const ACTIVITY = {
  search_products: "Procurando no catálogo",
  get_product: "Conferindo o produto",
  list_promotions: "Vendo as promoções",
  quote_purchase: "Calculando o total",
  estimate_shipping: "Vendo o frete",
  catalog_overview: "Olhando as categorias",
  search_policies: "Consultando o manual",
  store_info: "Vendo os dados da loja",
  lookup_order: "Conferindo o pedido",
  check_return: "Avaliando a devolução",
  open_ticket: "Abrindo o chamado",
};
const HISTORY_KEY = "emporio.conversations";
const KEY_KEY = "emporio.byok";
const REVEAL_PER_FRAME = 2;

function read(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key)) ?? fallback;
  } catch {
    return fallback;
  }
}

function write(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* private window */
  }
}

function Prose({ text }) {
  const paragraphs = text.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
  return html`<div class="prose">
    ${paragraphs.map(
      (paragraph) => html`<p>
        ${paragraph.split(/(\*\*[^*]+\*\*)/).map((piece) =>
          piece.startsWith("**") ? html`<strong>${piece.slice(2, -2)}</strong>` : piece,
        )}
      </p>`,
    )}
  </div>`;
}

function useReveal(target, active) {
  const [shown, setShown] = useState(active ? "" : target);
  const targetRef = useRef(target);
  targetRef.current = target;

  useEffect(() => {
    if (!active) {
      setShown(target);
      return undefined;
    }
    let frame;
    const tick = () => {
      setShown((current) => {
        const full = targetRef.current;
        if (!full.startsWith(current)) return full;
        const behind = full.length - current.length;
        if (behind <= 0) return current;
        return full.slice(0, current.length + Math.max(REVEAL_PER_FRAME, Math.ceil(behind / 24)));
      });
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [active]);

  return active ? shown : target;
}

function TextPart({ text, live }) {
  const shown = useReveal(text, live);
  return html`<${Prose} text=${shown} />`;
}

function BotTurn({ turn, live, onAsk }) {
  const lastText = turn.parts.map((p) => p.kind).lastIndexOf("text");
  return html`<div class="turn-bot">
    ${turn.parts.map((part, index) =>
      part.kind === "text"
        ? html`<${TextPart} key=${index} text=${part.text} live=${live && index === lastText} />`
        : html`<${Block} key=${part.id} block=${turn.blocks[part.id]} onAsk=${onAsk} />`,
    )}
    ${live && turn.activity
      ? html`<div class="activity"><span>${ACTIVITY[turn.activity] ?? "Pensando"}</span></div>`
      : null}
  </div>`;
}

function Trace({ turns, onClose }) {
  const end = useRef(null);
  useEffect(() => end.current?.scrollIntoView({ block: "end" }), [turns]);
  return html`<aside class="trace" aria-label="Bastidores">
    <button class="icon-button drawer-close" onClick=${onClose}>Fechar</button>
    <h2>Bastidores</h2>
    <p>O que o Amadeus consultou em cada resposta.</p>
    ${turns.map(
      (turn, index) => html`<div class="trace-turn" key=${index}>
        <div class="trace-q">${turn.question}</div>
        ${turn.trace.map(
          (step) => html`<div class="trace-step ${step.ok === false ? "fail" : ""}">
            <b>${step.name}</b> ${step.ms != null ? html`<small>${step.ms} ms</small>` : null}
            <code>${JSON.stringify(step.args)}</code>
            ${step.search
              ? html`<code>${step.search.modo}: ${step.search.top.map((t) => t.id).join(", ")}</code>`
              : null}
          </div>`,
        )}
        ${turn.guard
          ? html`<div class="trace-guard">Guarda barrou: ${turn.guard.join(", ")}</div>`
          : null}
        <div class="trace-meta">
          ${turn.trace.length ? "" : "Sem consulta. "}${turn.model ?? ""}
        </div>
      </div>`,
    )}
    <div ref=${end}></div>
  </aside>`;
}

function Settings({ current, onSave, onClose, required }) {
  const [provider, setProvider] = useState(current?.provider ?? "gemini");
  const [key, setKey] = useState(current?.key ?? "");
  return html`<div class="scrim" onClick=${(e) => e.target === e.currentTarget && onClose()}>
    <form
      class="dialog"
      onSubmit=${(e) => {
        e.preventDefault();
        onSave(key.trim() ? { provider, key: key.trim() } : null);
      }}
    >
      <h2>Sua chave de API</h2>
      <p>
        ${required
          ? "Este servidor não tem chave própria. Use a sua para conversar, ou abra uma conversa de exemplo."
          : "Opcional. Substitui a chave do servidor."}
        ${" "}Fica só neste navegador.
      </p>
      <label>Provedor
        <select value=${provider} onChange=${(e) => setProvider(e.target.value)}>
          <option value="gemini">Google AI Studio</option>
          <option value="openrouter">OpenRouter</option>
        </select>
      </label>
      <label>Chave
        <input type="password" autocomplete="off" value=${key} onInput=${(e) => setKey(e.target.value)} />
      </label>
      <div class="dialog-actions">
        <button type="button" class="icon-button" onClick=${onClose}>Cancelar</button>
        <button class="primary">Salvar</button>
      </div>
    </form>
  </div>`;
}

function App() {
  const [config, setConfig] = useState(null);
  const [turns, setTurns] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [traceOpen, setTraceOpen] = useState(false);
  const [settings, setSettings] = useState(null);
  const [byok, setByok] = useState(() => read(KEY_KEY, null));
  const [history, setHistory] = useState(() => read(HISTORY_KEY, []));
  const [replaying, setReplaying] = useState(false);
  const [restored, setRestored] = useState(false);
  const canvas = useRef(null);
  const robot = useRef(null);
  const scroller = useRef(null);
  const stick = useRef(true);
  const input = useRef(null);
  const replayToken = useRef(0);

  useEffect(() => {
    fetch("/api/config").then((r) => r.json()).then(setConfig);
    import("/static/robot.js")
      .then(({ Robot }) => {
        const instance = new Robot(canvas.current);
        robot.current = instance;
        return instance.start();
      })
      .catch(() => {
        robot.current = null;
      });
  }, []);

  useEffect(() => {
    if (config && !config.open) robot.current?.setBase("Sitting");
  }, [config]);

  useLayoutEffect(() => {
    const element = scroller.current;
    if (element && stick.current) element.scrollTop = element.scrollHeight;
  });

  useEffect(() => {
    const element = input.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${element.scrollHeight}px`;
  }, [draft]);

  const baseState = () => (config && !config.open ? "Sitting" : "Idle");

  function handleEvent(event) {
    if (event.type === "gesture") {
      if (event.name === "sit") robot.current?.setBase("Sitting");
      else robot.current?.gesture(event.name);
    }
    if (event.type === "tool_start") robot.current?.setBase("Walking");
    if (event.type === "tool_end") robot.current?.setBase(baseState());
    if (event.type === "done") robot.current?.setBase(baseState());
    setTurns((current) => {
      const copy = current.slice();
      copy[copy.length - 1] = applyEvent(copy[copy.length - 1], event);
      return copy;
    });
  }

  async function send(text) {
    const question = text.trim();
    if (!question || busy) return;
    if (config && !config.server_key && !byok) {
      setSettings({ required: true });
      return;
    }
    replayToken.current += 1;
    setReplaying(false);
    stick.current = true;
    setDraft("");
    setBusy(true);
    setRestored(false);
    setTurns((current) => [...current, newBotTurn(question)]);

    let id = conversationId;
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(byok ? { "X-Provider": byok.provider, "X-Api-Key": byok.key } : {}),
        },
        body: JSON.stringify({ conversation_id: id, message: question }),
      });
      if (response.status === 401) {
        setTurns((current) => current.slice(0, -1));
        setSettings({ required: true });
        return;
      }
      if (!response.ok) throw new Error(String(response.status));

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop();
        for (const chunk of chunks) {
          if (!chunk.startsWith("data: ")) continue;
          const event = JSON.parse(chunk.slice(6));
          if (event.type === "conversation") {
            id = event.id;
            setConversationId(id);
            remember(id, question);
          } else {
            handleEvent(event);
          }
        }
      }
    } catch {
      handleEvent({ type: "replace", text: `Não consegui falar com o servidor. Tente de novo ou ligue para ${config?.phone ?? "a loja"}.` });
      handleEvent({ type: "done" });
    } finally {
      setBusy(false);
      input.current?.focus();
    }
  }

  function remember(id, question) {
    setHistory((current) => {
      if (current.some((entry) => entry.id === id)) return current;
      const next = [{ id, title: question }, ...current].slice(0, 30);
      write(HISTORY_KEY, next);
      return next;
    });
  }

  function startNew() {
    replayToken.current += 1;
    setReplaying(false);
    setRestored(false);
    setTurns([]);
    setConversationId(null);
    stick.current = true;
    robot.current?.setBase(baseState());
    input.current?.focus();
  }

  async function open(id) {
    replayToken.current += 1;
    setReplaying(false);
    const response = await fetch(`/api/conversations/${id}`);
    if (!response.ok) {
      setHistory((current) => {
        const next = current.filter((entry) => entry.id !== id);
        write(HISTORY_KEY, next);
        return next;
      });
      return;
    }
    const data = await response.json();
    setRestored(true);
    setTurns(turnsFromHistory(data.turns));
    setConversationId(id);
    stick.current = true;
  }

  async function replay(name) {
    const token = (replayToken.current += 1);
    const data = await (await fetch(`/api/demos/${name}`)).json();
    setRestored(false);
    setConversationId(null);
    setTurns([]);
    setReplaying(true);
    stick.current = true;
    const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    for (const recorded of data.turns) {
      if (token !== replayToken.current) return;
      setTurns((current) => [...current, newBotTurn(recorded.user)]);
      await wait(600);
      for (const event of recorded.events) {
        if (token !== replayToken.current) return;
        handleEvent(event);
        if (event.type === "tool_start") await wait(450);
        else if (event.type === "text") await wait(Math.min(180, 12 * event.text.length));
      }
      await wait(1100);
    }
    if (token === replayToken.current) setReplaying(false);
  }

  const lastIndex = turns.length - 1;
  const liveNow = busy || replaying;
  const empty = turns.length === 0;

  return html`<div class="shell ${traceOpen ? "with-trace" : ""}">
    <aside class="rail">
      <div class="stage"><canvas ref=${canvas} aria-hidden="true"></canvas></div>
      <div class="identity">
        <h1>Amadeus</h1>
        <p>Assistente virtual da Empório da Música</p>
        ${config
          ? html`<div class="status ${config.open ? "" : "closed"}">
              <i></i><span>${config.open ? "Loja aberta" : "Loja fechada"}<span class="more">${config.open ? ` até ${config.closes}` : `, abre ${config.opens}`}</span></span>
            </div>`
          : null}
      </div>
      <button class="new-chat" onClick=${startNew}>Nova conversa</button>
      <nav class="history" aria-label="Conversas">
        ${history.map(
          (entry) => html`<button
            key=${entry.id}
            class=${entry.id === conversationId ? "active" : ""}
            onClick=${() => open(entry.id)}
            title=${entry.title}
          >${entry.title}</button>`,
        )}
      </nav>
      <div class="rail-foot">
        <a class="about" href="https://github.com/Vininic" target="_blank" rel="noreferrer">Vinícius Nicoluci Espíndola</a>
        <button class="icon-button" onClick=${() => setSettings({ required: false })}>Chave</button>
        <button class="icon-button mobile-only" onClick=${() => setTraceOpen(!traceOpen)}>Bastidores</button>
        <button class="icon-button mobile-only" onClick=${startNew} hidden=${empty}>Nova</button>
      </div>
    </aside>

    <main class="chat">
      <button class="icon-button trace-toggle" aria-pressed=${traceOpen} onClick=${() => setTraceOpen(!traceOpen)}>Bastidores</button>
      <div
        class="scroll"
        ref=${scroller}
        onScroll=${(e) => {
          const element = e.currentTarget;
          stick.current = element.scrollHeight - element.scrollTop - element.clientHeight < 80;
        }}
      >
        <div class="thread ${restored ? "instant" : ""}">
          ${empty
            ? html`<section class="empty">
                <h2>Sua música começa aqui.</h2>
                <div class="suggestions">
                  ${SUGGESTIONS.map((s) => html`<button onClick=${() => send(s)}>${s}</button>`)}
                </div>
                ${config?.demos?.length
                  ? html`<div class="demos">
                      Ver conversas gravadas:${" "}
                      ${config.demos.map((d) => html`<button onClick=${() => replay(d.name)}>${d.title}</button>`)}
                    </div>`
                  : null}
              </section>`
            : turns.map(
                (turn, index) => html`
                  <div class="turn-user" key=${`u${index}`}><div>${turn.question}</div></div>
                  <${BotTurn}
                    key=${`b${index}`}
                    turn=${turn}
                    live=${liveNow && index === lastIndex}
                    onAsk=${send}
                  />
                `,
              )}
        </div>
      </div>
      <div class="composer">
        <form onSubmit=${(e) => { e.preventDefault(); send(draft); }}>
          <textarea
            ref=${input}
            rows="1"
            maxlength="1000"
            value=${draft}
            placeholder="Pergunte sobre instrumentos ou pedidos"
            aria-label="Sua mensagem"
            onInput=${(e) => setDraft(e.target.value)}
            onKeyDown=${(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(draft);
              }
            }}
          ></textarea>
          <button class="send" aria-label="Enviar" disabled=${busy || !draft.trim()}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M8 13V3M3.5 7.5 8 3l4.5 4.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
        </form>
        <p class="fineprint">Protótipo com dados fictícios.</p>
      </div>
    </main>

    ${traceOpen ? html`<${Trace} turns=${turns} onClose=${() => setTraceOpen(false)} />` : null}
    ${settings
      ? html`<${Settings}
          current=${byok}
          required=${settings.required}
          onClose=${() => setSettings(null)}
          onSave=${(value) => {
            setByok(value);
            write(KEY_KEY, value);
            setSettings(null);
          }}
        />`
      : null}
  </div>`;
}

render(h(App, null), document.getElementById("app"));
