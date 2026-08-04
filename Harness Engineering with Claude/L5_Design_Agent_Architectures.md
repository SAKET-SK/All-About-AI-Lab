Lesson 5: Design Agent Architectures

5.1 Why Architecture Comes Before Code

Every agentic system starts with a temptation: build one big agent, give it every tool, and let it figure everything out. This works for toy demos and fails at scale. As task volume and complexity grow, a single-agent design runs into three walls:

Context overload — one agent trying to hold "how to classify a ticket," "how to answer billing questions," "how to write technical documentation," and "how to escalate legal issues" all in one prompt becomes unwieldy and inconsistent.
Permission conflicts — a single agent that can both draft a reply and issue a refund needs the most permissive access of all its jobs combined, which is a security and safety problem.
Unpredictable cost — if every task, simple or complex, goes through the same (usually most capable, most expensive) model, you're paying premium prices for routine work.

Agent architecture design is the discipline of decomposing a complex problem into a system of smaller, cooperating agents, each with a narrow job, appropriate tools, and an appropriate model tier — then defining how they hand work to each other.

5.2 Common Architectural Patterns
Pattern 1: Sequential Pipeline
```
Agent A → Agent B → Agent C → Result
```

Each agent's output becomes the next agent's input, in a fixed order. Good for tasks with a natural linear workflow (classify → draft → review). Simple to reason about, but rigid — no branching.

Pattern 2: Orchestrator–Worker (Hub and Spoke)
```
              ┌──▶ Worker A
Orchestrator ─┼──▶ Worker B
              └──▶ Worker C
```

A central orchestrating agent decides which worker(s) handle a given task and in what order, based on the specifics of the input. This is the most common pattern for systems handling heterogeneous inputs (like support tickets, which vary wildly in topic and urgency).

Pattern 3: Parallel / Fan-out–Fan-in
```
         ┌──▶ Agent A ──┐
Input ───┼──▶ Agent B ──┼──▶ Aggregator
         └──▶ Agent C ──┘
```

Multiple agents work on independent sub-pieces simultaneously, and their results are merged. Good when subtasks don't depend on each other's output — trades higher token/API cost for lower wall-clock latency.

Pattern 4: Hierarchical / Escalation
```
Tier 1 Agent → (if unresolved) → Tier 2 Agent → (if unresolved) → Human
```

A cheap, fast agent handles the common case; anything it can't resolve confidently gets escalated up the chain. This is the "smart routing" idea from Lesson 3, generalized into a full architecture — a recurring theme in this course.

Most production systems are actually a mix: hub-and-spoke for routing, hierarchical for escalation, and a sequential step at the end for verification.

5.3 The Decomposition Process

When you face a business problem and need to design the agent system for it, work through these questions in order:

- What are the distinct sub-jobs? List them out as if delegating to human specialists — a triage clerk, a billing specialist, a technical support engineer, a manager who handles escalations.
- Which sub-jobs need different tools or permissions? A billing agent needs read access to payment records; a technical agent needs access to logs or a knowledge base. Different access needs are a strong signal they should be different agents.
- Which sub-jobs need different model tiers? Classification is cheap and fast (Haiku). Drafting a routine reply is moderate (Sonnet). Handling an ambiguous, high-stakes escalation deserves the most capable model (Opus).
- What's the control flow between them? Sequential, hub-and-spoke, parallel, hierarchical, or some mix — determined by whether sub-jobs depend on each other's output.
- Where does verification sit? Decide explicitly where an external check (not just model self-report) confirms a step actually succeeded before moving on.
- What are the deterministic parts? Not everything belongs to an LLM. Things like "has this ticket's SLA deadline passed?" are pure logic — a clock comparison — and should be handled in code, not by asking a model to reason about time. Reserve the model for judgment calls, not arithmetic.
5.4 Applying This to the Support Ticket Scenario

Let's decompose the stated problem: 5,000 tickets/day, 4-hour average response time, missing the 1-hour enterprise SLA.

