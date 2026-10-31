# Workflow

Status: proposed by the assistant, approved by the author.

The author directs and decides. Claude Code implements. The point is that every claim in the README can be traced back and checked.

## The chain

Trap found → decision → eval case → code → commit. [Traps](traps.md) links them.

## Steps

1. **Audit before code.** The data was checked by script before any agent existed. See [Traps](traps.md).
2. **Decisions are written first** in `vault/decisions`, with the author's words when they are his. The assistant may propose; status says who decided.
3. **Evals before prompts.** Each trap becomes a case in `evals/`, asserting tools called, identity gates and exact values. Scores are kept per run, so progress is visible and real.
4. **Small pull requests.** One branch per stage, CI on tests, merge commits. No force-push.
5. **Independent review.** A second agent with no shared context attacks the running agent as a hostile customer and reviews the code. Findings go to `vault/reviews`, and the author accepts or rejects each.
6. **[AI log](ai-log.md).** Where the assistant was overruled, where it was wrong, and what was caught by evals rather than by reading.

## Rules for the coding agent

They live in `CLAUDE.md` at the repository root, versioned with the code.
