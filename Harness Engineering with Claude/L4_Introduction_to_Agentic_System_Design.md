Lesson 4: Introduction to Agentic System Design

4.1 From "Chatbot" to "Agent" — What Actually Changes

Up to this point, everything we've built has been reactive: you send Claude a message, it sends back a response, done. That's a chatbot pattern — a single request, a single reply.

An agent is different. It doesn't just answer — it operates in a loop, taking multiple steps, using tools, checking its own progress, and continuing until a goal is reached or it decides it's stuck. The shift is from "answer me this" to "go accomplish this."

This lesson introduces the conceptual skeleton that every agentic system is built on, regardless of the specific framework or tool involved.

4.2 The Perception–Reasoning–Action Loop

This is the core mental model for how an agent operates moment to moment. It's borrowed from classical AI and robotics, and it maps cleanly onto how Claude Code (or any tool-using agent) actually behaves.

```

        ┌──────────────────────────────┐
        │                              │
        ▼                              │
   ┌─────────┐    ┌───────────┐    ┌────────┐
   │PERCEIVE │───▶│  REASON   │───▶│  ACT   │
   └─────────┘    └───────────┘    └────────┘
        ▲                              │
        └──────────────────────────────┘
         (result of action feeds back in)

```

Perceive — The agent observes the current state of its environment. For a coding agent, this might mean reading a file, viewing a test failure's output, checking a directory listing, or simply reading the user's latest instruction. Perception is always bounded by what's actually in the model's context — if it can't see something, it can't perceive it.

Reason — The agent interprets what it perceived and decides what to do next. This is where the model's intelligence does the heavy lifting: "the test failed because of a null pointer on line 42, I should check how that variable gets initialized." Reasoning produces a plan for the next action, not the final answer.

Act — The agent executes a concrete action in the environment — running a shell command, editing a file, calling an API, asking the user a clarifying question. Crucially, the action changes the environment, which means...

...the loop repeats. The result of the action becomes new information to perceive on the next cycle. A file edit produces a new file state. A test run produces new output. A shell command produces new stdout. The agent keeps cycling through Perceive → Reason → Act until it judges the task complete, hits a limit, or needs human input.

Why This Loop Matters for Harness Design

Every harness mechanism you'll study in this course exists to make one part of this loop work better:


| Loop Stage | What Can Go Wrong | Harness Mechanism That Helps |
| :--- | :--- | :--- |
| **Perceive** | Agent can't see relevant info, or is drowned in irrelevant info | Context management, on-demand file/skill loading |
| **Reason** | Agent's plan is based on stale or incomplete understanding | Memory (`CLAUDE.md`), curated knowledge |
| **Act** | Agent takes a destructive or out-of-scope action | Permissions, sandboxing, approval gates |
| **Loop control** | Agent loses track of long-running progress, repeats work, or never stops | State/task tracking, termination conditions |


So when later lessons introduce specific components (hooks, permissions, subagents), you should be able to place each one back onto this loop and ask: which stage of Perceive-Reason-Act is this actually improving?

4.3 The Components of an Agentic System

Zooming out from the single loop cycle, a full agentic system is generally described as having these structural components:

1. The Model (the reasoning engine)

This is Claude itself — the part that actually does the perceiving-and-interpreting and the deciding-what-to-do-next. It's swappable in principle (you could use different tiers, as in Lesson 3), but it's the one component that supplies intelligence rather than structure.

2. The Tool Set (the hands)

A defined, bounded list of actions the agent is permitted to take — read a file, run a bash command, search the web, call an external API. Each tool typically has:

A name and description (so the model knows when to use it)
A strict input schema (so the model's request is well-formed and the harness can validate it before execution)
A handler (the actual code that performs the action and returns a result)

Good tool design keeps each tool atomic and composable — one clear action per tool, rather than a single mega-tool that tries to do everything. This makes the model's choices easier to reason about and easier for you to audit afterward.

3. Memory (what persists across the loop)

Two separate things get called "memory," and it's worth distinguishing them:

Working memory — what's in the current context window right now: recent messages, tool results, files read this session.
Persistent memory — information that survives across sessions: project conventions in a file like CLAUDE.md, a progress log, a task list. Without persistent memory, every new session starts from zero, which is disastrous for long-running or multi-day tasks.
4. Control / Permission System (the boundaries)

This governs what the agent is allowed to do without asking, versus what requires approval. For example: reading files might be unrestricted, but deleting files or pushing to main might require explicit human sign-off. This is the component most directly responsible for making autonomy safe rather than reckless.

5. Verification (the feedback signal)

Some mechanism, external to the model's own confidence, that checks whether an action actually worked — a test suite, a type checker, a diff review, a schema validator. Without this, the loop has no reliable way to know when to stop, retry, or escalate to a human. This ties directly back to Lesson 1's point: models are bad at knowing when they themselves are wrong.

6. Orchestration / State Tracking (the loop manager)

The part of the system that actually drives the Perceive-Reason-Act cycle forward — deciding when to continue, when the task is done, when to spawn a subagent for an isolated piece of work, and when to give up and ask for help. For long or complex tasks, this often includes an explicit task list or dependency graph so the agent (and you) can see what's been done and what remains.

4.4 Putting It Together

A useful way to hold all of this in your head:

The model perceives, reasons, and acts. The harness decides what it can perceive, what actions it can take, what's remembered, what's allowed, what's checked, and when to stop.

The model supplies the intelligence in each loop cycle. Every other component in Section 4.3 is something you design, and every design choice you make either tightens or loosens the loop's reliability. That's really the thesis of the entire course: the loop itself is almost embarrassingly simple — three steps repeating — and yet the six components wrapped around it are where nearly all the engineering effort, and nearly all the failure modes, actually live.