Sub-jobs identified:

Read and understand an incoming ticket (any channel)
Determine category (billing, technical, account, other) and urgency
Determine whether this customer's SLA requires expedited handling
Draft an appropriate response for the category
Catch anything ambiguous, sensitive, or high-stakes and route it to a more careful reasoner
Check the drafted response before it goes out

Resulting architecture:
```

Ticket arrives
      │
      ▼
┌─────────────┐
│Triage Agent │  (Haiku) — classify category + urgency, read customer tier
└──────┬──────┘
       │
       ▼
┌─────────────┐   deterministic logic, not an LLM call —
│ SLA Router  │   compares customer tier + urgency + elapsed
│ (plain code)│   time against SLA rules
└──────┬──────┘
       │
   ┌───┴────────────────┬─────────────────┐
   ▼                    ▼                 ▼
Billing Agent    Technical Agent    Escalation Agent
  (Sonnet)          (Sonnet)             (Opus)
   │                    │                 │
   └────────────────────┴─────────────────┘
                         │
                         ▼
                  ┌─────────────┐
                  │  QA Agent   │  (Haiku) — checks tone,
                  │             │  completeness before sending
                  └──────┬──────┘
                         │
                         ▼
                  Response sent /
                  logged for SLA tracking
```
Notice: the SLA Router is not an LLM call at all — it's a deterministic rule ("if enterprise tier and unresolved after 45 minutes, escalate") because that's a fact-check, not a judgment call. This is a good illustration of point 6 above: not every box in an agent architecture needs to be an agent.

Now let's build this.

Created a file, ran a command, read a file
Created a file, ran a command, read a file
How to Run
```bash
pip install anthropic
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
python support_ticket_triage.py
```
What Each Sample Ticket Is Designed to Demonstrate

| Ticket | Designed to Test |
| :--- | :--- |
| **T-1001** | Standard tier, clear billing category → routine path through Specialist Agent (Sonnet) |
| **T-1002** | Enterprise + high urgency, technical → escalates even though SLA hasn't technically breached yet (fail-safe on urgency) |
| **T-1003** | Submitted 2h15m ago, enterprise (1hr SLA) → already breached when processed → forces escalation, and the Opus prompt explicitly acknowledges the delay |
| **T-1004** | Ambiguous/uncategorizable ("general feedback") → routes to category: other → escalates not because it's urgent, but because it's ambiguous — the fail-safe-toward-caution principle from Lesson 3, applied again |

Expected Output Shape
```
--- Processing T-1002 (enterprise) ---
  [Triage/Haiku] T-1002: category=technical, urgency=high (0.4s)
  [SLA Router/code] T-1002: route=escalate, sla_deadline=10:00, breached=False
  [Escalation/Opus] T-1002: draft ready (3.9s)
  [QA/Haiku] T-1002: verdict=approve (0.5s)

============================================================================
Ticket   Tier        Category   Urgency  Handled By            SLA Breach  QA
--------------------------------------------------------------------------------
T-1001   standard    billing    low      Specialist-Sonnet...  False       approve
T-1002   enterprise  technical  high     Escalation-Opus       False       approve
T-1003   enterprise  other      medium   Escalation-Opus       True        approve
T-1004   standard    other      low      Escalation-Opus       False       approve
============================================================================
```
Tying It Back to the Architecture Diagram

Run the script and watch the log lines — you're watching the architecture from Section 5.4 execute in real time:

[Triage/Haiku] = the Triage Agent box
[SLA Router/code] = the deterministic Router box — notice it never says "calling model," because it isn't one
[Escalation/Opus] or [Specialist-Sonnet] = the branch the hub-and-spoke pattern took
[QA/Haiku] = the verification step closing the loop before anything "sends"

One thing worth deliberately breaking to build intuition: change T-1004's body to something clearly billing-related and rerun — you should see it take the cheaper Specialist path instead of escalating, since the ambiguity trigger no longer fires. That's a good way to directly feel the router's decision boundary rather than just reading about it.
