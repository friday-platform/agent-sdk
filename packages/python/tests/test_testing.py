"""Tests for the public friday_agent_sdk.testing module."""

import pytest

from friday_agent_sdk import (
    AgentContext,
    HttpProtocol,
    HttpResponse,
    LlmProtocol,
    LlmResponse,
    SessionData,
    StreamProtocol,
    ToolCallError,
    ToolDefinition,
    ToolsProtocol,
    make_test_context,
)
from friday_agent_sdk.testing import FakeHttp, FakeLlm, FakeStream, FakeTools


def _llm_response(text: str = "ok") -> LlmResponse:
    return LlmResponse(
        text=text,
        object=None,
        model="fake",
        usage={},
        finish_reason="stop",
    )


class TestMakeTestContext:
    def test_zero_arg_returns_agent_context(self):
        ctx = make_test_context()
        assert isinstance(ctx, AgentContext)

    def test_zero_arg_capabilities_satisfy_protocols(self):
        ctx = make_test_context()
        assert isinstance(ctx.llm, LlmProtocol)
        assert isinstance(ctx.http, HttpProtocol)
        assert isinstance(ctx.tools, ToolsProtocol)
        assert isinstance(ctx.stream, StreamProtocol)

    def test_zero_arg_capabilities_are_fakes(self):
        ctx = make_test_context()
        assert isinstance(ctx.llm, FakeLlm)
        assert isinstance(ctx.http, FakeHttp)
        assert isinstance(ctx.tools, FakeTools)
        assert isinstance(ctx.stream, FakeStream)

    def test_passes_through_simple_fields(self):
        session = SessionData(
            id="s1",
            workspace_id="w1",
            user_id="u1",
            datetime="2026-01-01T00:00:00Z",
        )
        ctx = make_test_context(
            env={"FOO": "bar"},
            config={"k": 1},
            session=session,
            output_schema={"type": "object"},
        )
        assert ctx.env == {"FOO": "bar"}
        assert ctx.config == {"k": 1}
        assert ctx.session is session
        assert ctx.output_schema == {"type": "object"}

    def test_overrides_individual_capabilities(self):
        my_llm = FakeLlm()
        my_http = FakeHttp()
        my_tools = FakeTools()
        my_stream = FakeStream()
        ctx = make_test_context(
            llm=my_llm,
            http=my_http,
            tools=my_tools,
            stream=my_stream,
        )
        assert ctx.llm is my_llm
        assert ctx.http is my_http
        assert ctx.tools is my_tools
        assert ctx.stream is my_stream

    def test_accepts_arbitrary_protocol_implementations(self):
        """Any object with the right method shape satisfies the field type.

        Verifies the structural-typing claim: users don't need to subclass
        the SDK's Fake* helpers, they can drop in a hand-written mock.
        """

        class HandRolledLlm:
            def generate(self, messages, **kwargs):
                return _llm_response("from-handrolled")

            def generate_object(self, messages, schema, **kwargs):
                return _llm_response("from-handrolled")

        ctx = make_test_context(llm=HandRolledLlm())  # type: ignore[arg-type]
        assert ctx.llm.generate(messages=[{"role": "user", "content": "x"}]).text == "from-handrolled"


