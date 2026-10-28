import json

import httpx
import pytest

from app.services.llm_client import (
    Endpoint,
    GenerationParameters,
    LLMError,
    OpenAICompatibleClient,
    Progress,
    ToolCall,
    normalise_base_url,
    parse_completion,
)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://127.0.0.1:11434", "http://127.0.0.1:11434"),
        ("http://127.0.0.1:11434/", "http://127.0.0.1:11434"),
        ("http://127.0.0.1:1234/v1", "http://127.0.0.1:1234"),
        ("http://127.0.0.1:1234/v1/", "http://127.0.0.1:1234"),
    ],
)
def test_base_url_is_normalised(url: str, expected: str):
    assert normalise_base_url(url) == expected


def test_parse_completion_with_tool_calls_and_usage():
    completion = parse_completion(
        {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "function": {"name": "read_file", "arguments": '{"path": "a.py"}'},
                            },
                            {"function": {"name": "list_files", "arguments": {"unused": True}}},
                        ],
                    }
                }
            ],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30},
        }
    )
    assert completion.content is None
    assert completion.tool_calls[0].id == "call_1"
    assert completion.tool_calls[1].id.startswith("call_")
    assert json.loads(completion.tool_calls[1].arguments) == {"unused": True}
    assert (completion.prompt_tokens, completion.completion_tokens) == (120, 30)


def test_parse_completion_without_usage():
    completion = parse_completion({"choices": [{"message": {"content": "Done."}}]})
    assert completion.content == "Done."
    assert completion.tool_calls == ()
    assert completion.prompt_tokens is None


def test_reasoning_field_is_captured():
    completion = parse_completion(
        {"choices": [{"message": {"content": "Answer.", "reasoning_content": "  Think first.  "}}]}
    )
    assert completion.content == "Answer."
    assert completion.reasoning == "Think first."


def test_inline_think_blocks_are_separated_from_content():
    completion = parse_completion(
        {"choices": [{"message": {"content": "<think>\nCheck the loop.\n</think>\n\nFixed."}}]}
    )
    assert completion.content == "Fixed."
    assert completion.reasoning == "Check the loop."


def test_unterminated_think_block_is_treated_as_reasoning():
    completion = parse_completion({"choices": [{"message": {"content": "<think>Still going"}}]})
    assert completion.content is None
    assert completion.reasoning == "Still going"


def _client(handler) -> OpenAICompatibleClient:
    endpoint = Endpoint(base_url="http://runtime.test/v1", model="test", timeout_seconds=5)
    return OpenAICompatibleClient(endpoint, transport=httpx.MockTransport(handler))


def _event_stream(*chunks: dict) -> bytes:
    events = [f"data: {json.dumps(chunk)}\n\n" for chunk in chunks]
    return ("".join(events) + "data: [DONE]\n\n").encode()


PARAMETERS = GenerationParameters(temperature=0.2, top_p=0.95, max_tokens=256)


def test_streamed_completion_is_assembled_and_reports_progress():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["stream"] is True
        assert request.url.path == "/v1/chat/completions"
        body = _event_stream(
            {"choices": [{"delta": {"reasoning_content": "Look at "}}]},
            {"choices": [{"delta": {"reasoning_content": "line 44."}}]},
            {"choices": [{"delta": {"content": "Found it."}}]},
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_7",
                                    "function": {"name": "report_bug", "arguments": '{"line"'},
                                }
                            ]
                        }
                    }
                ]
            },
            {
                "choices": [
                    {"delta": {"tool_calls": [{"index": 0, "function": {"arguments": ": 44}"}}]}}
                ]
            },
            {"choices": [], "usage": {"prompt_tokens": 900, "completion_tokens": 40}},
        )
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    progress: list[Progress] = []
    completion = _client(handler).complete([], [], PARAMETERS, on_progress=progress.append)

    assert completion.reasoning == "Look at line 44."
    assert completion.content == "Found it."
    assert completion.tool_calls == (ToolCall("call_7", "report_bug", '{"line": 44}'),)
    assert (completion.prompt_tokens, completion.completion_tokens) == (900, 40)
    assert progress[-1] == Progress(reasoning="Look at line 44.", content="Found it.")


def test_non_streaming_response_is_accepted():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "Plain."}}]})

    assert _client(handler).complete([], [], PARAMETERS).content == "Plain."


def test_runtime_errors_are_raised():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={"error": {"message": "fetch failed"}})

    with pytest.raises(LLMError, match="HTTP 502"):
        _client(handler).complete([], [], PARAMETERS)


def test_error_events_in_the_stream_are_raised():
    def handler(_request: httpx.Request) -> httpx.Response:
        body = _event_stream({"error": {"message": "context length exceeded"}})
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    with pytest.raises(LLMError, match="context length exceeded"):
        _client(handler).complete([], [], PARAMETERS)
