# ctx.http

HTTP capability wrapper for outbound requests through Friday's fetch layer.

## Class: Http

```python
class Http:
    def fetch(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout_ms: int | None = None,
    ) -> HttpResponse: ...
```

## Methods

### fetch()

Make an HTTP request through the host.

**Parameters:**

| Parameter    | Type            | Required | Default | Description                                       |
| ------------ | --------------- | -------- | ------- | ------------------------------------------------- | ------------------------------- |
| `url`        | `str`           | Yes      | —       | Target URL                                        |
| `method`     | `str`           | No       | `"GET"` | HTTP method (GET, POST, PUT, PATCH, DELETE, HEAD) |
| `headers`    | `dict[str, str] | None`    | No      | `None`                                            | Request headers                 |
| `body`       | `str            | None`    | No      | `None`                                            | Request body (string)           |
| `timeout_ms` | `int            | None`    | No      | `None`                                            | Request timeout in milliseconds |

**Returns:** `HttpResponse`

**Raises:** `HttpError` on network-level failure (DNS, TLS, timeout, connection)

## HttpResponse

```python
@dataclass
class HttpResponse:
    status: int              # HTTP status code
    headers: dict[str, str] # Response headers
    body: str               # Response body as string

    def json(self) -> Any:   # Parse body as JSON
        return json.loads(self.body)
```

## Basic GET

```python
response = ctx.http.fetch("https://api.example.com/data")

if response.status == 200:
    data = response.json()
    return ok({"data": data})
elif response.status == 404:
    return ok({"found": False})
else:
    return err(f"API error: {response.status}")
```

## POST with JSON

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

result = response.json()
return ok({"created_id": result["id"]})
```

## Error handling

```python
from friday_agent_sdk import HttpError, agent, err, ok

@agent(id="resilient", version="1.0.0", description="Handles HTTP failures")
def execute(prompt, ctx):
    try:
        response = ctx.http.fetch("https://api.example.com/data")
    except HttpError as e:
        # Network failure: DNS, TLS, connection, timeout
        return err(f"Request failed: {e}")

    # HTTP error status (4xx, 5xx) is NOT an exception
    if response.status >= 500:
        return err(f"Server error: {response.status}")

    if response.status == 429:
        return err("Rate limited. Please retry later.")

    if response.status >= 400:
        return err(f"Client error: {response.status} - {response.body[:200]}")

    return ok({"data": response.json()})
```

## Timeout

```python
response = ctx.http.fetch(
    "https://slow-api.example.com/data",
    timeout_ms=30000,  # 30 seconds
)
```

## Methods

All HTTP methods are supported:

```python
ctx.http.fetch(url, method="GET")      # Default
ctx.http.fetch(url, method="POST", body="...")
ctx.http.fetch(url, method="PUT", body="...")
ctx.http.fetch(url, method="PATCH", body="...")
ctx.http.fetch(url, method="DELETE")
ctx.http.fetch(url, method="HEAD")
```

## Headers

Case-insensitive header dict:

```python
response = ctx.http.fetch(
    url,
    headers={
        "Accept": "application/json",
        "User-Agent": "my-agent/1.0",
        "X-Custom-Header": "value",
    },
)

# Access response headers
content_type = response.headers.get("content-type", "")
rate_limit = response.headers.get("x-ratelimit-remaining")
```

## REST API patterns

```python
base_url = "https://api.service.com/v1"

# GET collection
response = ctx.http.fetch(f"{base_url}/items")
items = response.json()["items"]

# GET item
response = ctx.http.fetch(f"{base_url}/items/{item_id}")
item = response.json()

# POST create
response = ctx.http.fetch(
    f"{base_url}/items",
    method="POST",
    headers={"Content-Type": "application/json"},
    body=json.dumps({"name": "New"}),
)
new_item = response.json()

# PUT update
response = ctx.http.fetch(
    f"{base_url}/items/{item_id}",
    method="PUT",
    headers={"Content-Type": "application/json"},
    body=json.dumps({"name": "Updated"}),
)

# DELETE
response = ctx.http.fetch(
    f"{base_url}/items/{item_id}",
    method="DELETE",
)
```

## Authentication

```python
# Bearer token
response = ctx.http.fetch(
    url,
    headers={"Authorization": f"Bearer {ctx.env['TOKEN']}"},
)

# Basic auth (construct manually)
import base64
credentials = base64.b64encode(b"user:pass").decode()
response = ctx.http.fetch(
    url,
    headers={"Authorization": f"Basic {credentials}"},
)

# API key in header
response = ctx.http.fetch(
    url,
    headers={"X-API-Key": ctx.env['API_KEY']},
)
```

## Query parameters

Construct URL with parameters:

```python
import urllib.parse

params = {"q": "search query", "limit": 10}
query = urllib.parse.urlencode(params)
url = f"https://api.example.com/search?{query}"

response = ctx.http.fetch(url)
```

## Response body limits

- **5MB limit** enforced by platform
- Exceeding returns truncated or error response
- For large payloads, consider streaming (not yet available)

## URL allowlists

Not yet implemented. Currently all outbound HTTPS requests are allowed.

## Why not use `requests` or `httpx`?

You technically can — agents run as native Python processes, so installed packages work. But host-provided HTTP is still preferred:

- **Credential management** — Friday injects API keys; your agent code never holds them
- **Audit logging** — All requests are logged by the platform
- **Rate limiting** — The host enforces quotas and retries
- **TLS termination** — Certificates and CA bundles managed centrally
- **Response limits** — 5MB cap enforced uniformly

Use `ctx.http.fetch()` for any I/O that needs production observability. Use `requests` only for internal tooling or debugging where host tracking isn't needed.

## See also

- [How to Make HTTP Requests](../how-to/make-http-requests.md) — Task-oriented guide
