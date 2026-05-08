"""Tests for build_context() — constructs AgentContext from raw JSON dict."""

from unittest.mock import MagicMock

from friday_agent_sdk._context import build_context
from friday_agent_sdk._types import AgentContext, SessionData


def _build(raw: dict) -> AgentContext:
    """Convenience wrapper — mocks NATS and loop since build_context only stores them."""
    return build_context(raw, MagicMock(), "sess-1", MagicMock())


class TestBuildContext:
    def test_full_context(self):
        raw = {
            "env": {"API_KEY": "secret"},
            "config": {"temperature": 0.7},
            "input": {"config": {"upstream": {"summary": "ready"}}},
            "session": {
                "id": "sess-1",
                "workspace_id": "ws-1",
                "user_id": "user-1",
                "datetime": "2026-01-01T00:00:00Z",
            },
            "output_schema": {"type": "object"},
        }
        ctx = _build(raw)
        assert isinstance(ctx, AgentContext)
        assert ctx.env == {"API_KEY": "secret"}
        assert ctx.config == {"temperature": 0.7}
        assert ctx.input.get("upstream") == {"summary": "ready"}
        assert isinstance(ctx.session, SessionData)
        assert ctx.session.id == "sess-1"
        assert ctx.session.workspace_id == "ws-1"
        assert ctx.output_schema == {"type": "object"}

    def test_empty_context(self):
        ctx = _build({})
        assert ctx.env == {}
        assert ctx.config == {}
        assert ctx.input.get() == {}
        assert ctx.session is None
        assert ctx.output_schema is None

    def test_partial_context(self):
        raw = {"env": {"FOO": "bar"}}
        ctx = _build(raw)
        assert ctx.env == {"FOO": "bar"}
        assert ctx.config == {}
        assert ctx.session is None

    def test_session_fields(self):
        raw = {
            "session": {
                "id": "s1",
                "workspace_id": "w1",
                "user_id": "u1",
                "datetime": "2026-04-02T12:00:00Z",
            }
        }
        ctx = _build(raw)
        assert ctx.session is not None
        assert ctx.session.user_id == "u1"
        assert ctx.session.datetime == "2026-04-02T12:00:00Z"

    def test_llm_is_initialized(self):
        """With NATS context, llm is always initialized."""
        ctx = _build({})
        assert ctx.llm is not None

    def test_http_is_initialized(self):
        """With NATS context, http is always initialized."""
        ctx = _build({})
        assert ctx.http is not None

    def test_stream_is_initialized(self):
        """stream is always initialized (no-op stub or NATS-backed)."""
        ctx = _build({})
        assert ctx.stream is not None

    def test_tools_are_initialized(self):
        """tools are always initialized with NATS context."""
        ctx = _build({})
        assert ctx.tools is not None

    def test_llm_config_read_from_raw(self):
        """llm_config key in raw dict is stored for LLM builder."""
        raw = {"llm_config": {"model": "anthropic:claude-haiku-4-5"}}
        ctx = _build(raw)
        assert ctx.llm._config == {"model": "anthropic:claude-haiku-4-5"}