class TestFakeLlm:
    def test_default_returns_empty_response(self):
        llm = FakeLlm()
        result = llm.generate(messages=[{"role": "user", "content": "hi"}])
        assert result.text == ""
        assert result.model == "fake"
        assert result.finish_reason == "stop"

    def test_records_calls(self):
        llm = FakeLlm()
        llm.generate(messages=[{"role": "user", "content": "hi"}], model="m1")
        llm.generate_object(
            messages=[{"role": "user", "content": "hi"}],
            schema={"type": "object"},
        )
        assert len(llm.calls) == 2
        assert llm.calls[0]["method"] == "generate"
        assert llm.calls[0]["model"] == "m1"
        assert llm.calls[1]["method"] == "generate_object"
        assert llm.calls[1]["schema"] == {"type": "object"}

    def test_canned_response_queue_is_fifo(self):
        llm = FakeLlm(responses=[_llm_response("a"), _llm_response("b")])
        assert llm.generate(messages=[]).text == "a"
        assert llm.generate(messages=[]).text == "b"

    def test_falls_back_to_empty_when_queue_exhausted(self):
        llm = FakeLlm(responses=[_llm_response("only")])
        assert llm.generate(messages=[]).text == "only"
        assert llm.generate(messages=[]).text == ""

    def test_on_generate_callable_takes_precedence(self):
        captured: list = []

        def handler(**kwargs):
            captured.append(kwargs)
            return _llm_response("dynamic")

        llm = FakeLlm(responses=[_llm_response("queued")], on_generate=handler)
        result = llm.generate(messages=[{"role": "user", "content": "hi"}], model="m1")
        assert result.text == "dynamic"
        assert len(captured) == 1
        assert captured[0]["model"] == "m1"


class TestFakeHttp:
    def test_default_returns_200_empty(self):
        http = FakeHttp()
        result = http.fetch("https://example.com")
        assert result.status == 200
        assert result.body == ""

    def test_records_calls(self):
        http = FakeHttp()
        http.fetch(
            "https://example.com/api",
            method="POST",
            headers={"X": "1"},
            body="payload",
        )
        assert len(http.calls) == 1
        assert http.calls[0]["url"] == "https://example.com/api"
        assert http.calls[0]["method"] == "POST"
        assert http.calls[0]["headers"] == {"X": "1"}
        assert http.calls[0]["body"] == "payload"

    def test_canned_responses_fifo(self):
        http = FakeHttp(
            responses=[
                HttpResponse(status=201, headers={}, body="a"),
                HttpResponse(status=404, headers={}, body="b"),
            ]
        )
        assert http.fetch("https://example.com").status == 201
        assert http.fetch("https://example.com").status == 404
        # Queue exhausted → empty default
        assert http.fetch("https://example.com").status == 200

    def test_on_fetch_callable(self):
        def handler(url, **kwargs):
            return HttpResponse(status=418, headers={}, body=url)

        http = FakeHttp(on_fetch=handler)
        result = http.fetch("https://teapot")
        assert result.status == 418
        assert result.body == "https://teapot"


class TestFakeTools:
    def test_list_returns_provided_tools(self):
        tool = ToolDefinition(name="echo", description="d", input_schema={})
        tools = FakeTools(tools=[tool])
        assert tools.list() == [tool]

    def test_call_dispatches_to_handler(self):
        tools = FakeTools(handlers={"add": lambda args: {"sum": args["a"] + args["b"]}})
        result = tools.call("add", {"a": 1, "b": 2})
        assert result == {"sum": 3}

    def test_call_records(self):
        tools = FakeTools(handlers={"echo": lambda args: args})
        tools.call("echo", {"x": 1})
        tools.call("echo", {"y": 2})
        assert tools.calls == [("echo", {"x": 1}), ("echo", {"y": 2})]

    def test_unhandled_tool_raises(self):
        tools = FakeTools()
        with pytest.raises(ToolCallError, match="no handler registered"):
            tools.call("missing", {})


class TestFakeStream:
    def test_emit_records_event(self):
        stream = FakeStream()
        stream.emit("custom-event", {"k": "v"})
        assert stream.events == [("custom-event", {"k": "v"})]

    def test_progress_records_canonical_event(self):
        stream = FakeStream()
        stream.progress("doing thing", tool_name="my-tool")
        assert stream.events == [("data-tool-progress", {"toolName": "my-tool", "content": "doing thing"})]

    def test_progress_defaults_tool_name_to_agent(self):
        stream = FakeStream()
        stream.progress("step")
        assert stream.events[0][1] == {"toolName": "agent", "content": "step"}

    def test_intent_records_canonical_event(self):
        stream = FakeStream()
        stream.intent("planning to clone repo")
        assert stream.events == [("data-intent", {"content": "planning to clone repo"})]
