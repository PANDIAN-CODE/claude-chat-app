import os
import time
from typing import Iterator

import anthropic

API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MOCK_MODE = not API_KEY or API_KEY == "your_api_key_here"

client = None if MOCK_MODE else anthropic.Anthropic()
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
SYSTEM_PROMPT = "You are a helpful assistant. Answer clearly and concisely."


def _mock_stream(last_message: str) -> Iterator[str]:
    reply = f'[Dummy response - no API key set] You said: "{last_message}"'
    for word in reply.split(" "):
        yield word + " "
        time.sleep(0.05)


def _claude_stream(messages: list[dict], system_prompt: str) -> Iterator[str]:
    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text
    except anthropic.APIError as e:
        yield f"\n\n[Claude API error: {e}]"


def stream_reply(history: list[dict], extra_system: str = "") -> Iterator[str]:
    if MOCK_MODE:
        return _mock_stream(history[-1]["content"])
    return _claude_stream(history, SYSTEM_PROMPT + extra_system)
