"""Integration-flavoured tests for build_context() and _nats_call.

These exercise the real threading model used by the bridge: a background
event loop services NATS coroutines while the agent handler runs synchronously
on a worker thread and blocks on `_nats_call`. The NATS client is async-mocked
so no broker is required.

Wire format reference (friday-studio/apps/atlasd/src/capability-handlers.ts):

    caps.<sid>.llm.generate  -> JSON LlmResponse OR {"error": str}
    caps.<sid>.http.fetch    -> JSON HttpResponse OR {"error": str}
    caps.<sid>.tools.call    -> JSON tool result OR {"error": str}
    caps.<sid>.tools.list    -> {"tools": [...]} OR {"error": str}
"""

import asyncio
import json
import threading
from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from friday_agent_sdk._context import _nats_call, build_context
from friday_agent_sdk._types import HttpError, LlmError, ToolCallError


@pytest.fixture
def loop_in_thread() -> Iterator[asyncio.AbstractEventLoop]:
    """A real event loop running on a background thread, like the bridge does."""
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:
        yield loop
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=1)
        loop.close()


def _msg(payload: dict | str) -> SimpleNamespace:
    """Mimic nats.aio.msg.Msg — only `.data` is used by build_context."""
    body = payload if isinstance(payload, str) else json.dumps(payload)
    return SimpleNamespace(data=body.encode())


class TestNatsCallTypingPreserved:
    """_nats_call must forward whatever the coroutine returns, not coerce to str.

    Regression test for the old `-> str` annotation that hid a typing bug;
    the function is now generic over the coroutine's return type.
    """

    def test_returns_int(self, loop_in_thread):
        async def coro() -> int:
            return 42

        assert _nats_call(coro(), loop_in_thread, timeout=2) == 42

    def test_returns_list(self, loop_in_thread):
        async def coro() -> list[str]:
            return ["a", "b", "c"]

        assert _nats_call(coro(), loop_in_thread, timeout=2) == ["a", "b", "c"]

    def test_returns_dict(self, loop_in_thread):
        async def coro() -> dict[str, int]:
            return {"x": 1}

        assert _nats_call(coro(), loop_in_thread, timeout=2) == {"x": 1}

    def test_propagates_exception(self, loop_in_thread):
        async def coro() -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            _nats_call(coro(), loop_in_thread, timeout=2)


class TestLlmGenerateRoundTrip:
    def test_success(self, loop_in_thread):
        nc = MagicMock()
        nc.request = AsyncMock(
            return_value=_msg(
                {
                    "text": "hello",
                    "model": "test-model",
                    "usage": {"input_tokens": 1, "output_tokens": 2},
                    "finish_reason": "stop",
                }
            )
        )

        ctx = build_context({"llm_config": {"model": "test"}}, nc, "sess-1", loop_in_thread)
        resp = ctx.llm.generate(messages=[{"role": "user", "content": "hi"}], model="test-model")

        assert resp.text == "hello"
        assert resp.model == "test-model"
        assert resp.finish_reason == "stop"

        nc.request.assert_called_once()
        args, kwargs = nc.request.call_args
        assert args[0] == "caps.sess-1.llm.generate"
        assert kwargs["timeout"] == 120
        # Payload is the JSON-encoded request the SDK built for the daemon.
        sent = json.loads(args[1].decode())
        assert sent["messages"] == [{"role": "user", "content": "hi"}]
        assert sent["model"] == "test-model"

    def test_error_path(self, loop_in_thread):
        nc = MagicMock()
        nc.request = AsyncMock(return_value=_msg({"error": "rate limited"}))

        ctx = build_context({}, nc, "sess-1", loop_in_thread)
        with pytest.raises(LlmError, match="rate limited"):
            ctx.llm.generate(messages=[{"role": "user", "content": "x"}], model="test")


class TestHttpFetchRoundTrip:
    def test_success(self, loop_in_thread):
        nc = MagicMock()
        nc.request = AsyncMock(
            return_value=_msg({"status": 200, "headers": {"x": "y"}, "body": "ok"}),
        )

        ctx = build_context({}, nc, "sess-1", loop_in_thread)
        resp = ctx.http.fetch("https://example.com/foo", method="GET")

        assert resp.status == 200
        assert resp.headers == {"x": "y"}
        assert resp.body == "ok"

        nc.request.assert_called_once()
        args, kwargs = nc.request.call_args
        assert args[0] == "caps.sess-1.http.fetch"
        assert kwargs["timeout"] == 60
        sent = json.loads(args[1].decode())
        assert sent["url"] == "https://example.com/foo"
        assert sent["method"] == "GET"

    def test_error_path(self, loop_in_thread):
        nc = MagicMock()
        nc.request = AsyncMock(return_value=_msg({"error": "dns failure"}))

        ctx = build_context({}, nc, "sess-1", loop_in_thread)
        with pytest.raises(HttpError, match="dns failure"):
            ctx.http.fetch("https://fail.example.com", method="GET")


class TestToolsRoundTrip:
    def test_call_success(self, loop_in_thread):
        nc = MagicMock()
        nc.request = AsyncMock(return_value=_msg({"result": "value", "n": 3}))

        ctx = build_context({}, nc, "sess-1", loop_in_thread)
        out = ctx.tools.call("my-tool", {"x": 1})

        assert out == {"result": "value", "n": 3}
        args, kwargs = nc.request.call_args
        assert args[0] == "caps.sess-1.tools.call"
        assert kwargs["timeout"] == 60
        sent = json.loads(args[1].decode())
        assert sent == {"name": "my-tool", "args": {"x": 1}}

    def test_call_error(self, loop_in_thread):
        nc = MagicMock()
        nc.request = AsyncMock(return_value=_msg({"error": "tool not found"}))

        ctx = build_context({}, nc, "sess-1", loop_in_thread)
        with pytest.raises(ToolCallError, match="tool not found"):
            ctx.tools.call("missing", {})

    def test_list_success(self, loop_in_thread):
        nc = MagicMock()
        nc.request = AsyncMock(
            return_value=_msg(
                {
                    "tools": [
                        {
                            "name": "t1",
                            "description": "d1",
                            "inputSchema": {"type": "object", "properties": {}},
                        },
                        {"name": "t2", "description": "d2", "inputSchema": {}},
                    ]
                }
            )
        )

        ctx = build_context({}, nc, "sess-1", loop_in_thread)
        tools = ctx.tools.list()

        assert len(tools) == 2
        assert tools[0].name == "t1"
        assert tools[0].description == "d1"
        assert tools[0].input_schema == {"type": "object", "properties": {}}
        assert tools[1].name == "t2"
        assert tools[1].input_schema == {}

        args, kwargs = nc.request.call_args
        assert args[0] == "caps.sess-1.tools.list"
        assert kwargs["timeout"] == 10

    def test_list_error_returns_empty(self, loop_in_thread):
        nc = MagicMock()
        nc.request = AsyncMock(return_value=_msg({"error": "boom"}))

        ctx = build_context({}, nc, "sess-1", loop_in_thread)
        assert ctx.tools.list() == []
