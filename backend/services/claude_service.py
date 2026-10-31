import time
import os
from typing import Callable, Iterator, TypedDict

import anthropic

from services.rag_service import format_search_results

API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MOCK_MODE = not API_KEY or API_KEY == "your_api_key_here"

client = None if MOCK_MODE else anthropic.Anthropic()
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
SYSTEM_PROMPT = "You are a helpful assistant. Answer clearly and concisely."

MAX_AGENT_ITERATIONS = 3

# $ per million tokens (input, output). Used only for cost estimates shown to
# the user - not billed by this app, just a transparency/LLMOps feature.
MODEL_PRICING = {
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-opus-5-5": (4.00, 20.00),
}
DEFAULT_PRICING = (2.00, 10.00)

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


class ImageInput(TypedDict):
    media_type: str
    data: str  # base64-encoded


class Usage(TypedDict):
    input_tokens: int
    output_tokens: int
    cost_usd: float


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    in_price, out_price = MODEL_PRICING.get(model, DEFAULT_PRICING)
    return (input_tokens / 1_000_000) * in_price + (output_tokens / 1_000_000) * out_price


def _empty_usage() -> Usage:
    return {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}


def _chunk_text(text: str) -> Iterator[str]:
    for word in text.split(" "):
        if word:
            yield word + " "
            time.sleep(0.01)


def _attach_image(history: list[dict], image: ImageInput | None) -> list[dict]:
    """Turn the last user message into a multimodal content block list if an
    image was attached, leaving every other message untouched."""
    if not image or not history:
        return history

    messages = list(history)
    last = messages[-1]
    if last["role"] != "user":
        return messages

    messages[-1] = {
        "role": "user",
        "content": [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image["media_type"],
                    "data": image["data"],
                },
            },
            {"type": "text", "text": last["content"]},
        ],
    }
    return messages


def _mock_agent_turn(
    last_message: str, search_fn: SearchFn | None
) -> tuple[Iterator[str], list[dict], Usage]:
    results = search_fn(last_message) if search_fn else []
    citations = [{"document_id": r["document_id"], "filename": r["filename"]} for r in results]
    reply = f'[Dummy response - no API key set] You said: "{last_message}"'

    def gen() -> Iterator[str]:
        for word in reply.split(" "):
            yield word + " "
            time.sleep(0.05)

    return gen(), citations, _empty_usage()


def _run_real_agent_turn(
    history: list[dict], search_fn: SearchFn | None, image: ImageInput | None
) -> tuple[Iterator[str], list[dict], Usage]:
    messages = _attach_image(history, image)
    citations: list[dict] = []
    seen_documents: set[int] = set()
    total_input_tokens = 0
    total_output_tokens = 0

    # Prompt caching: the system prompt is identical on every single call (here
    # and across users), so marking it cacheable means Anthropic reuses the
    # already-processed version instead of reprocessing it from scratch each
    # time - cheaper and faster for anything sent repeatedly unchanged.
    system = [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]

    try:
        for _ in range(MAX_AGENT_ITERATIONS):
            response = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=system,
                tools=[SEARCH_DOCUMENTS_TOOL],
                messages=messages,
            )
            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

            if response.stop_reason != "tool_use":
                final_text = "".join(
                    block.text for block in response.content if block.type == "text"
                )
                usage: Usage = {
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                    "cost_usd": estimate_cost(MODEL, total_input_tokens, total_output_tokens),
                }
                return _chunk_text(final_text), citations, usage

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

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": format_search_results(results),
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        usage = {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "cost_usd": estimate_cost(MODEL, total_input_tokens, total_output_tokens),
        }
        return (
            _chunk_text("I looked through the documents but couldn't settle on an answer."),
            citations,
            usage,
        )
    except anthropic.APIError as e:
        usage = {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "cost_usd": estimate_cost(MODEL, total_input_tokens, total_output_tokens),
        }
        return iter([f"\n\n[Claude API error: {e}]"]), citations, usage


def run_agent_turn(
    history: list[dict],
    search_fn: SearchFn | None = None,
    image: ImageInput | None = None,
) -> tuple[Iterator[str], list[dict], Usage]:
    """Run one agent turn: Claude decides whether to call the document search
    tool, we execute it and feed results back, looping until it gives a final
    answer. Returns (text_chunks, citations, usage)."""
    if MOCK_MODE:
        return _mock_agent_turn(history[-1]["content"], search_fn)
    return _run_real_agent_turn(history, search_fn, image)
