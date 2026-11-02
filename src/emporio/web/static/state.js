export function newTurn(question, tokenBefore = null) {
  return {
    question,
    tokenBefore,
    tokenAfter: null,
    time: Date.now(),
    parts: [],
    blocks: {},
    trace: [],
    activity: "thinking",
    guard: null,
    model: null,
    done: false,
    rating: null,
    failed: false,
  };
}

function addText(parts, text) {
  const last = parts[parts.length - 1];
  if (last?.kind === "text") {
    return [...parts.slice(0, -1), { kind: "text", text: last.text + text }];
  }
  return [...parts, { kind: "text", text }];
}

function addBlock(parts, id) {
  if (parts.some((part) => part.kind === "block" && part.id === id)) return parts;
  return [...parts, { kind: "block", id }];
}

export function applyEvent(turn, event) {
  switch (event.type) {
    case "text":
      return { ...turn, activity: null, parts: addText(turn.parts, event.text) };
    case "tool_start":
      return {
        ...turn,
        activity: event.name,
        trace: [...turn.trace, { call: event.call, name: event.name, args: event.args }],
      };
    case "tool_end":
      return {
        ...turn,
        activity: "thinking",
        trace: turn.trace.map((step) =>
          step.call === event.call
            ? { ...step, ms: event.ms, ok: event.ok, search: event.search }
            : step,
        ),
      };
    case "block":
      return {
        ...turn,
        blocks: { ...turn.blocks, [event.id]: event.block },
        parts: event.id === "closed" ? addBlock(turn.parts, event.id) : turn.parts,
      };
    case "block_ref":
      return turn.blocks[event.id] ? { ...turn, parts: addBlock(turn.parts, event.id) } : turn;
    case "replace":
      return {
        ...turn,
        activity: null,
        parts: [
          ...turn.parts.filter((part) => part.kind === "block" && part.id === "closed"),
          { kind: "text", text: event.text },
        ],
      };
    case "guard":
      return { ...turn, guard: event.problems };
    case "provider_error":
      return { ...turn, failed: true };
    case "model":
      return { ...turn, model: event.name };
    case "state":
      return { ...turn, tokenAfter: event.token };
    case "done":
      return { ...turn, activity: null, done: true, model: event.model ?? turn.model };
    default:
      return turn;
  }
}

export function plainText(turn) {
  return turn.parts
    .filter((part) => part.kind === "text")
    .map((part) => part.text.trim())
    .join("\n\n");
}

export function toMarkdown(conversation, labelYou) {
  const lines = [`# ${conversation.title}`, ""];
  for (const turn of conversation.turns) {
    lines.push(`**${labelYou}:** ${turn.question}`, "", `**Amadeus:** ${plainText(turn)}`, "");
  }
  return lines.join("\n");
}
