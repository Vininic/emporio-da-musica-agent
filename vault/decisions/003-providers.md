# 003 Providers and BYOK

Status: decided by the author; default model to be confirmed by eval results.

## Decision

Google AI Studio by default, OpenRouter as the alternative, key supplied by whoever runs it. Both expose OpenAI-compatible endpoints, so one client covers both by swapping base URL and key.

Starting point, from the official docs read on 2026-10-31:

- Chat: `gemini-3.8-flash` (stable, listed as free of charge).
- Embeddings: `gemini-embedding-2`. It rejects `task_type`, so tasks go in the text prefix (`task: search result | query: ...`).

## Known limits

- The Gemini rate-limit page publishes no free-tier numbers; they appear per project in AI Studio.
- The free tier of `gemini-3.8-flash` is marked "Used to improve our products: Yes". All data here is fictional, so this is acceptable for the prototype and would not be in production.
- OpenRouter `:free` models allow 50 requests per day under the credit threshold.

Live evals must therefore be cached and rationed. Replay of recorded conversations lets anyone see the agent without a key.
