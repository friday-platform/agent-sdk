# How to Return Artifacts and Outline References

Persist outputs in Friday's artifact system and add structured references to the conversation outline.

## Basic Success Result

Use `ok()` to return structured data:

```python
from friday_agent_sdk import agent, ok

@agent(id="simple", version="1.0.0", description="Simple agent")
def execute(prompt, ctx):
    return ok({"answer": 42})
```

## With Extras

Include optional metadata via `AgentExtras`:

```python
from friday_agent_sdk import agent, ok, AgentExtras

@agent(id="with-extras", version="1.0.0", description="Returns extras")
def execute(prompt, ctx):
    data = {"result": "success"}
    extras = AgentExtras(reasoning="Based on heuristic analysis")

    return ok(data, extras=extras)
```

## Creating Artifacts

Create platform artifacts via the HTTP API:

```python
import json
from friday_agent_sdk import agent, ok, AgentExtras, ArtifactRef

@agent(id="artifact-creator", version="1.0.0", description="Creates artifacts")
def execute(prompt, ctx):
    # Your analysis result
    analysis = run_analysis(prompt)

    # Create artifact via Friday's API
    response = ctx.http.fetch(
        f"{ctx.config.get('platformUrl', 'http://localhost:8080')}/api/artifacts",
        method="POST",
        headers={"Content-Type": "application/json"},
        body=json.dumps({
            "data": {
                "type": "analysis",
                "version": 1,
                "data": analysis,
            },
            "title": f"Analysis: {prompt[:50]}",
            "summary": f"Generated analysis for task",
        }),
    )

    if response.status >= 400:
        # Artifact creation failed — return data anyway
        return ok({"analysis": analysis})

    result = response.json()
    artifact = result.get("artifact", {})

    # Reference the artifact in extras
    extras = AgentExtras(
        artifact_refs=[
            ArtifactRef(
                id=artifact.get("id", ""),
                type="analysis",
                summary=artifact.get("summary", "Generated analysis"),
            )
        ]
    )

    return ok({"analysis_id": artifact.get("id")}, extras=extras)
```

## Outline References

Add structured entries to the conversation outline:

```python
from friday_agent_sdk import agent, ok, AgentExtras, OutlineRef

@agent(id="outline-ref", version="1.0.0", description="Adds outline references")
def execute(prompt, ctx):
    # Multiple results to highlight
    sections = [
        OutlineRef(
            service="github",
            title="Pull Request #123",
            content="Fix authentication bug",
        ),
        OutlineRef(
            service="github",
            title="Pull Request #124",
            content="Update dependencies",
        ),
    ]

    extras = AgentExtras(outline_refs=sections)
    return ok({"count": len(sections)}, extras=extras)
```

## With Artifacts

```python
OutlineRef(
    service="github",
    title="Bug Report",
    content="Critical issue in auth flow",
    artifact_id="art_12345",
    artifact_label="Full Report",
)
```

## Reasoning Field

Provide transparency about agent decisions:

```python
extras = AgentExtras(
    reasoning="""
Selected claude-sonnet-4-6 for this task because it requires:
1. Multi-file context understanding
2. Complex refactoring operations
3. Cross-module dependency analysis

Haiku was insufficient for the architectural complexity.
""".strip()
)
```

## Complete Example

```python
import json
from friday_agent_sdk import (
    agent, ok, AgentExtras, ArtifactRef, OutlineRef
)

@agent(id="reporter", version="1.0.0", description="Generates reports")
def execute(prompt, ctx):
    # Generate content
    report_data = generate_report(prompt)

    # Create artifact
    art_response = ctx.http.fetch(
        f"{ctx.config.get('platformUrl')}/api/artifacts",
        method="POST",
        headers={"Content-Type": "application/json"},
        body=json.dumps({
            "data": {
                "type": "report",
                "version": 1,
                "data": report_data,
            },
            "title": f"Report: {prompt[:40]}",
            "summary": "Comprehensive analysis report",
        }),
    )

    artifact_ref = None
    if art_response.status < 400:
        art = art_response.json().get("artifact", {})
        artifact_ref = ArtifactRef(
            id=art.get("id", ""),
            type="report",
            summary=art.get("summary", ""),
        )

    # Build outline references
    outline = [
        OutlineRef(
            service="analysis",
            title="Key Findings",
            content=f"Found {report_data['issue_count']} issues",
            artifact_id=artifact_ref.id if artifact_ref else None,
        ),
        OutlineRef(
            service="analysis",
            title="Recommendations",
            content=f"{len(report_data['recommendations'])} suggested actions",
        ),
    ]

    # Return with full extras
    extras = AgentExtras(
        artifact_refs=[artifact_ref] if artifact_ref else None,
        outline_refs=outline,
        reasoning=f"Analysed using {report_data['model_used']} due to complexity",
    )

    return ok({
        "summary": report_data["summary"],
        "issue_count": report_data["issue_count"],
    }, extras=extras)
```

## Best Practices

- **Artifact creation is best-effort** — Always return data even if artifact creation fails
- **Keep reasoning concise** — 2-3 sentences explaining key decisions
- **Use outline_refs for scannable results** — Helps users navigate complex outputs
- **Include artifact_label** — Makes the link text in UI meaningful

## See Also

- [API reference: result types](../reference/result-types.md)
- [Claude Code agent example](../../examples/claude-code-agent/agent.py) — Full extras usage
