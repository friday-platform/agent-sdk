"""Tests for the NATS bridge — result serialization and metadata construction."""

import asyncio
import json
import os
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from friday_agent_sdk._bridge import (
    _run_async,
    _serialize_dataclass_camel,
    _serialize_extras,
    _serialize_result,
    _to_camel,
    _validate_async,
)
from friday_agent_sdk._registry import (
    AgentRegistration,
    _reset_registry,
    register_agent,
)
from friday_agent_sdk._result import AgentExtras, ArtifactRef, OutlineRef, err, ok


def _mock_msg(prompt: str, context_raw: dict):
    msg = MagicMock()
    msg.data = json.dumps({"prompt": prompt, "context": context_raw}).encode()
    msg.respond = AsyncMock()
    return msg


def _mock_nats(msg):
    sub = MagicMock()
    sub.next_msg = AsyncMock(return_value=msg)

    nc = MagicMock()
    nc.connect = AsyncMock()
    nc.subscribe = AsyncMock(return_value=sub)
    nc.publish = AsyncMock()
    nc.drain = AsyncMock()
    return nc


@pytest.fixture(autouse=True)
def clean_registry():
    _reset_registry()
    yield
    _reset_registry()


def _register(handler, **kwargs):
    """Register a handler with minimal defaults."""
    defaults = {"id": "test-agent", "version": "1.0.0", "description": "test"}
    defaults.update(kwargs)
    register_agent(AgentRegistration(handler=handler, **defaults))


class TestCamelCase:
    def test_simple(self):
        assert _to_camel("display_name") == "displayName"

    def test_multiple(self):
        assert _to_camel("use_workspace_skills") == "useWorkspaceSkills"


class TestSerializeDataclassCamel:
    def test_omits_none_fields(self):
        @dataclass
        class Ref:
            service: str
            title: str
            content: str | None = None

        result = _serialize_dataclass_camel(Ref(service="slack", title="update"))
        assert result == {"service": "slack", "title": "update"}
        assert "content" not in result

    def test_includes_set_fields(self):
        @dataclass
        class Ref:
            service: str
            title: str
            artifact_id: str | None = None

        result = _serialize_dataclass_camel(Ref(service="gh", title="PR", artifact_id="a1"))
        assert result == {"service": "gh", "title": "PR", "artifactId": "a1"}


class TestSerializeExtras:
    def test_none_produces_empty(self):
        extras = AgentExtras()
        result = _serialize_extras(extras)
        assert result == {}

    def test_reasoning(self):
        extras = AgentExtras(reasoning="I thought about it")
        result = _serialize_extras(extras)
        assert result["reasoning"] == "I thought about it"

    def test_artifact_refs(self):
        refs = [ArtifactRef(id="art-1", type="document", summary="A doc")]
        extras = AgentExtras(artifact_refs=refs)
        result = _serialize_extras(extras)
        assert result["artifactRefs"] == [
            {"id": "art-1", "type": "document", "summary": "A doc"}
        ]

    def test_outline_refs(self):
        refs = [
            OutlineRef(
                service="google-calendar",
                title="Meeting",
                content="Standup at 9am",
                artifact_id="art-2",
                artifact_label="Calendar",
            )
        ]
        extras = AgentExtras(outline_refs=refs)
        result = _serialize_extras(extras)
        assert result["outlineRefs"] == [
            {
                "service": "google-calendar",
                "title": "Meeting",
                "content": "Standup at 9am",
                "artifactId": "art-2",
                "artifactLabel": "Calendar",
            }
        ]

    def test_outline_ref_omits_none_fields(self):
        refs = [OutlineRef(service="slack", title="Channel update")]
        extras = AgentExtras(outline_refs=refs)
        result = _serialize_extras(extras)
        outline = result["outlineRefs"][0]
        assert outline == {"service": "slack", "title": "Channel update"}
        assert "content" not in outline
        assert "artifactId" not in outline
        assert "artifactLabel" not in outline

    def test_full_extras(self):
        extras = AgentExtras(
            reasoning="Analyzed the PR",
            artifact_refs=[ArtifactRef(id="a1", type="code", summary="Patch")],
            outline_refs=[OutlineRef(service="github", title="PR #42")],
        )
        result = _serialize_extras(extras)
        assert result["reasoning"] == "Analyzed the PR"
        assert len(result["artifactRefs"]) == 1
        assert len(result["outlineRefs"]) == 1


