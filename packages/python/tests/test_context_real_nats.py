"""Protocol-level test through a real NATS broker.

Spawns `nats-server` as a subprocess on a free port, registers a fake daemon
subscriber on the capability subjects, then drives the SDK end-to-end. Exercises
real `nats-py` serialization and the actual NATS wire protocol — complements
the AsyncMock-based tests in `test_context_nats.py` which prove the SDK's
threading and JSON contracts in isolation.

Skipped automatically if `nats-server` is not on PATH (so local dev without
the binary still passes). CI installs it explicitly.
"""

import asyncio
import contextlib
import json
import shutil
import socket
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from nats.aio.client import Client as NATS

from friday_agent_sdk._context import build_context
from friday_agent_sdk._types import LlmError

pytestmark = pytest.mark.skipif(
    shutil.which("nats-server") is None,
    reason="nats-server binary required for protocol-level test",
)

SESSION_ID = "test-session"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def nats_server() -> Iterator[str]:
    """Start nats-server on a free port; yield the connection URL.

    Polls the port until accept() succeeds so the test does not race the
    server's startup. Tears the process down cleanly on exit.
    """
    port = _free_port()
    proc = subprocess.Popen(
        ["nats-server", "-p", str(port), "-a", "127.0.0.1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)
    else:
        proc.kill()
        raise RuntimeError("nats-server failed to bind within 5s")
    try:
        yield f"nats://127.0.0.1:{port}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


async def _start_fake_daemon(url: str, *, llm_error: bool = False) -> NATS:
    """Connect a separate NATS client and subscribe to the four capability
    subjects, mirroring friday-studio/apps/atlasd/src/capability-handlers.ts.
    Returns the client so the test can drain it on teardown.
    """
    nc = NATS()
    await nc.connect(url)

    async def llm_handler(msg):
        if llm_error:
            await msg.respond(json.dumps({"error": "rate limited"}).encode())
            return
        req = json.loads(msg.data.decode())
        await msg.respond(
            json.dumps(
                {
                    "text": f"echo: {req['messages'][-1]['content']}",
                    "model": req.get("model", "unknown"),
                    "usage": {"input_tokens": 1, "output_tokens": 2},
                    "finish_reason": "stop",
                }
            ).encode()
        )

    async def http_handler(msg):
        req = json.loads(msg.data.decode())
        await msg.respond(
            json.dumps(
                {
                    "status": 200,
                    "headers": {"content-type": "text/plain"},
                    "body": f"fetched {req['url']}",
                }
            ).encode()
        )

    async def tools_call_handler(msg):
        payload = json.loads(msg.data.decode())
        await msg.respond(json.dumps({"tool": payload["name"], "got": payload["args"]}).encode())

    async def tools_list_handler(msg):
        await msg.respond(
            json.dumps(
                {
                    "tools": [
                        {
                            "name": "real-tool",
                            "description": "from broker",
                            "inputSchema": {"type": "object"},
                        }
                    ]
                }
            ).encode()
        )

    await nc.subscribe(f"caps.{SESSION_ID}.llm.generate", cb=llm_handler)
    await nc.subscribe(f"caps.{SESSION_ID}.http.fetch", cb=http_handler)
    await nc.subscribe(f"caps.{SESSION_ID}.tools.call", cb=tools_call_handler)
    await nc.subscribe(f"caps.{SESSION_ID}.tools.list", cb=tools_list_handler)
    return nc


async def _drain(nc: NATS) -> None:
    """Drain swallowing teardown errors — connection state at end-of-test
    is not what we're asserting on."""
    with contextlib.suppress(Exception):
        await nc.drain()


def test_all_capabilities_round_trip_via_real_broker():
    """Drive every capability through a real broker. Mirrors the bridge's
    threading model: handler runs on a worker thread (`asyncio.to_thread`)
    while the event loop services NATS callbacks."""

    async def main(url: str) -> None:
        loop = asyncio.get_running_loop()

        sdk_nc = NATS()
        await sdk_nc.connect(url)
        daemon_nc = await _start_fake_daemon(url)

        try:
            ctx = build_context({}, sdk_nc, SESSION_ID, loop)

            def handler():
                llm_resp = ctx.llm.generate(
                    messages=[{"role": "user", "content": "hello"}],
                    model="m1",
                )
                http_resp = ctx.http.fetch("https://example.com/x", method="GET")
                tool_call = ctx.tools.call("t1", {"a": 1})
                tools = ctx.tools.list()
                return llm_resp, http_resp, tool_call, tools

            llm_resp, http_resp, tool_call, tools = await asyncio.to_thread(handler)

            assert llm_resp.text == "echo: hello"
            assert llm_resp.model == "m1"
            assert llm_resp.finish_reason == "stop"

            assert http_resp.status == 200
            assert http_resp.body == "fetched https://example.com/x"

            assert tool_call == {"tool": "t1", "got": {"a": 1}}

            assert len(tools) == 1
            assert tools[0].name == "real-tool"
            assert tools[0].description == "from broker"
            assert tools[0].input_schema == {"type": "object"}
        finally:
            await _drain(sdk_nc)
            await _drain(daemon_nc)

    with nats_server() as url:
        asyncio.run(main(url))


def test_llm_error_propagates_via_real_broker():
    """When the daemon replies with {"error": ...}, the SDK raises LlmError."""

    async def main(url: str) -> None:
        loop = asyncio.get_running_loop()
        sdk_nc = NATS()
        await sdk_nc.connect(url)
        daemon_nc = await _start_fake_daemon(url, llm_error=True)
        try:
            ctx = build_context({}, sdk_nc, SESSION_ID, loop)

            def handler():
                return ctx.llm.generate(
                    messages=[{"role": "user", "content": "x"}],
                    model="m1",
                )

            with pytest.raises(LlmError, match="rate limited"):
                await asyncio.to_thread(handler)
        finally:
            await _drain(sdk_nc)
            await _drain(daemon_nc)

    with nats_server() as url:
        asyncio.run(main(url))
