"""
document_summarizer.py

Lesson 7 solution (Python, single file): a document summarizer built with
the Claude Agent SDK. Given a file path, it reads the document, analyzes
its content, and returns a structured summary (key points + prose
summary) -- using the SDK's built-in agentic loop rather than any
hand-written tool-use logic.

SETUP
-----
1. pip install claude-agent-sdk
2. export ANTHROPIC_API_KEY="sk-ant-..."
3. python document_summarizer.py

This will summarize the bundled sample "Orders API" doc (written to a
temp file on first run) and print the structured result.

NOTE ON MODEL NAMES: as with earlier lesson scripts, if you configure an
explicit model and it errors as "not found," check
https://docs.claude.com/en/docs/about-claude/models/overview for current
model IDs.
"""

import asyncio
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query


# ---------------------------------------------------------------------------
# Structured result type
# ---------------------------------------------------------------------------
@dataclass
class DocumentSummary:
    file_path: str
    key_points: list[str] = field(default_factory=list)
    summary: str = ""
    raw_response: str = ""


# ---------------------------------------------------------------------------
# Prompt design
# ---------------------------------------------------------------------------
def document_summarizer_prompt(file_path: str) -> str:
    """
    Builds the prompt sent to Claude. Three deliberate design choices:
      1. Persona -- "document summarization expert" -- for consistent
         tone and focus across runs.
      2. Numbered instructions -- explicit steps to follow.
      3. An EXACT required output format (markdown headings), so the
         response can be reliably parsed afterward instead of trying to
         regex-match free-form prose.
    """
    return f"""You are a document summarization expert working for a documentation team.

Your task:
1. Read the document located at: {file_path}
2. Identify the 3-6 most important key points in the document.
3. Write a concise summary of the document (2-4 sentences).

You MUST format your final response using EXACTLY this structure, with
these exact markdown headings, and nothing else before or after them:

## Key Points
- <first key point>
- <second key point>
- <third key point>
(add more bullet points as needed, up to 6)

## Summary
<your 2-4 sentence summary here>

Do not include any other headings, preamble, or commentary outside of
this structure."""


# ---------------------------------------------------------------------------
# Parsing the agent's raw markdown response into structured data
# ---------------------------------------------------------------------------
def parse_summary_response(raw_response: str) -> tuple[list[str], str]:
    key_points_match = re.search(
        r"##\s*Key Points\s*\n(.*?)(?=\n##\s*Summary|\Z)",
        raw_response,
        re.IGNORECASE | re.DOTALL,
    )
    summary_match = re.search(
        r"##\s*Summary\s*\n(.*)\Z",
        raw_response,
        re.IGNORECASE | re.DOTALL,
    )

    key_points: list[str] = []
    if key_points_match:
        for line in key_points_match.group(1).splitlines():
            line = line.strip()
            if line.startswith("-"):
                point = line.lstrip("-").strip()
                if point:
                    key_points.append(point)

    summary = summary_match.group(1).strip() if summary_match else ""

    return key_points, summary


# ---------------------------------------------------------------------------
# Core agent logic
# ---------------------------------------------------------------------------
async def summarize_document(file_path: str) -> DocumentSummary:
    """
    Summarizes a document at the given file path using the Claude Agent SDK.

    Step by step:
      1. Build a detailed prompt describing the task and required output
         format (see document_summarizer_prompt).
      2. Call query() with that prompt and options that set
         allowed_tools=["Read"] -- the ONLY capability this agent has is
         reading files. It cannot write, edit, or run shell commands.
         This is the Principle of Least Privilege in practice.
      3. query() returns an async iterator of messages. We iterate over
         it and watch for a ResultMessage with subtype "success" -- that
         is the agent's final answer.
      4. Once we have the final text, parse it into a structured
         DocumentSummary.

    We never write code to open the file, call a Read tool, or manage a
    loop of "did the model ask for a tool, execute it, feed back the
    result, repeat." All of that -- the full ReAct loop -- is handled
    internally by the SDK.
    """
    prompt = document_summarizer_prompt(file_path)

    options = ClaudeAgentOptions(
        allowed_tools=["Read"],
    )

    final_response_text = ""
    succeeded = False

    async for message in query(prompt=prompt, options=options):
        # Other message types (assistant text, tool-use events, system
        # messages) stream through here too. For this demo we only act
        # on the final ResultMessage, but in a real app you could log
        # each message here to observe the agent's step-by-step behavior.
        if isinstance(message, ResultMessage):
            if message.subtype == "success" and message.result is not None:
                final_response_text = message.result
                succeeded = True
            else:
                raise RuntimeError(
                    f"Agent run did not succeed (subtype: {message.subtype})"
                )
            break  # We have our final answer -- stop consuming the stream.

    if not succeeded:
        raise RuntimeError(
            f"summarize_document: no successful result received for {file_path}"
        )

    key_points, summary = parse_summary_response(final_response_text)

    return DocumentSummary(
        file_path=file_path,
        key_points=key_points,
        summary=summary,
        raw_response=final_response_text,
    )


# ---------------------------------------------------------------------------
# Sample document (written to a temp file so this is a single, runnable file)
# ---------------------------------------------------------------------------
SAMPLE_API_GUIDE = """# Orders API Guide

## Overview

The Orders API lets you create, retrieve, update, and cancel customer orders
for the platform. All endpoints require an authenticated API key passed in
the `Authorization` header.

## Authentication

Every request must include a bearer token:

    Authorization: Bearer YOUR_API_KEY

Requests without a valid key return a `401 Unauthorized` response.

## Endpoints

### Create an Order
`POST /orders` -- Creates a new order. Requires `customer_id`, `line_items`,
and `shipping_address`. Returns the order with a generated `order_id` and
`status` initialized to `pending`.

### Get an Order
`GET /orders/{order_id}` -- Retrieves full order details.

### Update an Order
`PATCH /orders/{order_id}` -- Updates mutable fields. Orders that have
already shipped cannot be modified and return `409 Conflict`.

### Cancel an Order
`DELETE /orders/{order_id}` -- Cancels an order if it hasn't shipped yet,
setting status to `cancelled` and triggering a refund if already paid.

## Rate Limits

100 requests per minute per API key. Exceeding this returns
`429 Too Many Requests` with a `Retry-After` header.

## Webhooks

Subscribe to order lifecycle events (`order.created`, `order.updated`,
`order.cancelled`, `order.shipped`) via a webhook URL in your dashboard.
Payloads are signed with HMAC-SHA256 and should be verified before use.
"""


def write_sample_file() -> str:
    """Writes the sample doc to a temp file and returns its path."""
    tmp_dir = tempfile.gettempdir()
    path = os.path.join(tmp_dir, "sample-api-guide.md")
    with open(path, "w") as f:
        f.write(SAMPLE_API_GUIDE)
    return path


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
async def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: Set your ANTHROPIC_API_KEY environment variable first.")
        print('  export ANTHROPIC_API_KEY="sk-ant-..."')
        sys.exit(1)

    sample_path = write_sample_file()
    print(f"Summarizing: {sample_path}\n")

    result = await summarize_document(sample_path)

    print("=== Key Points ===")
    if not result.key_points:
        print("(none parsed -- check raw_response below)")
    else:
        for i, point in enumerate(result.key_points, 1):
            print(f"{i}. {point}")

    print("\n=== Summary ===")
    print(result.summary or "(none parsed -- check raw_response below)")

    print("\n=== Raw Agent Response (for reference) ===")
    print(result.raw_response)


if __name__ == "__main__":
    asyncio.run(main())
