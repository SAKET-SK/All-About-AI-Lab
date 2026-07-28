"""
Lesson 3 Exercise 1: Intelligent Model Routing
Weather Notification Service — Haiku vs Sonnet vs Opus

WHAT THIS SCRIPT DOES
----------------------
1. Defines three sample weather alerts of increasing severity/complexity.
2. Implements four functions, each calling a different Claude model for a
   task suited to that model's strengths:
     - classify_alert_haiku          (Haiku: fast triage)
     - generate_notification_haiku   (Haiku: simple generation)
     - generate_detailed_summary_sonnet (Sonnet: balanced writing)
     - analyze_severe_threat_opus    (Opus: deep reasoning)
3. Implements route_alert(), a router that classifies first, then dispatches
   to the right model tier automatically (the "intelligent routing" pattern).
4. Runs a head-to-head comparison: the SAME severe alert is sent to Haiku,
   Sonnet, and Opus, timing each call and printing token usage, so you can
   directly see the speed/cost/quality tradeoff.

SETUP
-----
1. pip install anthropic
2. Set your API key:  export ANTHROPIC_API_KEY="sk-ant-..."
3. Run:  python weather_model_routing.py

NOTE ON MODEL NAMES
--------------------
Model version strings change over time. The ones below were current as of
mid-2026. If a call fails with a "model not found" error, check
https://docs.claude.com/en/docs/about-claude/models/overview for the latest
model IDs and swap them in.
"""

import os
import time
import sys

import anthropic

# ---------------------------------------------------------------------------
# Model tier constants — swap these if Anthropic ships newer versions
# ---------------------------------------------------------------------------
MODEL_HAIKU = "claude-haiku-4-5-20251001"
MODEL_SONNET = "claude-sonnet-5"
MODEL_OPUS = "claude-opus-4-8"

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment


# ---------------------------------------------------------------------------
# Sample alerts of increasing complexity
# ---------------------------------------------------------------------------
SIMPLE_ALERT = (
    "Weather update: Partly cloudy today, high of 72°F, light breeze from "
    "the west. No precipitation expected. No action needed."
)

MODERATE_ALERT = (
    "Thunderstorm watch issued for the metro region, effective until 8:00 PM "
    "tonight. Conditions are favorable for heavy rain, frequent lightning, "
    "and gusty winds up to 45 mph. Residents should secure loose outdoor "
    "items and monitor local updates."
)

SEVERE_ALERT = (
    "TORNADO WARNING: A confirmed tornado has been spotted 3 miles "
    "southwest of downtown, moving northeast at approximately 35 mph. "
    "The storm is producing large hail and destructive winds. This is a "
    "life-threatening situation for the following zip codes: 30301, 30302, "
    "30303, 30305. Take shelter immediately in a basement or interior "
    "room on the lowest floor, away from windows."
)


