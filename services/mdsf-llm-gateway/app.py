"""
MDSF crew LLM gateway — thin prompt validation proxy.

Sits between the MDSF crew pipeline and the local MLX server, ensuring only
well-formed MDSF structured-extraction prompts reach the model. Everything
else is rejected at the gate.

Endpoints
---------
POST /v1/chat/completions — validated proxy to MLX backend
GET  /health              — readiness probe
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "8183"))
MLX_BACKEND_URL = os.environ.get(
    "MLX_BACKEND_URL", "http://127.0.0.1:8181/v1/chat/completions"
)

REQUIRED_KEYWORDS = frozenset({
    "mdsf", "crew", "format", "analyze", "classify", "extract", "json", "structured",
})
MIN_KEYWORD_HITS = 3

MAX_TOKENS_CAP = 1000
MAX_TEMPERATURE = 0.3

app = FastAPI(title="mdsf-llm-gateway", docs_url=None, redoc_url=None)


def _validate_request(body: dict[str, Any]) -> str | None:
    """Return an error string if the request is invalid, else None."""

    if "tools" in body or "tool_choice" in body or "functions" in body:
        return "tool_use is not permitted"

    response_format = body.get("response_format")
    if not isinstance(response_format, dict) or response_format.get("type") != "json_object":
        return "response_format.type must be 'json_object'"

    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        return "messages array is required and must be non-empty"

    system_text = ""
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "system":
            content = msg.get("content", "")
            if isinstance(content, str):
                system_text += content.lower()

    if not system_text:
        return "a system message is required"

    hits = sum(1 for kw in REQUIRED_KEYWORDS if kw in system_text)
    if hits < MIN_KEYWORD_HITS:
        return (
            f"system prompt does not match MDSF crew schema "
            f"(matched {hits}/{MIN_KEYWORD_HITS} required keywords)"
        )

    return None


def _enforce_limits(body: dict[str, Any]) -> dict[str, Any]:
    """Clamp safety-critical parameters."""
    body = dict(body)

    if body.get("max_tokens") is not None:
        body["max_tokens"] = min(int(body["max_tokens"]), MAX_TOKENS_CAP)
    else:
        body["max_tokens"] = MAX_TOKENS_CAP

    temp = body.get("temperature")
    if temp is None or float(temp) > MAX_TEMPERATURE:
        body["temperature"] = MAX_TEMPERATURE

    body.pop("tools", None)
    body.pop("tool_choice", None)
    body.pop("functions", None)

    return body


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> JSONResponse:
    client_host = request.client.host if request.client else "unknown"
    if client_host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=403, detail="localhost only")

    body = await request.json()

    error = _validate_request(body)
    if error:
        raise HTTPException(status_code=422, detail=error)

    body = _enforce_limits(body)

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(MLX_BACKEND_URL, json=body)

    return JSONResponse(content=resp.json(), status_code=resp.status_code)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=LISTEN_PORT)