class TestSerializeResult:
    def test_ok_result(self):
        result = _serialize_result(ok({"echo": "hello"}))
        assert result["tag"] == "ok"
        parsed = json.loads(result["val"])
        assert parsed["data"] == {"echo": "hello"}

    def test_err_result(self):
        result = _serialize_result(err("something broke"))
        assert result["tag"] == "err"
        assert result["val"] == "something broke"

    def test_invalid_return_type(self):
        result = _serialize_result("not a result type")
        assert result["tag"] == "err"
        assert "OkResult or ErrResult" in result["val"]

    def test_string_ok_data(self):
        result = _serialize_result(ok("plain string"))
        assert result["tag"] == "ok"
        parsed = json.loads(result["val"])
        assert parsed["data"] == "plain string"

    def test_dataclass_ok_data(self):
        @dataclass
        class Output:
            name: str
            count: int

        result = _serialize_result(ok(Output(name="test", count=5)))
        assert result["tag"] == "ok"
        parsed = json.loads(result["val"])
        assert parsed["data"] == {"name": "test", "count": 5}

    def test_with_reasoning(self):
        extras = AgentExtras(reasoning="I thought about it")
        result = _serialize_result(ok("result", extras=extras))
        parsed = json.loads(result["val"])
        assert parsed["data"] == "result"
        assert parsed["reasoning"] == "I thought about it"

    def test_full_extras_envelope(self):
        extras = AgentExtras(
            reasoning="Analyzed the PR",
            artifact_refs=[ArtifactRef(id="a1", type="code", summary="Patch")],
            outline_refs=[OutlineRef(service="github", title="PR #42")],
        )
        result = _serialize_result(ok({"status": "ok"}, extras=extras))
        parsed = json.loads(result["val"])
        assert parsed["data"] == {"status": "ok"}
        assert parsed["reasoning"] == "Analyzed the PR"
        assert len(parsed["artifactRefs"]) == 1
        assert len(parsed["outlineRefs"]) == 1

    def test_extras_none_produces_data_only_envelope(self):
        result = _serialize_result(ok({"answer": 42}))
        parsed = json.loads(result["val"])
        assert parsed == {"data": {"answer": 42}}
        assert "artifactRefs" not in parsed
        assert "outlineRefs" not in parsed
        assert "reasoning" not in parsed


class TestGetMetadata:
    def _run_validate(self):
        mock_nc = _mock_nats(_mock_msg("", {}))
        with patch("friday_agent_sdk._bridge.NATS", return_value=mock_nc), patch.dict(
            os.environ, {"FRIDAY_VALIDATE_ID": "val-123", "NATS_URL": "nats://test"}
        ):
            asyncio.run(_validate_async("val-123"))
        return mock_nc

    def test_required_fields(self):
        _register(lambda p, c: ok("x"))
        nc = self._run_validate()
        meta = json.loads(nc.publish.call_args[0][1])
        assert meta["id"] == "test-agent"
        assert meta["version"] == "1.0.0"
        assert meta["description"] == "test"

    def test_optional_fields_omitted_when_none(self):
        _register(lambda p, c: ok("x"))
        nc = self._run_validate()
        meta = json.loads(nc.publish.call_args[0][1])
        assert "displayName" not in meta
        assert "summary" not in meta
        assert "constraints" not in meta
        assert "expertise" not in meta

    def test_optional_fields_included_when_set(self):
        _register(
            lambda p, c: ok("x"),
            display_name="Test Agent",
            summary="A test agent",
            constraints="be nice",
            examples=["example 1"],
        )
        nc = self._run_validate()
        meta = json.loads(nc.publish.call_args[0][1])
        assert meta["displayName"] == "Test Agent"
        assert meta["summary"] == "A test agent"
        assert meta["constraints"] == "be nice"
        assert meta["expertise"] == {"examples": ["example 1"]}

    def test_camel_case_keys(self):
        _register(lambda p, c: ok("x"), display_name="DN")
        nc = self._run_validate()
        meta = json.loads(nc.publish.call_args[0][1])
        assert "displayName" in meta
        assert "display_name" not in meta

    def test_environment_mcp_llm_passthrough(self):
        env = {"required": [{"name": "API_KEY"}]}
        mcp_conf = {"servers": []}
        llm_conf = {"provider": "anthropic"}
        _register(
            lambda p, c: ok("x"),
            environment=env,
            mcp=mcp_conf,
            llm=llm_conf,
        )
        nc = self._run_validate()
        meta = json.loads(nc.publish.call_args[0][1])
        assert meta["environment"] == env
        assert meta["mcp"] == mcp_conf
        assert meta["llm"] == llm_conf

    def test_use_workspace_skills_omitted_when_false(self):
        _register(lambda p, c: ok("x"))
        nc = self._run_validate()
        meta = json.loads(nc.publish.call_args[0][1])
        assert "useWorkspaceSkills" not in meta

    def test_use_workspace_skills_emitted_when_true(self):
        _register(lambda p, c: ok("x"), use_workspace_skills=True)
        nc = self._run_validate()
        meta = json.loads(nc.publish.call_args[0][1])
        assert meta["useWorkspaceSkills"] is True

    def test_json_schema_passthrough(self):
        _register(
            lambda p, c: ok("x"),
            input_json_schema={"type": "object"},
            output_json_schema={"type": "string"},
        )
        nc = self._run_validate()
        meta = json.loads(nc.publish.call_args[0][1])
        assert meta["inputSchema"] == {"type": "object"}
        assert meta["outputSchema"] == {"type": "string"}


