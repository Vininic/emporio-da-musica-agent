# 001 Hybrid retrieval plus deterministic core

Status: decided by the author.

## Decision

Function-calling agent with typed tools, on top of three layers:

- **Vector RAG plus keyword search** over the policy manual, chunked by numbered section so answers can cite `§4.1`.
- **Vector search over the catalog** for what SQL cannot answer ("violão de som quente para iniciante"), combined with hard filters on price, category and availability.
- **Deterministic Python** for price, discount, PIX, installments, shipping and hours. The model never does arithmetic.

SQLite holds the operational data. The agent has no free SQL: tools run fixed, parameterized queries, and the customer table is reachable only through identity verification.

## Why

The author, on the assistant's first recommendation of skipping vectors for an 8-page manual: "Não dá pra ter RAG vetorial + agente, + o código calcula preço desconto e parcela? Também há necessidade de ter RAG no currículo e portfólio."

Purely on need, a manual this short could be served by section lookup. Vectors earn their place on the catalog, where free-text descriptions meet vague questions. The hybrid also degrades gracefully: without an embedding key, keyword search still answers.

Free SQL rejected because a model-written query can reach `customers`.

## Related

[Traps](../traps.md) T07, T13, T15, T19, T20, T27.
