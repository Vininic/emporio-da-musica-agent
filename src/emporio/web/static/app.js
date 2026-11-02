import { h, html, render, useEffect, useLayoutEffect, useRef, useState } from "/static/vendor/preact-htm.js";
import { Block, StoreCard } from "/static/blocks.js";
import { STRINGS } from "/static/i18n.js";
import { applyEvent, newTurn, plainText, toMarkdown } from "/static/state.js";
import { Icon, IconButton, Markdown, Toggle, useReveal } from "/static/ui.js";

const REPO_URL = "https://github.com/Vininic/emporio-da-musica-agent";
const STORE = { chats: "emporio.chats", lang: "emporio.lang", byok: "emporio.byok", robot: "emporio.robot", theme: "emporio.theme", prefs: "emporio.prefs" };
const THEMES = ["night", "graphite", "light"];
const EFFORTS = ["low", "medium", "high"];
const LIMITED_MODELS = /3\.(6|8)-flash/;
const MAX_CHATS = 30;
const NARROW = 1180;
const LANGUAGES = [{ value: "pt", label: "PT" }, { value: "en", label: "EN" }];

function load(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key)) ?? fallback;
  } catch {
    return fallback;
  }
}

function save(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    localStorage.removeItem(STORE.chats);
  }
}

function clock(time, lang) {
  return new Intl.DateTimeFormat(lang === "pt" ? "pt-BR" : "en-US", { hour: "2-digit", minute: "2-digit" }).format(time);
}

function newId() {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;
}

function Avatar({ src }) {
  return html`<span class="avatar">
    ${src ? html`<img src=${src} alt="" />` : html`<${Icon} name="music" size=${16} />`}
  </span>`;
}

function TextPart({ text, live }) {
  const shown = useReveal(text, live);
  return html`<${Markdown} text=${shown} caret=${live} />`;
}

function Activity({ name, words }) {
  const [icon, label] = words.activity[name] ?? words.activity.thinking;
  return html`<div class="activity" key=${name}><${Icon} name=${icon} size=${14} /><span>${label}</span></div>`;
}

function Lookups({ turn, words }) {
  const [open, setOpen] = useState(false);
  if (!turn.trace.length) return null;
  return html`<div class="lookups">
    <button type="button" class=${open ? "on" : ""} onClick=${() => setOpen(!open)}>
      <${Icon} name="chevron-right" size=${13} /> ${words.consulted(turn.trace.length)}
    </button>
    ${open
      ? html`<ul>
          ${turn.trace.map((step) => {
            const [icon, label] = words.activity[step.name] ?? ["wrench", step.name];
            return html`<li><${Icon} name=${icon} size=${13} /> ${label}${step.ms != null ? html`<small>${step.ms} ms</small>` : null}</li>`;
          })}
        </ul>`
      : null}
  </div>`;
}

function BotMessage({ turn, live, lang, words, portrait, onAsk, onRegenerate, onRate, canRegenerate }) {
  const [copied, setCopied] = useState(false);
  const lastText = turn.parts.map((part) => part.kind).lastIndexOf("text");
  const streaming = live && !turn.activity;
  return html`<article class="message bot">
    <${Avatar} src=${portrait} />
    <div class="message-body">
      <header><b>Amadeus</b><time>${clock(turn.time, lang)}</time></header>
      <${Lookups} turn=${turn} words=${words} />
      ${turn.parts.map((part, index) =>
        part.kind === "text"
          ? html`<${TextPart} key=${index} text=${part.text} live=${streaming && index === lastText} />`
          : html`<${Block} key=${part.id} block=${turn.blocks[part.id]} lang=${lang} words=${words} onAsk=${onAsk} />`,
      )}
      ${live && turn.activity ? html`<${Activity} name=${turn.activity} words=${words} />` : null}
      ${!live && turn.done
        ? html`<footer class="actions">
            <${IconButton}
              icon=${copied ? "check" : "copy"}
              label=${copied ? words.copied : words.copy}
              onClick=${() => {
                navigator.clipboard?.writeText(plainText(turn));
                setCopied(true);
                setTimeout(() => setCopied(false), 1400);
              }}
            />
            ${canRegenerate ? html`<${IconButton} icon="refresh-cw" label=${words.regenerate} onClick=${onRegenerate} />` : null}
            <${IconButton} icon="thumbs-up" label=${words.good} pressed=${turn.rating === "good"} onClick=${() => onRate("good")} />
            <${IconButton} icon="thumbs-down" label=${words.bad} pressed=${turn.rating === "bad"} onClick=${() => onRate("bad")} />
          </footer>`
        : null}
    </div>
  </article>`;
}

