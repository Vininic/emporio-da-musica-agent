# 002 Local web chat with real blocks

Status: decided by the author.

## Decision

A local web chat in the author's visual identity (dark, palette `#06070A #4A69C7 #A8B8F4 #EEF4FF #7F8AA9 #263A70 #F7D25C`), clean like mainstream chat products, with fluid streaming and animation.

Answers carry real visual blocks: product cards, price breakdown, order timeline, policy citation, handoff ticket. Blocks are rendered from tool output, so a price on a card is always the system's price, never model text.

## Constraints

Python must stay the main language, so no React build. FastAPI streams over SSE to a small no-build front-end, one command to run. GitHub's language bar is checked before delivery.

## Why

The author asked for blocks that behave "como se realmente fosse um bloco na mensagem e não mero texto formatado md", as in Chronos. The role is full-stack for GenAI applications, so the interface is part of what is evaluated, not decoration.
