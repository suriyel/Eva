"""F19 · REST routes for classifier prompt (IAPI-002 sub-route).

Feature design §IS §3 REST 路由 — F22 §IC Section B 契约对齐:
    * GET /api/prompts/classifier — returns
      ``{current: {content, hash}, history: [{hash, content_summary, created_at, rev}]}``.
    * PUT /api/prompts/classifier — body ``{content: str}``; append rev; same shape.

REST adapter maps F19 internal ``ClassifierPrompt(current: str, history: [Rev(rev, saved_at, hash, summary)])``
to F22 §IC consumer shape (Zod ``classifierPromptSchema`` in apps/ui/src/lib/zod-schemas.ts).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, ValidationError

from ..dispatch.classifier.errors import (
    PromptStoreCorruptError,
    PromptStoreError,
    PromptValidationError,
)
from ..dispatch.classifier.models import ClassifierPrompt
from ..dispatch.classifier.prompt_store import PromptStore


router = APIRouter()


def _prompt_store_path() -> Path:
    env = os.environ.get("HARNESS_HOME", "")
    home = Path(env) if env else (Path.home() / ".harness")
    return home / "classifier_prompt.json"


def _to_f22_ic(prompt: ClassifierPrompt) -> dict[str, Any]:
    """Map F19 internal model to F22 §IC Section B response shape.

    `current.hash` is the latest history entry's hash when history is non-empty
    (guaranteed equal to sha256(current) post-put per prompt_store atomic write);
    otherwise computed on the fly for the built-in default prompt path.
    """
    current_str = prompt.current
    if prompt.history:
        current_hash = prompt.history[-1].hash
    else:
        current_hash = hashlib.sha256(current_str.encode("utf-8")).hexdigest()

    history_items: list[dict[str, Any]] = []
    for rev in prompt.history:
        history_items.append(
            {
                "hash": rev.hash,
                "content_summary": rev.summary,
                "created_at": rev.saved_at,
                "rev": rev.rev,
            }
        )

    return {
        "current": {"content": current_str, "hash": current_hash},
        "history": history_items,
    }


class _PutBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str


@router.get("/api/prompts/classifier")
async def get_prompt() -> dict[str, Any]:
    store = PromptStore(path=_prompt_store_path())
    try:
        prompt = store.get()
    except PromptStoreCorruptError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _to_f22_ic(prompt)


@router.put("/api/prompts/classifier")
async def put_prompt(request: Request) -> dict[str, Any]:
    try:
        raw = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid JSON: {exc}") from exc

    try:
        body = _PutBody.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "validation", "errors": exc.errors()},
        ) from exc

    store = PromptStore(path=_prompt_store_path())
    try:
        prompt = store.put(body.content)
    except PromptValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PromptStoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return _to_f22_ic(prompt)


__all__ = ["router"]
