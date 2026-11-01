# 002 Web chat with real blocks

Status: decided by the author.

## Decision

A web chat, clean like mainstream chat products, with fluid streaming and animation.

Answers carry real visual blocks: product cards, price breakdown, order timeline, policy citation, handoff ticket. Blocks are rendered from tool output, so a price on a card is always the system's price, never model text.

## Direction

The structure comes from the chat products the author named: ChatGPT, Claude, Janitor AI and SillyTavern. His identity is a subtle theme on top: blue-violet palette, gold for prices, square borders, JetBrains Mono. The target reader is a company evaluating the work, so the screen stays a clean, terminal-flavored chat. Earlier drafts that reused scenery from his portfolio were rejected.

- Left: conversations with search, rename and delete, plus recorded conversations.
- Center: edit and resend, regenerate, stop, copy and rating on messages. The composer holds the model and reasoning picker.
- Right: the robot in a fixed place, tool calls as they happen, and a store tab with address, weekly hours, holidays and a map. The store tab needs no LLM call.
- One settings dialog: language, theme, API key, downloads and about.

The robot is the CC0 RobotExpressive model with a conductor skin built in code. It conducts while text streams, looks down while tools run, and gestures occasionally when idle. Nothing depends on it.

Product images come from a script that searches the web and accepts a result only when brand and model are in its title. Results were then reviewed by eye. A product with no reliable image shows a category icon, because a wrong picture in a store is worse than none.

## Constraints

Python must stay the main language, so no React build. FastAPI streams over SSE to a small no-build front-end, one command to run. GitHub's language bar is checked before delivery.

## Why

The author asked for blocks that behave "como se realmente fosse um bloco na mensagem e não mero texto formatado md", as in Chronos. The role is full-stack for GenAI applications, so the interface is part of what is evaluated, not decoration.
