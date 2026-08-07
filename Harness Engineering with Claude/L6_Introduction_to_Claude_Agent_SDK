# Lesson 6: Introduction to the Claude Agent SDK

## Overview

This lesson introduces the **Claude Agent SDK** — the programmable library that exposes the same agent loop, tools, and context management that power Claude Code, but callable from your own Python or TypeScript code instead of an interactive CLI.

Where previous lessons built agentic systems by hand (manual API calls, hand-written routing and orchestration logic), this lesson shows how the SDK absorbs most of that scaffolding into a reusable engine.

> **Note:** The Claude Agent SDK was formerly called the **Claude Code SDK**. If you come across older tutorials or blog posts referencing "Claude Code SDK," they're describing the same product under its previous name.

---

## Key Concepts

### 1. What the SDK Is

- Built on top of the same agent harness that powers Claude Code.
- Gives developers the same tools, agent loop, and context management as Claude Code — as a library, in Python (`claude-agent-sdk` on PyPI) or TypeScript (`@anthropic-ai/claude-agent-sdk` on npm).
- The SDK and the interactive Claude Code CLI are powered by the same underlying engine; the difference is the *interface* used to access it.

### 2. The `query()` Method

- The main entry point for any agentic task.
- Takes two inputs:
  - A **prompt** — natural-language description of the goal.
  - An **options object** — configuration including model choice and, most importantly, which tools are available.
- Unlike a single-shot API call, `query()` returns a **stream of messages**, letting you observe the agent's reasoning and actions step by step as they happen.
- **Sessions** allow state to persist across multiple `query()` calls, enabling multi-step workflows where later queries build on earlier work.

### 3. The Agentic Loop

The SDK automatically manages a Perceive → Reason → Act cycle:

| Stage | Description |
|---|---|
| **Reason** | The agent decides what it needs to do next to achieve the goal. |
| **Act** | It uses an available tool to carry out that decision. |
| **Perceive** | The result of the action becomes new information for the next cycle. |

**Worked example:** Goal = "Summarize api-guide.md"
1. Agent reasons it must read the file before it can summarize it.
2. Agent acts by invoking the `Read` tool.
3. Agent perceives the file's contents as the tool result, then proceeds to summarize.

This entire cycle is handled automatically by the SDK — you don't hand-write the branching logic that decides which tool to call next.

### 4. Tools — An Agent's Capabilities

Tools are grouped by function and potential impact:

| Category | Tools | Role |
|---|---|---|
| Read-only | `Read`, `Glob`, `Grep` | Observe the file system without changes ("the agent's eyes") |
| Modification | `Edit`, `Write` | Change or create files |
| Execution | `Bash` | Run shell commands — powerful, system-level access |
| Web | `WebSearch`, `WebFetch` | Access the internet for information/content |
| Specialized | `Task`, `Skill` | Invoke subagents or specific skills |

**Best practice — Principle of Least Privilege:** only give an agent the tools it strictly needs for the task at hand. This creates a safe, predictable operational boundary and limits the blast radius of any mistake.

### 5. Permission Modes

Permission modes provide global control over the agent's autonomy level:

| Mode | Behavior |
|---|---|
| `default` | Most restrictive — every action requires explicit approval from your code. |
| `acceptEdits` | Auto-approves low-risk file edits; still gates powerful actions like shell execution. |
| `bypassPermissions` | Full autonomy — no approval gate on any allowed tool. Suitable only for trusted, automated environments. |
| `plan` | No tool execution at all — the agent can only analyze and produce a step-by-step plan, optionally using `AskUserQuestion` to clarify requirements. |

### 6. Building Workflows

- **Simple workflow example:** "Read this document, summarize it." One prompt, `Read` tool allowed, single `query()` call.
- **Complex workflow example:** Standardizing legal contracts across various formats — the agent uses `Read` to ingest documents and `Write` to save standardized output. A fully multi-step, multi-tool task accomplished through a **single `query()` call**, since looping, tool selection, and sequencing are all handled internally by the SDK.

---

## Key Takeaway

The SDK doesn't introduce new agentic concepts — it operationalizes the same Perceive-Reason-Act loop and harness components (tools, permissions, memory) covered in earlier lessons, but removes the need to hand-write the orchestration logic yourself. You configure *what's possible* (tools, permissions, model); the SDK drives the loop.

---

## Reference Links

- Agent SDK Overview: https://docs.claude.com/en/docs/agent-sdk/overview
- Claude Code Docs: https://docs.claude.com/en/docs/claude-code/overview

---

*Part of the "Harness Engineering with Claude and Claude Code" course series.*
