from types import SimpleNamespace

import services.claude_service as claude_service


class FakeTextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class FakeToolUseBlock:
    type = "tool_use"

    def __init__(self, id_, input_):
        self.id = id_
        self.input = input_


class FakeResponse:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content


class FakeMessages:
    def __init__(self, responses):
        self._responses = iter(responses)

    def create(self, **kwargs):
        return next(self._responses)


class FakeClient:
    def __init__(self, responses):
        self.messages = FakeMessages(responses)


def _patch_client(monkeypatch, responses):
    monkeypatch.setattr(claude_service, "MOCK_MODE", False)
    monkeypatch.setattr(claude_service, "client", FakeClient(responses))


def test_agent_answers_directly_without_tool_call(monkeypatch):
    _patch_client(
        monkeypatch,
        [FakeResponse("end_turn", [FakeTextBlock("Paris is the capital of France.")])],
    )

    search_calls = []
    chunks, citations = claude_service.run_agent_turn(
        [{"role": "user", "content": "What is the capital of France?"}],
        search_fn=lambda q: search_calls.append(q) or [],
    )

    assert "".join(chunks).strip() == "Paris is the capital of France."
    assert citations == []
    assert search_calls == []  # tool was never called - no document search needed


def test_agent_calls_search_tool_then_answers(monkeypatch):
    _patch_client(
        monkeypatch,
        [
            FakeResponse(
                "tool_use",
                [FakeToolUseBlock("tool_1", {"query": "vacation policy"})],
            ),
            FakeResponse(
                "end_turn",
                [FakeTextBlock("You get 15 paid vacation days per year [policy.pdf].")],
            ),
        ],
    )

    def fake_search(query):
        assert query == "vacation policy"
        return [{"document_id": 1, "filename": "policy.pdf", "content": "15 paid days off"}]

    chunks, citations = claude_service.run_agent_turn(
        [{"role": "user", "content": "How many vacation days do I get?"}],
        search_fn=fake_search,
    )

    assert "15 paid vacation days" in "".join(chunks)
    assert citations == [{"document_id": 1, "filename": "policy.pdf"}]


def test_agent_stops_after_max_iterations(monkeypatch):
    looping_response = FakeResponse(
        "tool_use", [FakeToolUseBlock("tool_x", {"query": "anything"})]
    )
    _patch_client(
        monkeypatch,
        [looping_response] * claude_service.MAX_AGENT_ITERATIONS,
    )

    chunks, citations = claude_service.run_agent_turn(
        [{"role": "user", "content": "question"}],
        search_fn=lambda q: [],
    )

    text = "".join(chunks)
    assert "couldn't settle" in text
    assert citations == []
