Lesson 3: Model Selection & Intelligent Routing

The Scenario

A weather notification service ingests thousands of alerts a day. They range wildly in stakes:

| Alert Type | Example | Stakes | Right Model |
| :--- | :--- | :--- | :--- |
| **Routine update** | "Partly cloudy, high of 72°F" | Low — informational only | Haiku |
| **Watch/advisory** | "Thunderstorm watch until 8pm" | Medium — needs clear, actionable messaging | Sonnet |
| **Severe warning** | "Confirmed tornado, take shelter now" | High — errors could cost lives | Opus |

Instead of sending every alert through your most expensive, slowest model "just to be safe," you build a small router step that classifies the incoming alert first, then dispatches it to the model tier that matches its actual complexity. This is a classic harness pattern:

```
Incoming alert
      │
      ▼
 [Cheap classifier: Haiku]  ← fast, cheap triage
      │
      ├── simple  → Haiku generates the notification
      ├── moderate → Sonnet generates the notification
      └── severe  → Opus performs deep analysis + notification
```

This mirrors the cascading pattern from Lesson 2: a cheap model filters volume, and only the cases that genuinely need it escalate to a more capable (and more expensive) model. At scale, this is the difference between a service that's affordable to run and one that isn't — while still guaranteeing your highest-stakes alerts get your best reasoning.

The Four Functions You'll Build
classify_alert_haiku — fast triage: given raw alert text, output one word: simple, moderate, or severe.
generate_notification_haiku — for simple alerts, draft a short push notification. Low complexity, needs speed.
generate_detailed_summary_sonnet — for moderate alerts, draft a fuller public-facing summary with recommended precautions. Needs balanced reasoning and clear writing.
analyze_severe_threat_opus — for severe alerts, perform deep reasoning: assess risk, estimate population impact, and give structured emergency-response recommendations.

Then a router function ties them together, and a comparison harness runs the same task on all three models so you can directly see the latency/cost/quality tradeoff.

Now let's build it.

Ran 2 commands, created a file
Ran 2 commands, created a file

Syntax verified — it compiles cleanly. I can't execute it end-to-end here since it needs your own ANTHROPIC_API_KEY and live API calls, but here's exactly what to expect when you run it locally.

Presented file
Presented file
3.2 How to Run It
bash
pip install anthropic
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
python weather_model_routing.py
3.3 What You'll See (Expected Shape of Output)

```
### PART 1: Intelligent Routing ###

--- Simple alert ---
  [Router] Haiku classified this alert as: 'simple' (0.4s, 45in/3out tokens)
  Routed to: claude-haiku-4-5-20251001
  Output:
  Sunny skies and mild temps today — nothing to worry about, enjoy it!

--- Moderate alert ---
  [Router] Haiku classified this alert as: 'moderate' (0.4s, 52in/3out tokens)
  Routed to: claude-sonnet-5
  Output:
  A thunderstorm watch is in effect for the metro area until 8 PM tonight...

--- Severe alert ---
  [Router] Haiku classified this alert as: 'severe' (0.4s, 68in/3out tokens)
  Routed to: claude-opus-4-8
  Output:
  1. Immediate Risk Assessment: A confirmed tornado is actively tracking...

### PART 2: Head-to-Head Model Comparison (severe alert) ###

==============================================================================
Model      Time (s)   Input tok   Output tok  Est. cost*
------------------------------------------------------------------------------
Haiku      0.9        95          210         $0.00115
Sonnet     1.8        95          245         $0.00396
Opus       4.2        95          312         $0.02481
==============================================================================

(Exact timings/tokens will vary run to run — that's expected with live API calls.)

```

3.4 What This Demonstrates
classify_alert_haiku — the triage step. Notice it's called on every alert, but costs almost nothing (tiny input/output, sub-second latency).
The router (route_alert) — is where the harness design decision lives: it never lets a human (or a slower model) make the routing call — the routing itself is automated and cheap.
The comparison table — makes the tradeoff concrete rather than theoretical. You'll typically observe: Haiku is fastest and cheapest but gives the thinnest analysis; Opus is slowest and most expensive but gives the most structured, cautious reasoning; Sonnet sits in between.
The "fail safe toward more analysis" comment in route_alert — a small but important harness design choice: if the classifier ever returns something unexpected, the router defaults to the most careful path (Opus) rather than the cheapest one. In safety-relevant systems, your fallback behavior should always err toward more scrutiny, not less.

One thing worth actually experimenting with once you have it running: change SEVERE_ALERT's wording slightly and rerun the classifier a few times. You'll likely see Haiku's classification is very consistent for clear-cut cases but can wobble on borderline ones — which is itself a good discussion point for Lesson 4 onward, when the course gets into verification and control systems for exactly this kind of uncertainty.
