# 004 What "simple" means here

Status: proposed by the assistant, reviewed by the author, who added deploy and said not to limit the project over time.

## The tension

The recruiting e-mail says: "you should solve it in the simplest way possible". The brief asks for a persona, data and policy routing, scope handling and justified decisions, and says it values initiative. The e-mail reads as a template for a written case.

## Reading

Simple applies to how the thing runs and how it is built, not to how good the experience is.

Kept simple: one command to run, no Docker, no vector database server, no front-end build, no agent framework hiding the loop, no login.

Not cut: the requirements in the brief, the eval suite, the visual blocks, and a deploy as the last step, at the author's request.

Every component must answer "what breaks without this?" in the README. If it cannot, it goes.
