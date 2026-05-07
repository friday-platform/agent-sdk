"""Tests for AgentInput structured action-input helpers."""

import json
from unittest.mock import MagicMock

import pytest

from friday_agent_sdk._types import AgentInput, InputArtifactRef, ToolCallError, Tools


def _tools_for_artifact(contents: object) -> Tools:
    artifact_payload = {
        "id": "art-1",
        "type": "file",
        "contents": json.dumps(contents),
    }
    call_result = {
        "content": [
            {
                "type": "text",
                "text": json.dumps(artifact_payload),
            }
        ],
        "isError": False,
    }
    return Tools(call_tool=MagicMock(return_value=json.dumps(call_result)), list_tools=MagicMock(return_value=[]))


class TestAgentInputLookup:
    def test_get_prefers_config_input_from_keys(self):
        agent_input = AgentInput(
            {
                "task": "rendered",
                "config": {
                    "fetched-emails": {"summary": "Fetched 10"},
                    "query": "from config",
                },
                "query": "from raw",
            }
        )

        assert agent_input.get("fetched-emails") == {"summary": "Fetched 10"}
        assert agent_input.get("query") == "from config"
        assert agent_input.get("missing", "fallback") == "fallback"
        assert agent_input.get()["task"] == "rendered"

    def test_require_raises_for_missing_named_input(self):
        agent_input = AgentInput({"config": {}})

        with pytest.raises(ValueError, match="Required action input not found: fetched-emails"):
            agent_input.require("fetched-emails")

    def test_require_without_name_raises_for_empty_input(self):
        agent_input = AgentInput({})

        with pytest.raises(ValueError, match="Required action input not found: input"):
            agent_input.require()

    def test_require_without_name_returns_non_empty_raw_input(self):
        agent_input = AgentInput({"task": "run"})

        assert agent_input.require() == {"task": "run"}


class TestArtifactRefs:
    def test_artifact_refs_reads_named_input_from_config(self):
        agent_input = AgentInput(
            {
                "config": {
                    "fetched-emails": {
                        "summary": "Fetched unread emails",
                        "artifactRefs": [{"id": "art-1", "type": "AgentResult", "summary": "Fetched unread emails"}],
                    }
                }
            }
        )

        assert agent_input.artifact_refs("fetched-emails") == [
            InputArtifactRef(id="art-1", type="AgentResult", summary="Fetched unread emails")
        ]

    def test_artifact_refs_accepts_artifact_id_alias(self):
        agent_input = AgentInput({"artifactRef": {"artifactId": "art-2", "summary": "alias"}})

        assert agent_input.artifact_refs() == [InputArtifactRef(id="art-2", summary="alias")]

    def test_artifact_refs_deduplicates_nested_refs(self):
        agent_input = AgentInput(
            {
                "artifactRefs": [{"id": "art-1"}],
                "config": {"doc": {"artifactRefs": [{"id": "art-1"}, {"id": "art-2"}]}},
            }
        )

        assert [ref.id for ref in agent_input.artifact_refs()] == ["art-1", "art-2"]


class TestArtifactJson:
    def test_artifact_json_fetches_and_parses_json_contents(self):
        tools = _tools_for_artifact({"emails": [{"id": "fake-001"}], "count": 1})
        agent_input = AgentInput(
            {"config": {"fetched-emails": {"artifactRefs": [{"id": "art-1"}]}}},
            tools,
        )

        assert agent_input.artifact_json("fetched-emails") == {
            "emails": [{"id": "fake-001"}],
            "count": 1,
        }
        tools._call_tool.assert_called_once_with("artifacts_get", json.dumps({"artifactId": "art-1"}))

    def test_artifact_json_returns_list_for_multiple_refs(self):
        calls = [
            json.dumps({"content": [{"type": "text", "text": json.dumps({"contents": json.dumps({"a": 1})})}]}),
            json.dumps({"content": [{"type": "text", "text": json.dumps({"contents": json.dumps({"b": 2})})}]}),
        ]
        tools = Tools(call_tool=MagicMock(side_effect=calls), list_tools=MagicMock(return_value=[]))
        agent_input = AgentInput({"artifactRefs": [{"id": "a"}, {"id": "b"}]}, tools)

        assert agent_input.artifact_json() == [{"a": 1}, {"b": 2}]

    def test_artifact_json_raises_when_no_refs(self):
        agent_input = AgentInput({"config": {"fetched-emails": {}}}, _tools_for_artifact({}))

        with pytest.raises(ValueError, match="No artifact refs found"):
            agent_input.artifact_json("fetched-emails")

    def test_artifact_json_requires_tools(self):
        agent_input = AgentInput({"artifactRefs": [{"id": "art-1"}]})

        with pytest.raises(ToolCallError, match="artifacts_get unavailable"):
            agent_input.artifact_json()

    def test_artifact_json_raises_on_tool_error_result(self):
        tools = Tools(
            call_tool=MagicMock(return_value=json.dumps({"content": [], "isError": True})),
            list_tools=MagicMock(return_value=[]),
        )
        agent_input = AgentInput({"artifactRefs": [{"id": "art-1"}]}, tools)

        with pytest.raises(ToolCallError, match="artifacts_get failed"):
            agent_input.artifact_json()
