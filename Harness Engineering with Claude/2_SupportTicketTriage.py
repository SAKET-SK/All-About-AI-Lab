"""
Lesson 5 Exercise: Multi-Agent Support Ticket Triage System

SCENARIO
--------
A SaaS company receives 5,000+ support tickets/day. Manual triage takes
~4 hours on average and misses the 1-hour SLA for enterprise customers.
This script implements an automated multi-agent architecture:

    Ticket -> Triage Agent (Haiku)
           -> SLA Router (deterministic code, not an LLM)
           -> Specialist Agent: Billing / Technical / General (Sonnet)
              OR Escalation Agent (Opus) for high-stakes / SLA-critical cases
           -> QA Agent (Haiku) reviews the draft before it "sends"

SETUP
-----
1. pip install anthropic
2. export ANTHROPIC_API_KEY="sk-ant-..."
3. python support_ticket_triage.py

NOTE ON MODEL NAMES: see Lesson 3 script for the same caveat — check
https://docs.claude.com/en/docs/about-claude/models/overview if these
version strings have since changed.
"""

import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import anthropic

MODEL_HAIKU = "claude-haiku-4-5-20251001"
MODEL_SONNET = "claude-sonnet-5"
MODEL_OPUS = "claude-opus-4-8"

client = anthropic.Anthropic()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class Ticket:
    ticket_id: str
    customer_tier: str  # "enterprise" or "standard"
    channel: str        # "email", "chat", "api"
    subject: str
    body: str
    submitted_at: datetime
    # filled in as the ticket moves through the pipeline
    category: str = ""
    urgency: str = ""
    sla_deadline: datetime = None
    sla_breached: bool = False
    handled_by: str = ""
    draft_response: str = ""
    qa_verdict: str = ""


# SLA rules: (customer_tier) -> minutes allowed before response is due
SLA_MINUTES = {
    "enterprise": 60,   # 1-hour SLA
    "standard": 240,    # 4-hour SLA
}


# ---------------------------------------------------------------------------
# Helper: call a model, time it, return usage info alongside the text
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
    return {
        "text": response.content[0].text.strip(),
        "elapsed_sec": round(elapsed, 2),
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }


# ---------------------------------------------------------------------------
# AGENT 1: Triage Agent (Haiku) — cheap, fast classification
# ---------------------------------------------------------------------------
def triage_agent(ticket: Ticket) -> None:
    """
    Classifies category and urgency. Cheap classification task -> Haiku.
    Mutates the ticket in place.
    """
    system_prompt = (
        "You triage customer support tickets. Given a ticket subject and "
        "body, respond with EXACTLY two lines, nothing else:\n"
        "category: <billing|technical|account|other>\n"
        "urgency: <low|medium|high>"
    )
    user_message = f"Subject: {ticket.subject}\n\nBody: {ticket.body}"
    result = _call_model(MODEL_HAIKU, system_prompt, user_message, max_tokens=30)

    category, urgency = "other", "medium"
    for line in result["text"].splitlines():
        if line.lower().startswith("category:"):
            category = line.split(":", 1)[1].strip().lower()
        elif line.lower().startswith("urgency:"):
            urgency = line.split(":", 1)[1].strip().lower()

    ticket.category = category
    ticket.urgency = urgency
    print(f"  [Triage/Haiku] {ticket.ticket_id}: category={category}, "
          f"urgency={urgency} ({result['elapsed_sec']}s)")


# ---------------------------------------------------------------------------
# DETERMINISTIC COMPONENT: SLA Router — plain code, no model call
# ---------------------------------------------------------------------------
def sla_router(ticket: Ticket, now: datetime) -> str:
    """
    This is deliberately NOT an LLM call. Whether an SLA deadline has
    passed is a factual comparison, not a judgment call -- exactly the
    kind of thing that belongs in plain code, per the lesson's point
    about reserving models for genuine reasoning tasks.

    Returns the routing decision: "escalate" or "standard".
    """
    minutes_allowed = SLA_MINUTES.get(ticket.customer_tier, 240)
    ticket.sla_deadline = ticket.submitted_at + timedelta(minutes=minutes_allowed)
    ticket.sla_breached = now > ticket.sla_deadline

    # Escalate if: SLA already breached, OR enterprise + high urgency,
    # OR category is ambiguous ("other") -- fail safe toward more careful
    # handling, same principle as the router in Lesson 3.
    if ticket.sla_breached:
        return "escalate"
    if ticket.customer_tier == "enterprise" and ticket.urgency == "high":
        return "escalate"
    if ticket.category == "other":
        return "escalate"
    return "standard"


# ---------------------------------------------------------------------------
# AGENT 2a/2b: Specialist Agents (Sonnet) — balanced drafting
# ---------------------------------------------------------------------------
def specialist_agent(ticket: Ticket) -> None:
    """
    Drafts a response for routine billing/technical/account tickets.
    Balanced reasoning + writing task -> Sonnet.
    """
    role_context = {
        "billing": "You are a billing support specialist. Be precise about "
                   "charges, refunds, and invoices.",
        "technical": "You are a technical support engineer. Give clear, "
                     "step-by-step troubleshooting guidance.",
        "account": "You are an account support specialist. Handle login, "
                   "profile, and access questions.",
    }
    system_prompt = role_context.get(
        ticket.category,
        "You are a general customer support specialist."
    ) + " Write a helpful, concise reply (3-5 sentences) to the customer."

    user_message = f"Subject: {ticket.subject}\n\nBody: {ticket.body}"
    result = _call_model(MODEL_SONNET, system_prompt, user_message, max_tokens=250)

    ticket.draft_response = result["text"]
    ticket.handled_by = f"Specialist-Sonnet ({ticket.category})"
    print(f"  [{ticket.handled_by}] {ticket.ticket_id}: draft ready "
          f"({result['elapsed_sec']}s)")