function UserMessage({ turn, words, canEdit, onEdit }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(turn.question);
  return html`<article class="message user">
    <div class="message-body">
      ${editing
        ? html`<form
            class="edit-form"
            onSubmit=${(event) => {
              event.preventDefault();
              setEditing(false);
              onEdit(draft);
            }}
          >
            <textarea rows="2" value=${draft} onInput=${(event) => setDraft(event.target.value)}></textarea>
            <div>
              <button type="button" class="btn ghost" onClick=${() => setEditing(false)}>${words.cancel}</button>
              <button class="btn primary">${words.save}</button>
            </div>
          </form>`
        : html`<div class="user-text">${turn.question}</div>`}
      ${canEdit && !editing
        ? html`<footer class="actions">
            <${IconButton} icon="pencil" label=${words.edit} onClick=${() => setEditing(true)} />
          </footer>`
        : null}
    </div>
  </article>`;
}

function Trace({ turns, words }) {
  const root = useRef(null);
  useEffect(() => {
    const body = root.current?.parentElement;
    if (body) body.scrollTop = body.scrollHeight;
  }, [turns]);
  if (!turns.some((turn) => turn.trace.length || turn.guard)) return html`<p class="side-empty">${words.traceEmpty}</p>`;
  return html`<div class="log" ref=${root}>
    ${turns.map(
      (turn, index) => html`<div class="log-turn" key=${index}>
        <div class="log-question">${turn.question}</div>
        ${turn.trace.map(
          (step) => html`<div class="log-step ${step.ok === false ? "fail" : ""}">
            <div><b>${step.name}</b>${step.ms != null ? html`<small>${step.ms} ms</small>` : null}</div>
            <code>${JSON.stringify(step.args)}</code>
            ${step.search ? html`<code class="hits">${step.search.mode}: ${step.search.top.map((hit) => hit.id).join(", ")}</code>` : null}
          </div>`,
        )}
        ${turn.guard ? html`<div class="log-guard"><${Icon} name="shield-check" size=${13} /> ${words.guardHit}: ${turn.guard.join("; ")}</div>` : null}
        <div class="log-meta">${turn.trace.length ? "" : `${words.noConsult} · `}${turn.model ?? ""}</div>
      </div>`,
    )}
  </div>`;
}

function About({ words }) {
  const body = words.sheetBody;
  return html`<div class="about">
    <p>${body.who}</p>
    <h4>${body.toolsTitle}</h4>
    <ul class="tool-list">${body.tools.map(([icon, label]) => html`<li><${Icon} name=${icon} size=${14} /> ${label}</li>`)}</ul>
    <h4>${body.rulesTitle}</h4>
    <ul class="rule-list">${body.rules.map((rule) => html`<li>${rule}</li>`)}</ul>
    <p class="sub">${body.author}</p>
    <a class="btn" href=${REPO_URL} target="_blank" rel="noreferrer"><${Icon} name="github" size=${14} /> ${body.code}</a>
  </div>`;
}