class TestExecute:
    def _run_execute(self, msg, session_id="sess-1"):
        nc = _mock_nats(msg)
        with patch("friday_agent_sdk._bridge.NATS", return_value=nc), patch.dict(
            os.environ,
            {"FRIDAY_SESSION_ID": session_id, "NATS_URL": "nats://test"},
        ):
            asyncio.run(_run_async())
        return nc, msg

    def _parse_response(self, msg):
        raw = msg.respond.call_args[0][0]
        outer = json.loads(raw.decode())
        if outer["tag"] == "ok":
            inner = json.loads(outer["val"])
            return "ok", inner
        return "err", outer["val"]

    def test_ok_result_dispatches(self):
        _register(lambda prompt, ctx: ok({"echo": prompt}))
        msg = _mock_msg("hello", {})
        _, msg = self._run_execute(msg)
        tag, parsed = self._parse_response(msg)
        assert tag == "ok"
        assert parsed["data"] == {"echo": "hello"}

    def test_err_result_dispatches(self):
        _register(lambda prompt, ctx: err("something broke"))
        msg = _mock_msg("hello", {})
        _, msg = self._run_execute(msg)
        tag, parsed = self._parse_response(msg)
        assert tag == "err"
        assert parsed == "something broke"

    def test_handler_exception_returns_error(self):
        def exploding_handler(prompt, ctx):
            raise ValueError("kaboom")

        _register(exploding_handler)
        msg = _mock_msg("hello", {})
        _, msg = self._run_execute(msg)
        tag, parsed = self._parse_response(msg)
        assert tag == "err"
        assert "kaboom" in parsed

    def test_invalid_return_type_returns_error(self):
        _register(lambda prompt, ctx: "not a result type")
        msg = _mock_msg("hello", {})
        _, msg = self._run_execute(msg)
        tag, parsed = self._parse_response(msg)
        assert tag == "err"
        assert "OkResult or ErrResult" in parsed

    def test_string_ok_data_in_envelope(self):
        _register(lambda prompt, ctx: ok("plain string"))
        msg = _mock_msg("hi", {})
        _, msg = self._run_execute(msg)
        tag, parsed = self._parse_response(msg)
        assert tag == "ok"
        assert parsed["data"] == "plain string"

    def test_dataclass_ok_data_serialized(self):
        @dataclass
        class Output:
            name: str
            count: int

        _register(lambda prompt, ctx: ok(Output(name="test", count=5)))
        msg = _mock_msg("hi", {})
        _, msg = self._run_execute(msg)
        tag, parsed = self._parse_response(msg)
        assert tag == "ok"
        assert parsed["data"] == {"name": "test", "count": 5}

    def test_async_handler(self):
        async def async_handler(prompt, ctx):
            return ok({"async": True})

        _register(async_handler)
        msg = _mock_msg("hi", {})
        _, msg = self._run_execute(msg)
        tag, parsed = self._parse_response(msg)
        assert tag == "ok"
        assert parsed["data"] == {"async": True}

    def test_context_passed_to_handler(self):
        captured = {}

        def capturing_handler(prompt, ctx):
            captured["env"] = ctx.env
            return ok("done")

        _register(capturing_handler)
        msg = _mock_msg("hi", {"env": {"KEY": "val"}, "config": {}})
        self._run_execute(msg)
        assert captured["env"] == {"KEY": "val"}

    def test_config_passed_to_handler(self):
        captured = {}

        def handler(prompt, ctx):
            captured["config"] = ctx.config
            return ok("done")

        _register(handler)
        msg = _mock_msg("hi", {"config": {"model": "opus", "temp": 0.5}})
        self._run_execute(msg)
        assert captured["config"] == {"model": "opus", "temp": 0.5}

    def test_session_passed_to_handler(self):
        captured = {}

        def handler(prompt, ctx):
            captured["session"] = ctx.session
            return ok("done")

        _register(handler)
        msg = _mock_msg(
            "hi",
            {
                "session": {
                    "id": "sess_1",
                    "workspace_id": "ws_1",
                    "user_id": "user_42",
                    "datetime": "2026-04-03T12:00:00Z",
                }
            },
        )
        self._run_execute(msg)
        assert captured["session"].id == "sess_1"
        assert captured["session"].workspace_id == "ws_1"
        assert captured["session"].user_id == "user_42"
        assert captured["session"].datetime == "2026-04-03T12:00:00Z"

    def test_output_schema_passed_to_handler(self):
        captured = {}

        def handler(prompt, ctx):
            captured["output_schema"] = ctx.output_schema
            return ok("done")

        _register(handler)
        schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
        msg = _mock_msg("hi", {"output_schema": schema})
        self._run_execute(msg)
        assert captured["output_schema"] == schema

    def test_missing_session_is_none(self):
        captured = {}

        def handler(prompt, ctx):
            captured["session"] = ctx.session
            return ok("done")

        _register(handler)
        msg = _mock_msg("hi", {})
        self._run_execute(msg)
        assert captured["session"] is None
