"""FastAPI microservice exposing Qwen summarization."""
from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Ensure project package is importable when running from container root
if "/app" not in os.sys.path:
    os.sys.path.append("/app")

from newsbot.llm_qwen import summarize_text  # noqa: E402

logger = logging.getLogger("qwen_server")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

app = FastAPI(title="Qwen Summarization Service", version="0.1.0")


class SummarizeRequest(BaseModel):
    text: str = Field(..., description="Article text to summarize", min_length=1)
    max_tokens: int = Field(200, ge=16, le=1024, description="Maximum tokens to generate")
    temperature: float = Field(0.3, ge=0.0, le=1.5, description="Sampling temperature")


class SummarizeResponse(BaseModel):
    summary: str
    tokens_used: Optional[int] = None


@app.get("/health", summary="Service health check")
def health() -> dict[str, str]:
    # Optionally, confirm the model path is configured
    model_path = os.environ.get("QWEN_LOCAL_PATH")
    status = "ready" if model_path else "model_path_not_set"
    return {"status": status}


@app.post("/summarize", response_model=SummarizeResponse, summary="Generate a summary")
def summarize(req: SummarizeRequest) -> SummarizeResponse:
    try:
        summary_text = summarize_text(req.text, max_tokens=req.max_tokens, temperature=req.temperature)
        tokens_used = len(summary_text.split())
        return SummarizeResponse(summary=summary_text, tokens_used=tokens_used)
    except Exception as exc:  # pragma: no cover - runtime errors returned as HTTP 500
        logger.exception("Summarization failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/warmup", summary="Force model load")
def warmup() -> dict[str, str]:
    try:
        summarize_text("Warmup request", max_tokens=16, temperature=0.1)
        return {"status": "loaded"}
    except Exception as exc:
        logger.exception("Warmup failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
