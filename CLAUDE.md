# Working agreement

Prototype customer service agent for Empório da Música. Read `vault/Home.md` first.

## Rules

- Never rewrite history: no force-push, no squash, no backdating. Commit each real step.
- Decisions that belong to the author go to him first. Record them in `vault/decisions` with who decided.
- The LLM never computes prices, discounts, installments, dates or eligibility. Python does.
- The LLM never writes SQL. Tools run fixed, parameterized queries.
- Every customer-facing fact comes from a tool result. A price on a block comes from tool output.
- Customer data is reachable only after identity verification, enforced in code, not in the prompt.
- Every trap in `vault/traps.md` gets an eval case. New failure, new case.
- Report eval scores as measured. Failing cases stay visible.
- `vault/ai-log.md` records only what happened.
- Secrets stay in `.env`. Never read, print or commit keys.

## Language

English for code, commits and docs. Customers read Portuguese or English, their choice.

## Before committing

Run the tests. Keep Python as the repository's main language.
