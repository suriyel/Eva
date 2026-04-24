"""F19 · REST routes for classifier prompt (IAPI-002 sub-route).

Feature design §IS §3 REST 路由:
    * GET /api/prompts/classifier — returns ``{current, history[]}``.
    * PUT /api/prompts/classifier — body ``{content: str}``; append rev.
"""

from __future__ import annotations

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
from ..dispatch.classifier.prompt_store import PromptStore


router = APIRouter()


def _prompt_store_path() -> Path:
    env = os.environ.get("HARNESS_HOME", "")
    home = Path(env) if env else (Path.home() / ".harness")
    return home / "classifier_prompt.json"


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
    return prompt.model_dump(mode="json")


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

    return prompt.model_dump(mode="json")


__all__ = ["router"]
