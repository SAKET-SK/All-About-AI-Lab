Lesson 2: The Claude 4 Model Family

2.1 Why This Lesson Exists in a Harness Engineering Course

Before you can design a good harness, you need to understand the raw material you're building around: the model itself. Different Claude models trade off intelligence, speed, and cost differently, and a well-designed harness often uses more than one model at once — a cheap, fast model for simple sub-tasks and an expensive, capable model reserved for the hard parts. That routing decision is itself a harness design choice.

One quick note before we go further: model naming moves fast, and by the time you're taking this course, the exact version numbers referenced in the material may already be one generation behind reality. I'll give you the concepts (which are stable) alongside the actual current lineup as of today, so you're not memorizing numbers that expire.

2.2 The Tier System

Anthropic organizes Claude into named tiers, each tuned for a different point on the capability/speed/cost curve. Since Claude 3, the tiers have been named after forms of writing, ordered from shortest/cheapest to longest/most capable:


| Tier | Analogy | Role |
| :--- | :--- | :--- |
| **Haiku** | Short, dense, cheap | Speed and volume — classification, extraction, high-throughput tasks |
| **Sonnet** | Medium-length, well-structured | The balanced default — most coding, writing, and agentic work |
| **Opus** | Long, ambitious | Maximum reasoning depth for genuinely hard problems |


Within a generation, all tiers share the same underlying training philosophy and safety approach — they differ mainly in scale, latency, price, and how far they push on the hardest benchmarks.

2.3 The Current Lineup (as of mid-2026)

As of today, the lineup looks like this:

Claude Haiku 4.5 — the fast, cheap tier. Best for classification, tagging, quick lookups, and high-volume pipelines where latency and cost matter more than squeezing out the last bit of reasoning quality.
Claude Sonnet 5 — the everyday workhorse. Strong reasoning and coding ability at a price point that makes it the default choice for most production use cases.
Claude Opus 4.8 — the flagship reasoning tier, reserved for genuinely hard multi-step problems, dense analysis, or situations where a wrong answer is expensive.
Claude Fable 5 / Claude Mythos 5 — a newer tier that sits above Opus, called the "Mythos" class. These share the same underlying model; Fable 5 carries additional safety measures in sensitive domains (biology, cybersecurity, LLM research), while Mythos 5 is currently restricted to a small set of trusted organizations rather than being broadly available.

If your course materials mention "the Claude 4.5 family — Haiku, Sonnet, and Opus," that's very likely describing the lineup as it stood a bit earlier this year. The three-tier structure it teaches is still exactly correct — just mentally substitute in whatever the current version numbers are when you're actually building.

2.4 The Dimensions That Matter When Choosing a Model

When a harness needs to decide "which model handles this step," there are really four variables in play:

Intelligence / reasoning depth — can it reliably solve the problem in one pass, or does it need multiple attempts and heavy verification scaffolding around it?
Latency — how fast does a response come back? Matters enormously for interactive or high-frequency agentic loops.
Cost — priced per million tokens, with output tokens typically costing several times more than input tokens. This is why a chatty, verbose agent can get expensive fast, and why techniques like prompt caching (covered later in the course) matter.
Context window — how much information can the model hold in view at once. Larger context tiers can ingest bigger codebases or longer documents without losing track of earlier material.
2.5 The Practical Decision Rule

A simplified rule of thumb that shows up throughout the course:

Use Haiku when: the task is simple, repetitive, and high-volume — triage, classification, quick extraction. Think of it as a filter that decides what actually needs to go to a smarter model.
Use Sonnet when: you want a strong, reliable answer quickly, for the majority of everyday coding, writing, and analysis work. For most builders, this is the model you reach for by default.
Use Opus (or above) when: the task is genuinely hard — complex multi-step reasoning, high-stakes code, or anything where getting it wrong is costly. You pay a premium in latency and price for the extra reasoning depth.
2.6 Why This Matters for Harness Design

This tiering directly shapes harness architecture in two recurring patterns you'll see later in the course:

Cascading / triage patterns: a cheap model (Haiku) screens or pre-processes a large volume of inputs, and only the genuinely hard or ambiguous cases get escalated to a more expensive model (Sonnet or Opus). This keeps cost down without sacrificing quality on the cases that need it.
Subagent specialization: in a multi-agent harness, you might deliberately assign a fast, cheap model to narrow, well-defined subagent roles (e.g., "run this lint check and summarize results") while reserving the flagship model for the orchestrating agent that has to make judgment calls.

Model selection, in other words, isn't just a cost-optimization afterthought — it's a first-class harness design decision, made before you write a single tool definition or permission rule.
