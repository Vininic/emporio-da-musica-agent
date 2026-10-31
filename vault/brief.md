# Brief

## The challenge

Artefact, AI Engineer (Full-Stack for GenAI applications). Prototype a customer service agent for Empório da Música, a fictional instrument store in Campo Grande/MS. Python is the only hard technical constraint.

The agent must:

- take on a persona aligned with the store's identity and tone
- answer from the provided context
- know when to query data (availability, prices, order status) and when to query policies (exchange rules, hours, payment)
- handle out-of-scope questions properly

Evaluation, from the brief: "Estamos mais interessados em como você resolve o problema e toma decisões do que em uma solução perfeita."

## Rules on the repository

- Public GitHub repository.
- "Mantenha um histórico de commits com progresso real — não faça force-push de tudo em um único commit."
- Nothing changes after the deadline.
- README: setup, justified technical decisions, known limitations and next steps, and how coding assistants were used.
- 3 to 5 example conversations, at least one non-trivial.
- Ambiguity: assume, document in the README, move on.

## The author's direction (verbatim)

Interface:

> Melhor web local nessa estética mesmo. Mas quero bem clean e padrão chats competentes, com animações flúidas igual um GPT, próprio Claude, Janitor AI, Silly Tavern ou afins. O próprio Chronos já teve algo parecido implementado, e é importante as respostas terem integrações visuais também (de novo com exemplo do Chronos, que coloca um bloco de tempo do dia como se realmente fosse um bloco na mensagem e não mero texto formatado md.

Retrieval:

> Não dá pra ter RAG vetorial + agente, + o código calcula preço desconto e parcela? Também há necessidade de ter RAG no currículo e portfólio. Já fica. Se o SQL é vulnerável, não precisa ser.

Providers:

> Normalmente uso AI studio pra tudo. Tenho um Openrouter também. Normalmente é sempre essas por padrão do sistema em deploy e BYOK.

Workflow:

> Sim, usar obsidian então. Mas Obsidian era mera sugestão, e queria mesmo era o workflow bom já que será avaliado.

Standing principle, from earlier projects: "a IA não pode surtar". A deterministic core does the work; the LLM reads intent and narrates.
