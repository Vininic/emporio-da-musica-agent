# AI log

Only what actually happened. Tool: Claude Code (desktop app). Newest last.

## 2026-10-31

**Vector RAG: assistant overruled.** The assistant recommended skipping vector search because the manual is 8 pages. The author: "Também há necessidade de ter RAG no currículo e portfólio. Já fica." Kept, and on review vectors turned out to have a real job on the catalog. See [001](decisions/001-hybrid-retrieval.md).

**Obsidian: the assistant added conditions.** The author suggested Obsidian. The assistant pointed out that GitHub does not render wikilinks and that a vault written at the end would be decoration, so this vault uses plain links and started before the code. The author then made the actual goal explicit: "Obsidian era mera sugestão, e queria mesmo era o workflow bom já que será avaliado."

**Data audit: the assistant's script found the traps.** The audit script produced most of [Traps](traps.md). The author has not yet reviewed each finding.

**Instructions conflict: the author surfaced the e-mail.** The assistant had read only the PDF and assumed delivery by e-mail reply. The e-mail the author pasted adds Google Forms, a PDF, English, and "the simplest way possible". See [004](decisions/004-simple.md) and [005](decisions/005-delivery.md).

**No written plan: the author caught it.** Asked "Há plano real?", the honest answer was no: decisions and traps were written, but the sequence of work lived only in the assistant's head. [Plan](plan.md) was written then.

**Name: the assistant's pick rejected.** The assistant recommended "Heitor", after Villa-Lobos. The author: "Heitor é um nome péssimo. Quis dizer clássicos de verdade." The agent is Amadeus.

**Tone: the assistant overdid the humor.** Its samples were jokes. The author: "Ficar colocando piadinhas no meio é necessário? [...] O humor seria 'ranzinza engraçado involuntário' do Lord, não 'piadista'." The persona was written to that brief, and the brief only asks for a persona aligned with the store.

**Tests caught three defects in code the assistant had just written.** A `[[` split across two stream chunks leaked into the text; the claim guard rejected the agent's own fallback message; a test expected 28 manual sections when there are 25.

**A live run exposed two wrong assumptions.** Google's OpenAI-compatible endpoint returns embeddings with `index` set to null, which crashed the sort and silently degraded search to keywords. A turn that "hung" looked like a history bug and was in fact model latency: `gemini-3.8-flash` over 25 s, `gemini-3.5-flash-lite` about 3 s on the same question. The default model will be chosen from eval results.

**Evals caught the agent lying.** Asked why a PIX discount did not appear on order 5, the agent said the item "já estava com desconto". Order 5 has no promotion. The guard cannot catch this because no number is invented. The prompt now forbids explaining past orders with general rules, and the case asserts it. The same run showed the agent saying "vou abrir um chamado" and not opening one.

**Evals also caught the assistant's own bad tests.** Two cases rejected correct answers ("está elegível", "a troca imediata não é mais possível"). The patterns were corrected and the reason recorded here, because loosening a test to pass is exactly what this log exists to expose.

**The assistant's model choice was wrong.** It chose `gemini-3.8-flash` because it was newest. The API's error response revealed a free-tier limit of 20 requests per day per model, which the first eval runs exhausted. See [003](decisions/003-providers.md).

**A provider hiccup looked like a code bug, twice.** Streaming was suspected and tested head to head: not the cause. Latency on the free tier simply varies from 0.8 s to 30 s.

**A parallel-call bug hid behind a vague provider error.** One case failed twice with "400 invalid argument". Google's endpoint sends parallel tool calls with `index: null`, and the collector merged them into one call with broken arguments. Found by printing the raw stream.

**The guard grew from facts to actions.** A prompt rule against promising without acting did not hold on the lite model, so the guard now rejects "abri um chamado" when `open_ticket` was not called. It fired on real runs. This follows the author's principle: "a IA não pode surtar".

**A printed "applied" that applied nothing.** A throwaway script meant to adjust recorded conversations printed success without writing a file. The assistant noticed on the next turn and re-recorded instead, since hand-edited recordings would be fake.

**47/47 is not proof.** The same assistant wrote the cases and the code, and models vary between runs. Stage 5 exists for this reason.

**The author rejected the interface twice before accepting a direction.** The first draft was generic. The second over-corrected by reusing his portfolio's scenery in a chat screen. He redirected the work to the chat products he had named from the start, with his palette and square borders as a subtle theme, and to what a company would expect to see. Rejected drafts were not committed, and from then on interface work went to him as screenshots before entering history.

**The assistant gave two wrong causes for a head-shaking bug.** It blamed duplicate nodes, then rotation accumulating between clips, stating both as facts. Sampling the head's rotation frame by frame showed the real cause: the Idle clip's own head track swings by 0.7 rad. That track is now filtered out, and the samples stay constant.

**The assistant recommended no key on the public site, and the author overruled it.** A visitor without a key would be turned away. The key stays on the server, never reaches the browser, and a per-address rate limit sits in front of it. See [003](decisions/003-providers.md).

**The assistant claimed a fallback it had not tested.** OpenRouter was described as the automatic fallback from the start. Testing it for the public site showed the key returning 401, so the fallback had never run.

**The author found the replies stilted.** Reading them showed why: section numbers in customer text, phrases copied from the prompt's examples, and call-center openings. The prompt was rewritten and citations moved to chips under the message.

**English was added at the author's request, and his test found a gap.** Tools, blocks, manual and persona follow the conversation language. Tool arguments moved to English so the model sees one schema. He then reported that English did not really work. The backend did respond in English when asked to, but a customer writing English in a Portuguese session still got Portuguese. Each message now sets the language, by a small word-count check, and the interface follows.

**A visual check caught wrong product images.** The image script requires brand and model in the result's title, and that rule still let through computer keyboards for "Teclado Sintetizador" and a mismatched guitar. A contact sheet of all 48 matches showed 7 wrong pictures. They were rejected. The author then found most cards with no picture and some with bad crops, so the script now prefers studio shots and products with no exact match get a tagged illustrative image.

**The independent review found what 55/55 did not.** A separate agent with no shared context sent 40 messages and read the code, producing 23 findings in [vault/reviews](reviews/2026-11-01-red-team.md). The worst: a customer imitating the internal check message got a false price past the guard, because the guard trusted values from customer messages. The attempt limit, described in the README as enforced in code, lived in a token the client could discard. Most findings were fixed the same day, some only partly, and each states which. The author rules on them.
