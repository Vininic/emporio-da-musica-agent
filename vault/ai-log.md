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