function ModelMenu({ words, models, defaultModel, prefs, setPrefs }) {
  const [open, setOpen] = useState(false);
  const root = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (event) => {
      if (!root.current?.contains(event.target)) setOpen(false);
    };
    const onKey = (event) => event.key === "Escape" && setOpen(false);
    addEventListener("pointerdown", onDown);
    addEventListener("keydown", onKey);
    return () => {
      removeEventListener("pointerdown", onDown);
      removeEventListener("keydown", onKey);
    };
  }, [open]);

  const current = prefs.model || defaultModel || "";
  return html`<div class="model-menu" ref=${root}>
    <button type="button" class="model-button ${open ? "on" : ""}" aria-expanded=${open} onClick=${() => setOpen(!open)}>
      <span>${current}</span><small>${words.efforts[prefs.effort]}</small><${Icon} name="chevron-down" size=${12} />
    </button>
    ${open
      ? html`<div class="model-pop">
          <h4>${words.modelTitle}</h4>
          ${models.map(
            (name) => html`<button
              type="button"
              class="model-row ${name === current ? "on" : ""}"
              onClick=${() => setPrefs({ ...prefs, model: name === defaultModel ? "" : name })}
            >
              <span><b>${name}</b><small>${name === defaultModel ? words.modelDefault : LIMITED_MODELS.test(name) ? words.modelLimited : ""}</small></span>
              ${name === current ? html`<${Icon} name="check" size=${14} />` : null}
            </button>`,
          )}
          <h4>${words.effortTitle}</h4>
          <${Toggle}
            label=${words.effortTitle}
            value=${prefs.effort}
            onChange=${(effort) => setPrefs({ ...prefs, effort })}
            options=${EFFORTS.map((value) => ({ value, label: words.efforts[value] }))}
          />
        </div>`
      : null}
  </div>`;
}

function Settings({ words, lang, setLang, theme, setTheme, byok, robotOn, setRobotOn, onSave, onClose, required, hasChat, hasChats, onExportChat, onExportAll, onClearAll }) {
  const [tab, setTab] = useState(required ? "key" : "general");
  const [provider, setProvider] = useState(byok?.provider ?? "gemini");
  const [key, setKey] = useState(byok?.key ?? "");
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    const onKey = (event) => event.key === "Escape" && onClose();
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, []);

  const tabs = [["general", "sliders-horizontal"], ["key", "key-round"], ["data", "download"], ["about", "info"]];
  return html`<div class="scrim" onClick=${(event) => event.target === event.currentTarget && onClose()}>
    <div class="dialog" role="dialog" aria-modal="true" aria-label=${words.settings}>
      <header>
        <h2>${words.settings}</h2>
        <${IconButton} icon="x" label=${words.close} onClick=${onClose} />
      </header>
      <div class="dialog-body">
        <nav class="dialog-tabs">
          ${tabs.map(
            ([name, icon]) => html`<button type="button" class=${tab === name ? "on" : ""} onClick=${() => setTab(name)}><${Icon} name=${icon} size=${14} /> ${words.tabs[name]}</button>`,
          )}
        </nav>
        <div class="dialog-pane" key=${tab}>
          ${tab === "general"
            ? html`<div class="setting-row"><span>${words.language}</span><${Toggle} label=${words.language} value=${lang} onChange=${setLang} options=${LANGUAGES} /></div>
                <div class="setting-row"><span>${words.theme}</span><${Toggle} label=${words.theme} value=${theme} onChange=${setTheme} options=${THEMES.map((value) => ({ value, label: words.themes[value] }))} /></div>
                <label class="switch">
                  <input type="checkbox" checked=${robotOn} onChange=${(event) => setRobotOn(event.target.checked)} />
                  <span class="box"><${Icon} name="check" size=${12} /></span>
                  ${words.robotOn}
                </label>`
            : null}
          ${tab === "key"
            ? html`<form
                class="key-form"
                onSubmit=${(event) => {
                  event.preventDefault();
                  onSave(key.trim() ? { provider, key: key.trim() } : null);
                }}
              >
                <p class="sub">${required ? words.apiKeyRequired : words.apiKeyHint}</p>
                <label class="field">${words.provider}
                  <select value=${provider} onChange=${(event) => setProvider(event.target.value)}>
                    <option value="gemini">Google AI Studio</option>
                    <option value="openrouter">OpenRouter</option>
                  </select>
                </label>
                <label class="field">${words.apiKey}
                  <input type="password" autocomplete="off" spellcheck="false" value=${key} onInput=${(event) => setKey(event.target.value)} />
                </label>
                <div class="dialog-actions"><button class="btn primary">${words.saveKey}</button></div>
              </form>`
            : null}
          ${tab === "data"
            ? html`<button type="button" class="data-row" disabled=${!hasChat} onClick=${onExportChat}><${Icon} name="download" size=${15} /><span>${words.exportChat}<small>${words.exportChatHint}</small></span></button>
                <button type="button" class="data-row" disabled=${!hasChats} onClick=${onExportAll}><${Icon} name="download" size=${15} /><span>${words.exportAll}<small>${words.exportAllHint}</small></span></button>
                <button
                  type="button"
                  class="data-row danger"
                  disabled=${!hasChats}
                  onClick=${() => {
                    if (confirming) {
                      onClearAll();
                      setConfirming(false);
                    } else {
                      setConfirming(true);
                    }
                  }}
                ><${Icon} name="trash-2" size=${15} /><span>${confirming ? words.clearConfirm : words.clearAll}<small>${words.clearHint}</small></span></button>`
            : null}
          ${tab === "about" ? html`<${About} words=${words} />` : null}
        </div>
      </div>
    </div>
  </div>`;
}

