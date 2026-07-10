from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _FakeResponse:
    status_code = 200

    def __init__(self, deltas: list[dict[str, object]]) -> None:
        self._deltas = deltas

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def aiter_lines(self):
        for delta in self._deltas:
            yield f"data: {json.dumps({'choices': [{'delta': delta}]})}"
        yield "data: [DONE]"


class _FakeClient:
    def __init__(self, responses: list[_FakeResponse], **_kwargs: object) -> None:
        self._responses = responses

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    def stream(self, *_args: object, **_kwargs: object) -> _FakeResponse:
        return self._responses.pop(0)


class ToolLoopTest(unittest.IsolatedAsyncioTestCase):
    async def test_tool_loop_can_continue_beyond_eight_rounds(self) -> None:
        from app.llm import stream_openai_compatible

        responses = [
            _FakeResponse(
                [
                    {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": f"call_{index}",
                                "type": "function",
                                "function": {"name": "unknown", "arguments": "{}"},
                            }
                        ]
                    }
                ]
            )
            for index in range(1, 10)
        ]
        responses.append(_FakeResponse([{"content": "done"}]))
        settings = SimpleNamespace(
            model_base_url="https://model.example/v1",
            model_api_key="test-key",
            model_name="test-model",
            request_timeout_seconds=30,
        )

        with (
            patch("app.llm.get_settings", return_value=settings),
            patch("app.llm.httpx.AsyncClient", side_effect=lambda **kwargs: _FakeClient(responses, **kwargs)),
        ):
            events = [
                event
                async for event in stream_openai_compatible(
                    [{"role": "user", "content": "keep working"}],
                    project_slug=None,
                )
            ]

        self.assertEqual(sum(event["type"] == "tool_result" for event in events), 9)
        self.assertIn({"type": "text_delta", "content": "done"}, events)
        self.assertFalse(any(event["type"] == "error" for event in events))


if __name__ == "__main__":
    unittest.main()