# ---------------------------------------------------------------------------
# AGENT 3: Escalation Agent (Opus) — deep reasoning for high-stakes cases
# ---------------------------------------------------------------------------
def escalation_agent(ticket: Ticket) -> None:
    """
    Handles SLA-breached, high-urgency enterprise, or ambiguous tickets.
    Getting these wrong is costly -> use the most capable model.
    """
    system_prompt = (
        "You are a senior escalation specialist handling a high-priority "
        "or SLA-critical support ticket. Write a reply that: "
        "(1) acknowledges any delay or urgency directly, "
        "(2) gives a clear resolution or concrete next step, "
        "(3) offers a way to reach a human immediately if needed. "
        "Keep it professional and empathetic, 4-6 sentences."
    )
    user_message = (
        f"Customer tier: {ticket.customer_tier}\n"
        f"SLA breached: {ticket.sla_breached}\n"
        f"Subject: {ticket.subject}\n\nBody: {ticket.body}"
    )
    result = _call_model(MODEL_OPUS, system_prompt, user_message, max_tokens=350)

    ticket.draft_response = result["text"]
    ticket.handled_by = "Escalation-Opus"
    print(f"  [Escalation/Opus] {ticket.ticket_id}: draft ready "
          f"({result['elapsed_sec']}s)")


# ---------------------------------------------------------------------------
# AGENT 4: QA Agent (Haiku) — verification step before "sending"
# ---------------------------------------------------------------------------
def qa_agent(ticket: Ticket) -> None:
    """
    A lightweight check that the draft response is complete and on-tone
    before it goes out. This is the 'verification' component from
    Lesson 4 -- an external check rather than trusting the drafting
    agent's own confidence. Cheap check -> Haiku.
    """
    system_prompt = (
        "You review draft customer support replies. Respond with exactly "
        "one word: 'approve' if the reply is polite, on-topic, and "
        "addresses the customer's issue; 'revise' if it does not."
    )
    user_message = (
        f"Customer issue: {ticket.subject} - {ticket.body}\n\n"
        f"Draft reply: {ticket.draft_response}"
    )
    result = _call_model(MODEL_HAIKU, system_prompt, user_message, max_tokens=10)
    ticket.qa_verdict = result["text"].strip().lower()
    print(f"  [QA/Haiku] {ticket.ticket_id}: verdict={ticket.qa_verdict} "
          f"({result['elapsed_sec']}s)")


# ---------------------------------------------------------------------------
# ORCHESTRATOR: ties the whole pipeline together for one ticket
# ---------------------------------------------------------------------------
def process_ticket(ticket: Ticket, now: datetime) -> Ticket:
    print(f"\n--- Processing {ticket.ticket_id} ({ticket.customer_tier}) ---")

    triage_agent(ticket)
    route = sla_router(ticket, now)
    print(f"  [SLA Router/code] {ticket.ticket_id}: route={route}, "
          f"sla_deadline={ticket.sla_deadline.strftime('%H:%M')}, "
          f"breached={ticket.sla_breached}")

    if route == "escalate":
        escalation_agent(ticket)
    else:
        specialist_agent(ticket)

    qa_agent(ticket)
    return ticket


# ---------------------------------------------------------------------------
# Sample batch of tickets covering different scenarios
# ---------------------------------------------------------------------------
def build_sample_tickets():
    base_time = datetime(2026, 7, 29, 9, 0)
    return [
        Ticket(
            ticket_id="T-1001",
            customer_tier="standard",
            channel="email",
            subject="How do I update my card on file?",
            body="I need to change the credit card linked to my subscription.",
            submitted_at=base_time,
        ),
        Ticket(
            ticket_id="T-1002",
            customer_tier="enterprise",
            channel="chat",
            subject="API returning 500 errors since this morning",
            body="Our integration has been failing since 8am with server "
                 "errors on the /v2/orders endpoint. This is blocking our "
                 "checkout flow in production.",
            submitted_at=base_time,
        ),
        Ticket(
            ticket_id="T-1003",
            customer_tier="enterprise",
            channel="email",
            subject="Still waiting - urgent",
            body="I submitted this ticket about our data export failing "
                 "over two hours ago and haven't heard back. This is time "
                 "sensitive for our board meeting.",
            submitted_at=base_time - timedelta(hours=2, minutes=15),  # already breached
        ),
        Ticket(
            ticket_id="T-1004",
            customer_tier="standard",
            channel="api",
            subject="General feedback",
            body="Just wanted to say the new dashboard redesign looks great, "
                 "not sure if this is the right place to send this.",
            submitted_at=base_time,
        ),
    ]


def print_summary(tickets):
    print("\n" + "=" * 90)
    print(f"{'Ticket':<9}{'Tier':<12}{'Category':<11}{'Urgency':<9}"
          f"{'Handled By':<22}{'SLA Breach':<12}{'QA':<10}")
    print("-" * 90)
    for t in tickets:
        print(f"{t.ticket_id:<9}{t.customer_tier:<12}{t.category:<11}"
              f"{t.urgency:<9}{t.handled_by:<22}{str(t.sla_breached):<12}{t.qa_verdict:<10}")
    print("=" * 90)


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: Set your ANTHROPIC_API_KEY environment variable first.")
        sys.exit(1)

    now = datetime(2026, 7, 29, 9, 20)  # simulated "current time"
    tickets = build_sample_tickets()

    for ticket in tickets:
        process_ticket(ticket, now)

    print_summary(tickets)

    print("\n### Sample drafted responses ###\n")
    for t in tickets:
        print(f"--- {t.ticket_id} ({t.handled_by}) ---")
        print(t.draft_response)
        print()


if __name__ == "__main__":
    main()
