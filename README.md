# Empório da Música agent

Customer service agent prototype for a fictional instrument store in Campo Grande, Brazil. Technical case for Artefact, AI Engineer.

Amadeus answers in Portuguese or English. It searches the catalog, quotes prices, checks orders after verifying identity, explains store policy, gives the store's hours and location, and opens tickets for the team.

- Live: https://emporio-da-musica.vercel.app
- Example conversations: [docs/conversations](docs/conversations)
- Why it is built this way: [vault/Home.md](vault/Home.md)

## Run it

Needs Python 3.11 or newer and a [Google AI Studio](https://aistudio.google.com/apikey) key.

```bash
python -m venv .venv
.venv/Scripts/activate        # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # then set GEMINI_API_KEY; STATE_SECRET is only required on Vercel
uvicorn --factory emporio.web.app:create_app --port 8000
```

Open http://localhost:8000. With no key in `.env`, the settings panel asks for one and keeps it in your browser only.

```bash
pytest                                                  # no key needed
python -m evals.run --model gemini-3.1-flash-lite       # live, writes to evals/HISTORY.md
```

## How it works

```
browser ── SSE ── FastAPI ── agent loop ── LLM (Gemini, OpenRouter)
                                 │
                                 ├─ tools ─ deterministic core ─ SQLite (from the CSVs)
                                 ├─ hybrid retrieval ─ BM25 + vectors, on catalog and manual
                                 └─ guard ─ checks the answer against what the tools returned
```

The model chooses tools and writes prose. It never computes a price, a date or an eligibility, and never writes SQL.

## Decisions

| Decision | Why | What breaks without it |
|---|---|---|
| Python computes prices, installments, hours, shipping and returns | The data has traps: expired promotions, tiers that differ from the manual's examples, contradictions. See [traps](vault/traps.md) | The model invents plausible prices |
| Fixed parameterized queries, no text-to-SQL | Customer data sits in the same database | Prompt injection reaches other customers' data |
| Identity gate in code: order number and phone, the phone must come from the customer, with limits per session and per order | A rule in a prompt can be talked around | "Sou primo dele" works |
| Hybrid retrieval: BM25 and vectors with rank fusion | "Violão de som quente" needs vectors; "GD20" needs keywords. [Decision 001](vault/decisions/001-hybrid-retrieval.md) | One kind of query always fails |
| Guard on every answer | Checks money, percentages, phones and e-mails against tool output, and rejects "I opened a ticket" when no ticket was opened. One correction round, then a safe fallback | A wrong number reaches the customer |
| Blocks rendered from tool output | The price on a card comes from the tool, not from model text | A card can disagree with the system |
| No agent framework | The loop is under 300 lines and is the thing being evaluated | Nothing; a framework would only hide it |
| Stateless server with a signed conversation token | Serverless instances share nothing, and the token is HMAC-signed, so a client cannot edit its verified identity | Conversations break between instances |
| Evals as code | Every trap has a case, and every full run is kept in [evals/HISTORY.md](evals/HISTORY.md), failures included | Prompt changes are judged by feel |
| Default to `gemini-3.5-flash-lite`, falling through to `3.1-flash-lite` | Measured, not assumed: newer models allow 20 requests a day on the free tier. [Decision 003](vault/decisions/003-providers.md) | A demo dies after a few conversations |
| Each message sets the language, by counting common words | A customer writing English in a Portuguese session should get English, with no LLM call to find that out | A setting nobody opens decides the answer's language |
| No build step: Preact and htm from a vendored file | One command to run; Python stays the main language. [Decision 004](vault/decisions/004-simple.md) | Node becomes a dependency |

## Results

57 live cases cover every trap in [vault/traps.md](vault/traps.md), in Portuguese and English. Results on `gemini-3.5-flash-lite` at low reasoning effort, from [evals/HISTORY.md](evals/HISTORY.md):

| Run | Passed | Note |
|---|---|---|
| 1 | 50/55 | First run with English cases. Found a marker leaking into text, an order card going missing, and a discontinued model described as never sold |
| 2 | 49/55 | After those fixes. Same code can vary between runs, since the model is not deterministic |
| 3 | 55/55 | After prompt fixes, and after seven cases were adjusted: four rejected correct phrasing, two named one tool where the outcome is what matters, and one counted a call rejected for lacking a phone |
| 4 | 51/57 on `gemini-3.1-flash-lite` | After the independent review added two cases. The default model had run out of daily quota, so this ran on the fallback, which is weaker: it asked for an order number instead of opening a complaint ticket, and stated there are no branches without a source. Two of its six failures were cases stricter than their purpose, since relaxed |

Median time to first token was about 1.9 s, and a full turn about 2.1 s, excluding rate-limit waits. There are also 181 offline tests with no API key needed.

The same assistant wrote the cases and the code, so this score shows the agent does what its author checked, not that it is safe. [vault/reviews](vault/reviews) holds an independent attack by a separate agent, with the state of each finding. It found 23 problems that a perfect score had not, including a way to get a false price past the guard.

## Known limitations

- **Lite model.** Facts hold because of tools and the guard, but the prose is less graceful than a larger model's, and behavior varies between runs: the same suite scored 49 and 55. It sometimes opens a ticket for a late order before the customer asks, as in one recorded conversation.
- **Product images.** A script found them by web search and they were reviewed by eye. They are third-party thumbnails linked from the search engine's cache, fine for a prototype and not for production, where the store would use its own photos. 40 of 65 products have an exact match; the other 25 show a picture of the same type of instrument, tagged as illustrative.
- **Store address.** The manual's street does not appear on OpenStreetMap, so the map shows the city center with no pin.
- **Language detection.** It counts common words, so a short or mixed message keeps the current language.
- **Provider limits.** The public site runs on a free-tier key. Three eval runs and the review used up the default model's daily quota, and the chain then falls to a weaker model. If that runs out too, the agent says so and gives the store's phone number. A visitor can use their own key in settings.
- **Limits per instance.** The rate limit and the per-order lockout are in memory, so on serverless they slow abuse and do not stop it. Production needs a shared store.
- **Guard coverage.** It catches invented numbers and unbacked actions. A value from any tool result passes even when attached to the wrong product, foreign currency and day counts are not checked, and a wrong statement with no number can pass. Evals are the defense there.
- **Streaming comes first.** Text streams as it arrives and the guard runs afterward, so a rejected answer can be on screen for a moment before it is replaced. Holding text back would remove streaming, and I chose to keep it for a prototype.
- **Readable state token.** It is signed, not encrypted, and it expires in 24 hours. It holds the customer's own conversation in their own browser.
- **Identity by order and phone.** Enough for a prototype, weak for production: anyone holding both passes.
- **Tickets are local.** They go to SQLite (`/tmp` on Vercel, so they vanish with the instance) and nobody receives them.
- **Snapshot clock.** The data stops in March 2026, so "today" is pinned to 2026-03-25 with the real time of day. See [decision 006](vault/decisions/006-clock.md).
- **Prompt injection.** Tools limit the damage, since no tool can return another customer's data. The model can still be made to say odd things without numbers.

## Next steps

1. Real ticket delivery and order status from a live system, replacing the CSV snapshot.
2. Traces and cost per conversation in an observability tool, with the eval suite running in CI against a paid key.
3. Stronger identity: a one-time code to the phone on file.
4. Human handoff inside the chat, with the conversation attached to the ticket.
5. A store-managed knowledge base, so the manual's contradictions get fixed at the source.

## How coding assistants were used

Claude Code (desktop app) wrote nearly all the code and documents. I directed the project, made the product and identity decisions, reviewed the results and rejected what was not good enough.

The workflow is in [vault/workflow.md](vault/workflow.md):

1. Audit the data by script before any agent exists.
2. Write decisions down first, with who decided.
3. Turn each trap into an eval case, then write the code.
4. Keep rules for the assistant in [CLAUDE.md](CLAUDE.md), versioned with the code.
5. Have a second agent, with no shared context, attack the result.

[vault/ai-log.md](vault/ai-log.md) records what actually happened, including what went wrong:

- I overruled the assistant on vector search, on the agent's name and on keeping a key on the public site.
- I rejected two interface drafts before accepting a direction, and from then on interface work came to me as screenshots before it entered the history.
- The assistant stated two false causes for a robot animation bug before measuring the real one, and claimed a fallback provider worked without testing it.
- Evals caught the agent inventing an explanation for a missing discount, and caught the assistant's own bad tests.
- A contact sheet caught wrong product images that the matching rule had let through.

## Credits

Robot: [RobotExpressive](src/emporio/web/static/assets/CREDITS.md) by Tomás Laulhé, CC0, with a conductor skin added in code. Icons: Lucide. 3D: three.js.
