# How to Make HTTP Requests

Make outbound HTTP requests through Friday's fetch layer — TLS, timeouts, and audit logging handled by the host.

> **New here?** See [Your First Friday Agent](../tutorial/your-first-agent.md#step-3-build-and-test) for how to build and run your agent.

## Basic GET request

```python
from friday_agent_sdk import agent, ok

@agent(id="fetcher", version="1.0.0", description="Fetches data from APIs")
def execute(prompt, ctx):
    response = ctx.http.fetch("https://api.example.com/data")

    if response.status >= 400:
        return err(f"API error {response.status}")

    data = response.json()  # Convenience helper
    return ok({"data": data})
```

## POST with JSON body

```python
import json

response = ctx.http.fetch(
    "https://api.example.com/items",
    method="POST",
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ctx.env['API_KEY']}",
    },
    body=json.dumps({"name": "New Item", "value": 42}),
)
```

Access environment variables via `ctx.env` — configure them in the decorator:

```python
@agent(
    id="api-client",
    version="1.0.0",
    description="Calls external API",
    environment={
        "required": [
            {"name": "API_KEY", "description": "API authentication token"},
        ],
    },
)
def execute(prompt, ctx):
    api_key = ctx.env["API_KEY"]  # Raises KeyError if not set
    ...
```

## Response handling

```python
response = ctx.http.fetch(...)

# Fields
response.status   # HTTP status code (int)
response.headers  # Dict of response headers
response.body     # Response body as string

# Convenience methods
data = response.json()  # Parses body as JSON
```

## Error handling

HTTP errors raise `HttpError`:

```python
from friday_agent_sdk import HttpError, agent, err, ok

@agent(id=" resilient", version="1.0.0", description="Handles API failures")
def execute(prompt, ctx):
    try:
        response = ctx.http.fetch("https://api.example.com/data")
    except HttpError as e:
        # Network-level failure (DNS, TLS, timeout)
        return err(f"Request failed: {e}")

    if response.status >= 500:
        # Server error — could retry
        return err(f"Server error: {response.status}")

    if response.status == 404:
        # Not found — might be expected
        return ok({"found": False})

    return ok({"found": True, "data": response.json()})
```

## Timeouts

```python
response = ctx.http.fetch(
    "https://slow-api.example.com/data",
    timeout_ms=30000,  # 30 seconds
)
```

## Methods and options

```python
response = ctx.http.fetch(
    url,
    method="PUT",           # GET, POST, PUT, PATCH, DELETE, HEAD
    headers={...},          # Dict of request headers
    body="raw body",        # String body
    timeout_ms=10000,       # Request timeout
)
```

## Limitations

- **5MB response limit** — Matches Friday's platform webfetch limit
- **No URL allowlists yet** — Designed but not implemented; all outbound requests allowed
- **No streaming responses** — Body returned as complete string

## Why not use `requests` or `httpx`?

You technically can — agents run as native Python processes, so installed packages work. But host-provided HTTP is still preferred:

- **Credential management** — Friday injects API keys; your agent code never holds them
- **Audit logging** — All requests are logged by the platform
- **Rate limiting** — The host enforces quotas and retries
- **TLS termination** — Certificates and CA bundles managed centrally
- **Response limits** — 5MB cap enforced uniformly

Use `ctx.http.fetch()` for any I/O that needs production observability. Use `requests` only for internal tooling or debugging where host tracking isn't needed.

## See also

- [API reference: ctx.http](../reference/http-capability.md)
- [How to Use MCP Tools](use-mcp-tools.md) — For APIs with official MCP servers, tools may be more ergonomic than raw HTTP