function ChatRow({ chat, active, words, onOpen, onRename, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(chat.title);
  if (editing) {
    return html`<form
      class="chat-row editing"
      onSubmit=${(event) => {
        event.preventDefault();
        setEditing(false);
        onRename(title.trim() || chat.title);
      }}
    >
      <input autofocus value=${title} onInput=${(event) => setTitle(event.target.value)} onBlur=${() => setEditing(false)} />
    </form>`;
  }
  return html`<div class="chat-row ${active ? "active" : ""}">
    <button type="button" class="chat-open" title=${chat.title} onClick=${onOpen}><span>${chat.title}</span></button>
    <span class="chat-tools">
      <${IconButton} icon="pencil" label=${words.rename} size=${13} onClick=${() => setEditing(true)} />
      <${IconButton} icon="trash-2" label=${words.remove} size=${13} onClick=${onDelete} />
    </span>
  </div>`;
}

function Sidebar({ words, lang, chats, activeId, demos, activeDemo, open, onNew, onOpen, onRename, onDelete, onDemo, onSettings, onClose }) {
  const [query, setQuery] = useState("");
  const shown = chats.filter((chat) => chat.title.toLowerCase().includes(query.toLowerCase()));
  const localDemos = (demos ?? []).filter((demo) => demo.lang === lang);
  return html`<aside class="sidebar ${open ? "open" : ""}">
    <div class="sidebar-inner">
      <div class="sidebar-top">
        <div class="brand"><span class="brand-mark"><${Icon} name="music" size=${14} /></span> ${words.brand}</div>
        <button type="button" class="new-chat" onClick=${onNew}><${Icon} name="plus" size=${15} /> ${words.newChat}</button>
        <label class="search"><${Icon} name="search" size=${14} /><input placeholder=${words.searchChats} aria-label=${words.searchChats} value=${query} onInput=${(event) => setQuery(event.target.value)} /></label>
      </div>
      <div class="sidebar-scroll">
        ${shown.length ? html`<h2>${words.conversations}</h2>` : null}
        ${shown.map(
          (chat) => html`<${ChatRow}
            key=${chat.id}
            chat=${chat}
            active=${chat.id === activeId}
            words=${words}
            onOpen=${() => onOpen(chat.id)}
            onRename=${(title) => onRename(chat.id, title)}
            onDelete=${() => onDelete(chat.id)}
          />`,
        )}
        ${localDemos.length
          ? html`<h2>${words.recorded}</h2>
              ${localDemos.map(
                (demo) => html`<div class="chat-row ${activeDemo === demo.name ? "active" : ""}">
                  <button type="button" class="chat-open" title=${demo.title} onClick=${() => onDemo(demo.name)}>
                    <${Icon} name="play" size=${13} /><span>${demo.title}</span>
                  </button>
                </div>`,
              )}`
          : null}
      </div>
      <footer class="sidebar-foot">
        <button type="button" class="foot-settings" onClick=${onSettings}><${Icon} name="settings" size=${15} /> ${words.settings}</button>
      </footer>
    </div>
    <button type="button" class="drawer-scrim" aria-label=${words.close} tabindex="-1" onClick=${onClose}></button>
  </aside>`;
}

function App() {
  const [config, setConfig] = useState(null);
  const [lang, setLangState] = useState(() => load(STORE.lang, (navigator.language || "pt").startsWith("pt") ? "pt" : "en"));
  const [chats, setChats] = useState(() => load(STORE.chats, []));
  const [activeId, setActiveId] = useState(null);
  const [draftTurns, setDraftTurns] = useState([]);
  const [activeDemo, setActiveDemo] = useState(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(() => innerWidth > 820);
  const [panelOpen, setPanelOpen] = useState(() => innerWidth > NARROW);
  const [panelTab, setPanelTab] = useState("trace");
  const [store, setStore] = useState(null);
  const [theme, setThemeState] = useState(() => load(STORE.theme, "night"));
  const [prefs, setPrefsState] = useState(() => ({ model: "", effort: "low", ...load(STORE.prefs, {}) }));
  const [settings, setSettings] = useState(null);
  const [byok, setByok] = useState(() => load(STORE.byok, null));
  const [robotOn, setRobotOnState] = useState(() => load(STORE.robot, true));
  const [portrait, setPortrait] = useState(null);

  const canvas = useRef(null);
  const robot = useRef(null);
  const composer = useRef(null);
  const composerTop = useRef(null);
  const scroller = useRef(null);
  const stick = useRef(true);
  const textarea = useRef(null);
  const abort = useRef(null);
  const demoToken = useRef(0);

  const words = STRINGS[lang];
  const chat = chats.find((item) => item.id === activeId);
  const turns = activeDemo ? draftTurns : chat?.turns ?? [];
  const empty = turns.length === 0;
  const live = busy || Boolean(activeDemo && draftTurns.at(-1) && !draftTurns.at(-1).done);
  const closeOnNarrow = () => {
    if (innerWidth <= 820) setSidebarOpen(false);
  };

  const setLang = (value) => {
    setLangState(value);
    save(STORE.lang, value);
    document.documentElement.lang = value === "pt" ? "pt-BR" : "en";
  };
  const setTheme = (value) => {
    setThemeState(value);
    save(STORE.theme, value);
  };
  const setPrefs = (value) => {
    setPrefsState(value);
    save(STORE.prefs, value);
  };
  const setRobotOn = (value) => {
    setRobotOnState(value);
    save(STORE.robot, value);
  };

  useEffect(() => {
    document.documentElement.lang = lang === "pt" ? "pt-BR" : "en";
    fetch("/api/config").then((response) => response.json()).then(setConfig);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    if (panelTab === "store") fetch(`/api/store?lang=${lang}`).then((response) => response.json()).then(setStore);
  }, [panelTab, lang]);

  useEffect(() => {
    if (!robotOn || robot.current) return;
    import("/static/robot.js")
      .then(async ({ Robot }) => {
        const instance = new Robot(canvas.current);
        await instance.start();
        robot.current = instance;
        setPortrait(instance.portrait());
      })
      .catch(() => {
        robot.current = null;
      });
  }, [robotOn]);

  useEffect(() => save(STORE.chats, chats.slice(0, MAX_CHATS)), [chats]);

  useLayoutEffect(() => {
    const element = scroller.current;
    if (element && stick.current) element.scrollTop = element.scrollHeight;
  });

  useLayoutEffect(() => {
    const box = composer.current;
    if (!box) return;
    const top = box.getBoundingClientRect().top;
    const before = composerTop.current;
    composerTop.current = top;
    if (before == null || before === top || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    box.animate([{ transform: `translateY(${before - top}px)` }, { transform: "none" }], { duration: 420, easing: "cubic-bezier(0.22, 1, 0.36, 1)" });
  }, [empty]);

  useEffect(() => {
    const element = textarea.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 180)}px`;
  }, [input]);

  function reactRobot(event) {
    const instance = robot.current;
    if (!instance) return;
    if (event.type === "gesture") instance.gesture(event.name);
    else if (event.type === "tool_start") instance.setMood("thinking");
    else if (event.type === "text") instance.setMood("conducting");
    else if (event.type === "done") instance.setMood("idle");
  }

  function updateTurns(id, change) {
    setChats((current) => current.map((item) => (item.id === id ? { ...item, turns: change(item.turns), updated: Date.now() } : item)));
  }

  function applyToLast(id, event) {
    updateTurns(id, (list) => {
      const copy = list.slice();
      copy[copy.length - 1] = applyEvent(copy[copy.length - 1], event);
      return copy;
    });
  }

  async function ask(text, base = null) {
    const question = text.trim();
    if (!question || busy) return;
    if (config && !config.server_key && !byok) {
      setInput(question);
      setSettings({ required: true });
      return;
    }

    demoToken.current += 1;
    setActiveDemo(null);
    setDraftTurns([]);
    stick.current = true;
    setInput("");
    setBusy(true);
    robot.current?.setMood("thinking");

    let id = activeDemo ? null : activeId;
    const previous = base?.turns ?? chats.find((item) => item.id === id)?.turns ?? [];
    const token = base ? base.token : [...previous].reverse().find((item) => item.tokenAfter)?.tokenAfter ?? null;
    const turn = newTurn(question, token);

    if (!id) {
      id = newId();
      setChats((current) => [{ id, title: question.slice(0, 60), lang, turns: [turn], updated: Date.now() }, ...current]);
      setActiveId(id);
    } else {
      updateTurns(id, () => [...previous, turn]);
    }
    closeOnNarrow();

    const controller = new AbortController();
    abort.current = controller;
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        signal: controller.signal,
        headers: {
          "Content-Type": "application/json",
          ...(prefs.model ? { "X-Model": prefs.model } : {}),
          "X-Effort": prefs.effort,
          ...(byok ? { "X-Provider": byok.provider, "X-Api-Key": byok.key } : {}),
        },
        body: JSON.stringify({ state: token, message: question, lang }),
      });
      if (response.status === 401) {
        updateTurns(id, (list) => list.slice(0, -1));
        setSettings({ required: true });
        return;
      }
      if (!response.ok) {
        const message = response.status === 429 ? words.errors.rate : response.status === 400 ? words.errors.expired : words.errors.network;
        applyToLast(id, { type: "replace", text: message });
        applyToLast(id, { type: "done" });
        return;
      }

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
          if (event.type === "lang") setLang(event.lang);
          reactRobot(event);
          applyToLast(id, event);
        }
      }
    } catch (error) {
      if (error.name !== "AbortError") applyToLast(id, { type: "replace", text: words.errors.network });
      applyToLast(id, { type: "done" });
    } finally {
      abort.current = null;
      setBusy(false);
      robot.current?.setMood("idle");
      textarea.current?.focus();
    }
  }

  function resendFrom(index, text) {
    ask(text, { turns: turns.slice(0, index), token: turns[index].tokenBefore });
  }

  function rate(index, value) {
    updateTurns(activeId, (list) => list.map((turn, i) => (i === index ? { ...turn, rating: turn.rating === value ? null : value } : turn)));
  }

  function leaveDemo() {
    demoToken.current += 1;
    setActiveDemo(null);
    setDraftTurns([]);
    stick.current = true;
    robot.current?.setMood("idle");
  }

  function startNew() {
    leaveDemo();
    abort.current?.abort();
    setActiveId(null);
    closeOnNarrow();
    textarea.current?.focus();
  }

  function openChat(id) {
    leaveDemo();
    setActiveId(id);
    closeOnNarrow();
  }

  function deleteChat(id) {
    setChats((current) => current.filter((item) => item.id !== id));
    if (id === activeId) setActiveId(null);
  }

  async function playDemo(name) {
    const token = (demoToken.current += 1);
    const data = await (await fetch(`/api/demos/${name}`)).json();
    setActiveId(null);
    setActiveDemo(name);
    setDraftTurns([]);
    stick.current = true;
    closeOnNarrow();
    const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    await wait(350);
    for (const recorded of data.turns) {
      if (token !== demoToken.current) return;
      setDraftTurns((current) => [...current, newTurn(recorded.user)]);
      robot.current?.setMood("thinking");
      await wait(750);
      for (const event of recorded.events) {
        if (token !== demoToken.current) return;
        reactRobot(event);
        setDraftTurns((current) => {
          const copy = current.slice();
          copy[copy.length - 1] = applyEvent(copy[copy.length - 1], event);
          return copy;
        });
        if (event.type === "tool_start") await wait(500);
        else if (event.type === "text") await wait(Math.min(140, 7 * event.text.length));
      }
      await wait(1300);
    }
  }

  function download(name, content, type) {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([content], { type }));
    link.download = name;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function exportChat() {
    const source = chat ?? { title: "Amadeus", turns };
    download(`${source.title.slice(0, 40).replace(/[^\w-]+/g, "-")}.md`, toMarkdown(source, words.you), "text/markdown");
  }

  function exportAll() {
    const safe = chats.map(({ id, title: name, lang: language, turns: list }) => ({
      id,
      title: name,
      lang: language,
      turns: list.map((turn) => ({ question: turn.question, answer: plainText(turn), time: turn.time, rating: turn.rating })),
    }));
    download("amadeus-chats.json", JSON.stringify(safe, null, 1), "application/json");
  }

  function clearAll() {
    leaveDemo();
    setChats([]);
    setActiveId(null);
  }

  const title = activeDemo ? config?.demos?.find((demo) => demo.name === activeDemo)?.title : chat?.title;
  const lastIndex = turns.length - 1;
  const provider = byok?.provider ?? config?.provider ?? "gemini";

  return html`<div class="shell ${sidebarOpen ? "with-sidebar" : ""} ${panelOpen ? "with-panel" : ""}">
    <${Sidebar}
      words=${words}
      lang=${lang}
      chats=${chats}
      activeId=${activeId}
      demos=${config?.demos}
      activeDemo=${activeDemo}
      open=${sidebarOpen}
      onNew=${startNew}
      onOpen=${openChat}
      onRename=${(id, value) => setChats((current) => current.map((item) => (item.id === id ? { ...item, title: value } : item)))}
      onDelete=${deleteChat}
      onDemo=${playDemo}
      onSettings=${() => setSettings({ required: false })}
      onClose=${() => setSidebarOpen(false)}
    />

    <main class="main ${empty ? "empty" : ""}">
      <header class="topbar">
        <${IconButton} icon="panel-left" label=${words.conversations} pressed=${sidebarOpen} onClick=${() => setSidebarOpen(!sidebarOpen)} />
        <span class="chat-title">${title ?? ""}</span>
        <div class="topbar-tools">
          <${IconButton} icon="panel-right" label=${words.panel} pressed=${panelOpen} onClick=${() => setPanelOpen(!panelOpen)} />
        </div>
      </header>

      <div
        class="scroll"
        ref=${scroller}
        onScroll=${(event) => {
          const element = event.currentTarget;
          stick.current = element.scrollHeight - element.scrollTop - element.clientHeight < 90;
        }}
      >
        <div class="thread">
          ${empty
            ? html`<div class="welcome" key=${lang}><h1>${words.greeting}</h1><p>${words.greetingSub}</p></div>`
            : turns.map(
                (turn, index) => html`
                  <${UserMessage}
                    key=${`u${turn.time}`}
                    turn=${turn}
                    words=${words}
                    canEdit=${!activeDemo && !busy}
                    onEdit=${(text) => resendFrom(index, text)}
                  />
                  <${BotMessage}
                    key=${`b${turn.time}`}
                    turn=${turn}
                    live=${live && index === lastIndex}
                    lang=${lang}
                    words=${words}
                    portrait=${portrait}
                    onAsk=${ask}
                    canRegenerate=${!activeDemo && !busy && index === lastIndex}
                    onRegenerate=${() => resendFrom(index, turn.question)}
                    onRate=${(value) => (activeDemo ? null : rate(index, value))}
                  />
                `,
              )}
        </div>
      </div>

      <div class="composer-wrap">
        <form
          class="composer"
          ref=${composer}
          onSubmit=${(event) => {
            event.preventDefault();
            ask(input);
          }}
        >
          <textarea
            ref=${textarea}
            rows="1"
            maxlength="1000"
            value=${input}
            placeholder=${words.placeholder}
            aria-label=${words.placeholder}
            onInput=${(event) => setInput(event.target.value)}
            onKeyDown=${(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                ask(input);
              }
            }}
          ></textarea>
          <div class="composer-bar">
            <${ModelMenu} words=${words} models=${config?.models?.[provider] ?? []} defaultModel=${config?.model} prefs=${prefs} setPrefs=${setPrefs} />
            ${input.length > 800 ? html`<span class="counter">${input.length}/1000</span>` : null}
            ${busy
              ? html`<button type="button" class="send stop" aria-label=${words.stop} title=${words.stop} onClick=${() => abort.current?.abort()}><${Icon} name="square" size=${13} /></button>`
              : html`<button class="send" aria-label=${words.send} title=${words.send} disabled=${!input.trim()}><${Icon} name="arrow-up" size=${16} /></button>`}
          </div>
        </form>
        ${empty
          ? html`<div class="starters" key=${lang}>
              ${words.prompts.map(
                ([icon, label, prompt], index) => html`<button type="button" class="starter" style=${`animation-delay:${0.04 + index * 0.04}s`} onClick=${() => ask(prompt)}>
                  <${Icon} name=${icon} size=${14} /><span>${label}</span>
                </button>`,
              )}
            </div>`
          : html`<p class="fineprint">${words.prototype}</p>`}
      </div>
    </main>

    <aside class="panel ${panelOpen ? "open" : ""}">
      <div class="panel-inner">
        <div class="stage ${robotOn ? "" : "off"}">
          <canvas ref=${canvas}></canvas>
        </div>
        <div class="identity">
          <div><b>Amadeus</b><span>${words.role}</span></div>
          ${config
            ? html`<span class="status ${config.open ? "live" : ""}" title=${config.open ? `${words.openUntil} ${config.closes}` : `${words.opens} ${config.opens[lang]}`}><i></i>${config.open ? words.open : words.closed}</span>`
            : null}
        </div>
        <div class="panel-tabs">
          <${Toggle}
            label=${words.panel}
            value=${panelTab}
            onChange=${setPanelTab}
            options=${[{ value: "trace", label: words.trace }, { value: "store", label: words.storeTab }]}
          />
          <span class="panel-close"><${IconButton} icon="x" label=${words.close} onClick=${() => setPanelOpen(false)} /></span>
        </div>
        <div class="panel-body">
          ${panelTab === "trace"
            ? html`<${Trace} turns=${turns} words=${words} />`
            : store
              ? html`<${StoreCard} block=${store} lang=${lang} words=${words.block} />`
              : null}
        </div>
      </div>
    </aside>

    ${settings
      ? html`<${Settings}
          words=${words}
          lang=${lang}
          setLang=${setLang}
          theme=${theme}
          setTheme=${setTheme}
          byok=${byok}
          robotOn=${robotOn}
          setRobotOn=${setRobotOn}
          required=${settings.required}
          hasChat=${turns.length > 0}
          hasChats=${chats.length > 0}
          onExportChat=${exportChat}
          onExportAll=${exportAll}
          onClearAll=${clearAll}
          onClose=${() => setSettings(null)}
          onSave=${(value) => {
            setByok(value);
            save(STORE.byok, value);
            setSettings(null);
          }}
        />`
      : null}
  </div>`;
}

render(h(App, null), document.getElementById("app"));
