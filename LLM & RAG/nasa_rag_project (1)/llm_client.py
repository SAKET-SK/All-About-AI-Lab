from typing import Dict, List
from openai import OpenAI


def generate_response(
    openai_key: str,
    user_message: str,
    context: str,
    conversation_history: List[Dict],
    model: str = "gpt-3.5-turbo",
) -> str:
    """Generate response using OpenAI with context"""

    # TODO: Define system prompt
    system_prompt = """You are an expert NASA mission analyst and historian with deep knowledge 
of all NASA space missions, including Apollo 11, Apollo 13, and the Challenger disaster.

Your role is to answer questions accurately using ONLY the context provided to you.
Always cite the source of your information (e.g., "According to [source]...").

Rules you must follow:
- Base your answers strictly on the retrieved context provided below.
- If the context does not contain enough information to answer the question, clearly say:
  "I don't have enough information in the retrieved documents to answer that accurately."
- Never fabricate facts, dates, names, or events.
- When citing, reference the mission name and document source from the metadata.
- Be concise, factual, and professional."""

    # TODO: Set context in messages
    # Inject the retrieved context as a system-level message so the LLM
    # always sees it at the top of the conversation, separate from history.
    context_message = {
        "role": "system",
        "content": (
            f"{system_prompt}\n\n"
            "--- RETRIEVED CONTEXT ---\n"
            f"{context if context else 'No relevant context was retrieved for this query.'}\n"
            "--- END OF CONTEXT ---\n\n"
            "Answer the user's question using only the context above."
        ),
    }

    # TODO: Add chat history
    # Build the full message list:
    #   [system+context]  +  [prior turns]  +  [current user message]
    messages = [context_message]

    for turn in conversation_history:
        # Each turn must have "role" and "content" keys
        if "role" in turn and "content" in turn:
            messages.append({"role": turn["role"], "content": turn["content"]})

    # Append the current user question
    messages.append({"role": "user", "content": user_message})

    # TODO: Create OpenAI Client
    client = OpenAI(api_key=openai_key)

    # TODO: Send request to OpenAI
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,       # Low temperature for factual, grounded answers
        max_tokens=1024,
    )

    # TODO: Return response
    return completion.choices[0].message.content
