# 003 Providers and BYOK

Status: providers decided by the author; default model decided from measurements.

## Decision

Google AI Studio by default, OpenRouter as automatic fallback when its key is present, key supplied by whoever runs it. Both expose OpenAI-compatible endpoints, so one client covers both by swapping base URL and key.

- Chat: `gemini-3.5-flash-lite`, then `gemini-3.1-flash-lite`, then OpenRouter.
- Embeddings: `gemini-embedding-2`. It rejects `task_type`, so tasks go in the text prefix (`task: search result | query: ...`).

## What decided the model

The assistant's first choice was `gemini-3.8-flash`, the newest stable model. Measurement overturned it on 2026-10-31:

- The free tier allows **20 requests per day, per model** on `gemini-3.6-flash` and `gemini-3.8-flash` (quota `GenerateRequestsPerDayPerProjectPerModel-FreeTier`, value 20). One conversation with tools uses several requests, so an evaluator with a free key would run out within minutes. The documentation does not publish this; it came from the API's error response.
- `gemini-3.8-flash` also returned 503 and took over 25 s to first byte on calls where `gemini-3.5-flash-lite` took about 3 s.
- `gemini-3.5-flash-lite` carried full eval runs on the free tier.

The cost is quality: the lite model occasionally slips in Portuguese ("Boa dia"). Tools and the guard hold the facts either way.

## Variance

The same free-tier call takes anywhere from 0.8 s to 30 s, in streaming or not. So the wait for the first byte is capped at 12 s, then the next model is tried, then the next provider. A single slow call must not hold the customer.

## Known limits

- The free tier is marked "Used to improve our products: Yes". All data here is fictional, so this is acceptable for the prototype and would not be in production.
- OpenRouter is paid per token, and its `:free` models allow 50 requests per day under the credit threshold.
- Rate limits make evals wait; waiting is subtracted from reported latency.
