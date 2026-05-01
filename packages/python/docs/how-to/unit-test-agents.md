# Unit-test agents

Friday agents are plain Python functions that take a prompt and an
`AgentContext`. To test them in isolation you need an `AgentContext` whose
capability fields don't actually talk to the daemon — that's what
`make_test_context()` is for.

## The 30-second version

```python
from friday_agent_sdk import make_test_context

from my_agent import execute  # the @agent-decorated handler


def test_echoes_prompt():
    ctx = make_test_context()
    result = execute("hello", ctx)
    assert result.data == "hello"
```

`make_test_context()` returns an `AgentContext` with `Fake*` instances for
`ctx.llm`, `ctx.http`, `ctx.tools`, and `ctx.stream`. Each fake records every
call and returns a permissive default — no daemon, no NATS, no API keys.

## Asserting on emitted progress

`FakeStream` records every event into `ctx.stream.events`:

```python
from friday_agent_sdk import make_test_context


def test_emits_progress():
    ctx = make_test_context()

    execute("hi", ctx)

    assert ctx.stream.events == [
        ("data-tool-progress", {"toolName": "agent", "content": "Starting"}),
        ("data-tool-progress", {"toolName": "agent", "content": "Done"}),
    ]
```

## Stubbing LLM responses

Pass canned responses (FIFO queue) or a callable:

```python
from friday_agent_sdk import LlmResponse, make_test_context
from friday_agent_sdk.testing import FakeLlm


def test_uses_llm_output():
    fake_llm = FakeLlm(
        responses=[
            LlmResponse(
                text="42",
                object=None,
                model="fake",
                usage={},
                finish_reason="stop",
            )
        ]
    )
    ctx = make_test_context(llm=fake_llm)

    result = execute("what is 6 * 7?", ctx)

    assert result.data == "42"
    assert fake_llm.calls[0]["messages"][-1]["content"] == "what is 6 * 7?"
```

For dynamic responses, use `on_generate`:

```python
fake_llm = FakeLlm(
    on_generate=lambda messages, **kwargs: LlmResponse(
        text=f"echo: {messages[-1]['content']}",
        object=None,
        model="fake",
        usage={},
        finish_reason="stop",
    )
)
```

## Stubbing HTTP responses

```python
from friday_agent_sdk import HttpResponse, make_test_context
from friday_agent_sdk.testing import FakeHttp


fake_http = FakeHttp(
    responses=[
        HttpResponse(status=200, headers={}, body='{"ok": true}'),
        HttpResponse(status=429, headers={"Retry-After": "10"}, body=""),
    ]
)
ctx = make_test_context(http=fake_http)
```

`FakeHttp` also accepts an `on_fetch=callable` for URL-aware logic.

## Stubbing tool calls

`FakeTools` requires you to register handlers explicitly — unhandled calls
raise `ToolCallError` rather than silently returning empty results:

```python
from friday_agent_sdk import ToolDefinition, make_test_context
from friday_agent_sdk.testing import FakeTools


fake_tools = FakeTools(
    tools=[
        ToolDefinition(name="add", description="adds two numbers", input_schema={}),
    ],
    handlers={"add": lambda args: {"sum": args["a"] + args["b"]}},
)
ctx = make_test_context(tools=fake_tools)
```

## Custom protocol implementations

You don't have to use the `Fake*` classes. The capability fields are typed as
**protocols** (`LlmProtocol`, `HttpProtocol`, `ToolsProtocol`, `StreamProtocol`),
so any object with the right method shape is accepted:

```python
class RecordingLlm:
    def __init__(self):
        self.seen: list[str] = []

    def generate(self, messages, **kwargs):
        self.seen.append(messages[-1]["content"])
        return LlmResponse(text="ok", object=None, model="x", usage={}, finish_reason="stop")

    def generate_object(self, messages, schema, **kwargs):
        return LlmResponse(text=None, object={}, model="x", usage={}, finish_reason="stop")


ctx = make_test_context(llm=RecordingLlm())
```

This is the same mechanism a custom production gateway would use — the
protocols are the contract, the `Fake*` classes are convenience.

## What goes in `make_test_context()`

| Argument        | Type              | Default        |
| --------------- | ----------------- | -------------- |
| `env`           | `dict[str, str]`  | `{}`           |
| `config`        | `dict`            | `{}`           |
| `skills`        | `list[Skill...]`  | `[]`           |
| `session`       | `SessionData?`    | `None`         |
| `output_schema` | `dict?`           | `None`         |
| `llm`           | `LlmProtocol?`    | `FakeLlm()`    |
| `http`          | `HttpProtocol?`   | `FakeHttp()`   |
| `tools`         | `ToolsProtocol?`  | `FakeTools()`  |
| `stream`        | `StreamProtocol?` | `FakeStream()` |
