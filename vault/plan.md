# Plan

Written on 2026-10-31 at the author's prompting ("Há plano real?"), after stage 2 had started. Until then the sequence existed only in the assistant's head. Each stage is meant to be one pull request, though PR 2 grew to include the first eval suite and web chat. A stage is done when its check passes, not when the code exists.

Deadline: Tuesday 2026-11-03, 23:59 São Paulo. See [005](decisions/005-delivery.md).

| # | Stage | Done when | Status |
|---|---|---|---|
| 1 | Deterministic core | Prices, installments, hours, shipping, returns and the identity gate are tested; CI green | Done, PR 1 |
| 2 | Retrieval, tools, agent loop | Unit tests pass and a real conversation runs end to end on Gemini | Done, PR 2 |
| 3 | Evals | Every trap in [Traps](traps.md) has a case; a live run produces a scored report kept in the repo | Done: 55 cases in two languages, latest run 55/55 after 50/55 and 49/55, see `evals/HISTORY.md`. Same assistant wrote the cases and the code; stage 5 tests this independently |
| 4 | Web chat | Streaming, inline blocks, trace panel and robot run in a browser, checked on desktop and phone width | Rebuilt after the author's review, in Portuguese and English; direction accepted, see [002](decisions/002-interface.md) |
| 5 | Independent review | A separate agent attacks the running agent and reviews the code; the author rules on each finding; accepted ones become fixes and cases | 23 findings, all accepted by the author, fixes applied, see [review](reviews/2026-11-01-red-team.md) |
| 6 | Conversations and README | 3 to 5 real recorded conversations; README covers setup, decisions, limitations, AI use | Done: 8 recorded, 5 Portuguese and 3 English |
| 7 | Deploy | Public URL works with BYOK and with replay of recorded conversations | |
| 8 | Delivery | English PDF ready for the author to submit; final eval run; language bar shows Python; repository frozen | |

## Author checkpoints

- End of stage 4: the author sees the chat running and judges it.
- Stage 5: the author rules on findings.
- Stage 8: the author submits the form and replies to the e-mail.

## Rule for cutting scope

Stages 1 to 6 and 8 are required by the brief. Stage 7 is the author's addition. If time runs short, the order of sacrifice is: deploy, then robot gestures, then replay. Evals and the blocks stay.
