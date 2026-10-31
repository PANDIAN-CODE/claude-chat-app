import time
import os
from typing import Callable, Iterator

import anthropic

API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MOCK_MODE = not API_KEY or API_KEY == "your_api_key_here"

client = None if MOCK_MODE else anthropic.Anthropic()
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
SYSTEM_PROMPT = "You are a helpful assistant. Answer clearly and concisely."

MAX_AGENT_ITERATIONS = 3

SEARCH_DOCUMENTS_TOOL = {
    "name": "search_documents",
    "description": (
        "Search the user's uploaded PDF documents for passages relevant to a query. "
        "Use this only when the user's question might be answered by content in "
        "their uploaded files - not for general knowledge questions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for in the user's documents",
            }
        },
        "required": ["query"],
    },
}

SearchFn = Callable[[str], list[dict]]


def _chunk_text(text: str) -> Iterator[str]:
    for word in text.split(" "):
        if word:
            yield word + " "
            time.sleep(0.01)


def _mock_agent_turn(last_message: str, search_fn: SearchFn | None) -> tuple[Iterator[str], list[dict]]:
    results = search_fn(last_message) if search_fn else []
    citations = [{"document_id": r["document_id"], "filename": r["filename"]} for r in results]
    reply = f'[Dummy response - no API key set] You said: "{last_message}"'

    def gen() -> Iterator[str]:
        for word in reply.split(" "):
            yield word + " "
            time.sleep(0.05)

    return gen(), citations


def _run_real_agent_turn(
    history: list[dict], search_fn: SearchFn | None
) -> tuple[Iterator[str], list[dict]]:
    messages = list(history)
    citations: list[dict] = []
    seen_documents: set[int] = set()

    try:
        for _ in range(MAX_AGENT_ITERATIONS):
            response = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=[SEARCH_DOCUMENTS_TOOL],
                messages=messages,
            )

            if response.stop_reason != "tool_use":
                final_text = "".join(
                    block.text for block in response.content if block.type == "text"
                )
                return _chunk_text(final_text), citations

            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                query = block.input.get("query", "") if isinstance(block.input, dict) else ""
                results = search_fn(query) if search_fn else []

                for r in results:
                    if r["document_id"] not in seen_documents:
                        seen_documents.add(r["document_id"])
                        citations.append(
                            {"document_id": r["document_id"], "filename": r["filename"]}
                        )

                content_text = "\n\n".join(r["content"] for r in results) or "No relevant documents found."
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": content_text}
                )

            messages.append({"role": "user", "content": tool_results})

        return _chunk_text("I looked through the documents but couldn't settle on an answer."), citations
    except anthropic.APIError as e:
        return iter([f"\n\n[Claude API error: {e}]"]), citations


def run_agent_turn(
    history: list[dict], search_fn: SearchFn | None = None
) -> tuple[Iterator[str], list[dict]]:
    """Run one agent turn: Claude decides whether to call the document search
    tool, we execute it and feed results back, looping until it gives a final
    answer. Returns (text_chunks, citations)."""
    if MOCK_MODE:
        return _mock_agent_turn(history[-1]["content"], search_fn)
    return _run_real_agent_turn(history, search_fn)