# ---------------------------------------------------------------------------
# Helper: time a single API call and print usage stats
# ---------------------------------------------------------------------------
def _call_model(model_name, system_prompt, user_message, max_tokens=300):
    start = time.perf_counter()
    response = client.messages.create(
        model=model_name,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    elapsed = time.perf_counter() - start
    text = response.content[0].text
    usage = response.usage
    return {
        "model": model_name,
        "text": text,
        "elapsed_sec": round(elapsed, 2),
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
    }


# ---------------------------------------------------------------------------
# Function 1: Fast triage classification (Haiku)
# ---------------------------------------------------------------------------
def classify_alert_haiku(alert_text: str) -> str:
    """
    Use Haiku for cheap, fast classification. This is a low-complexity task
    (single-word output) that doesn't need a large model — speed and cost
    matter more here than deep reasoning.
    """
    system_prompt = (
        "You classify weather alerts by severity. Respond with exactly one "
        "word: 'simple', 'moderate', or 'severe'. No punctuation, no "
        "explanation."
    )
    result = _call_model(MODEL_HAIKU, system_prompt, alert_text, max_tokens=10)
    result["text"] = result["text"].strip().lower()
    return result


# ---------------------------------------------------------------------------
# Function 2: Simple notification generation (Haiku)
# ---------------------------------------------------------------------------
def generate_notification_haiku(alert_text: str) -> dict:
    """
    Draft a short push notification for a routine, low-stakes alert.
    Haiku is well-suited here: the task is short-form generation with no
    complex reasoning required.
    """
    system_prompt = (
        "You write short push notifications for a weather app. Keep it to "
        "one sentence, under 20 words, friendly tone."
    )
    return _call_model(MODEL_HAIKU, system_prompt, alert_text, max_tokens=60)


# ---------------------------------------------------------------------------
# Function 3: Detailed public summary (Sonnet)
# ---------------------------------------------------------------------------
def generate_detailed_summary_sonnet(alert_text: str) -> dict:
    """
    For moderate-complexity alerts, use Sonnet to produce a fuller,
    well-structured summary with recommended precautions. This needs more
    nuanced writing than Haiku typically produces, but doesn't require
    Opus-level deep reasoning.
    """
    system_prompt = (
        "You are a public safety communicator. Write a clear, calm summary "
        "(3-4 sentences) of this weather alert for a general audience, "
        "including one concrete recommended precaution."
    )
    return _call_model(MODEL_SONNET, system_prompt, alert_text, max_tokens=250)


# ---------------------------------------------------------------------------
# Function 4: Deep threat analysis (Opus)
# ---------------------------------------------------------------------------
def analyze_severe_threat_opus(alert_text: str) -> dict:
    """
    For severe, life-threatening alerts, use Opus to perform deeper
    reasoning: risk assessment, likely impact, and structured
    recommendations for both the public and emergency responders. Getting
    this wrong is costly, so it's worth paying for the strongest reasoning
    available.
    """
    system_prompt = (
        "You are an emergency management analyst. Given a severe weather "
        "alert, produce a structured response with three sections:\n"
        "1. Immediate Risk Assessment (who is affected, how severe)\n"
        "2. Public Guidance (specific, actionable safety steps)\n"
        "3. Responder Coordination Notes (what emergency services should "
        "prioritize)\n"
        "Be concise but thorough."
    )
    return _call_model(MODEL_OPUS, system_prompt, alert_text, max_tokens=500)


# ---------------------------------------------------------------------------
# The Router: classify first, then dispatch to the right model tier
# ---------------------------------------------------------------------------
def route_alert(alert_text: str) -> dict:
    """
    Intelligent routing pattern:
      1. A cheap model (Haiku) classifies the alert's severity.
      2. Based on that classification, the alert is dispatched to the
         model tier appropriate for its complexity.
    This keeps routine traffic cheap and fast while still guaranteeing
    severe alerts get the deepest reasoning available.
    """
    classification = classify_alert_haiku(alert_text)
    severity = classification["text"]

    print(f"  [Router] Haiku classified this alert as: '{severity}' "
          f"({classification['elapsed_sec']}s, "
          f"{classification['input_tokens']}in/{classification['output_tokens']}out tokens)")

    if severity == "simple":
        result = generate_notification_haiku(alert_text)
    elif severity == "moderate":
        result = generate_detailed_summary_sonnet(alert_text)
    else:  # severe, or anything unexpected — fail safe toward more analysis
        result = analyze_severe_threat_opus(alert_text)

    result["classified_as"] = severity
    return result


# ---------------------------------------------------------------------------
# Comparison harness: same task, three models, side by side
# ---------------------------------------------------------------------------
def compare_models_head_to_head(alert_text: str):
    """
    Sends the SAME severe alert to Haiku, Sonnet, and Opus using an
    identical prompt, so you can directly compare speed, token usage,
    and response quality across tiers.
    """
    shared_system_prompt = (
        "You are an emergency management analyst. Given a severe weather "
        "alert, produce a structured response with three sections:\n"
        "1. Immediate Risk Assessment\n2. Public Guidance\n"
        "3. Responder Coordination Notes\nBe concise but thorough."
    )

    results = []
    for model_name, label in [
        (MODEL_HAIKU, "Haiku"),
        (MODEL_SONNET, "Sonnet"),
        (MODEL_OPUS, "Opus"),
    ]:
        print(f"  Calling {label}...")
        r = _call_model(model_name, shared_system_prompt, alert_text, max_tokens=500)
        r["label"] = label
        results.append(r)

    return results


def print_comparison_table(results):
    print("\n" + "=" * 78)
    print(f"{'Model':<10} {'Time (s)':<10} {'Input tok':<11} {'Output tok':<11} {'Est. cost*':<12}")
    print("-" * 78)
    # Rough per-million-token pricing snapshot (input / output) — check
    # current pricing at https://docs.claude.com before relying on this.
    pricing = {
        "Haiku": (1.00, 5.00),
        "Sonnet": (3.00, 15.00),
        "Opus": (15.00, 75.00),
    }
    for r in results:
        in_price, out_price = pricing[r["label"]]
        cost = (r["input_tokens"] / 1_000_000 * in_price) + \
               (r["output_tokens"] / 1_000_000 * out_price)
        print(f"{r['label']:<10} {r['elapsed_sec']:<10} {r['input_tokens']:<11} "
              f"{r['output_tokens']:<11} ${cost:.5f}")
    print("=" * 78)
    print("*Estimated cost based on a pricing snapshot — verify current rates "
          "at https://docs.claude.com/en/docs/about-claude/pricing")


# ---------------------------------------------------------------------------
# Main demo
# ---------------------------------------------------------------------------
def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: Set your ANTHROPIC_API_KEY environment variable first.")
        print('  export ANTHROPIC_API_KEY="sk-ant-..."')
        sys.exit(1)

    print("\n### PART 1: Intelligent Routing ###\n")
    for label, alert in [
        ("Simple alert", SIMPLE_ALERT),
        ("Moderate alert", MODERATE_ALERT),
        ("Severe alert", SEVERE_ALERT),
    ]:
        print(f"--- {label} ---")
        result = route_alert(alert)
        print(f"  Routed to: {result['model']}")
        print(f"  Output:\n  {result['text']}\n")

    print("\n### PART 2: Head-to-Head Model Comparison (severe alert) ###\n")
    results = compare_models_head_to_head(SEVERE_ALERT)
    print_comparison_table(results)

    print("\n### PART 3: Sample Outputs ###\n")
    for r in results:
        print(f"--- {r['label']} response ---")
        print(r["text"])
        print()


if __name__ == "__main__":
    main()
