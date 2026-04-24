"""F19 · REST routes for model rules + classifier config (IAPI-002 sub-routes).

Feature design §Implementation Summary §3 REST 路由:
    * GET  /api/settings/model_rules
    * PUT  /api/settings/model_rules
    * GET  /api/settings/classifier
    * PUT  /api/settings/classifier
    * POST /api/settings/classifier/test

All routes read HARNESS_HOME each request (hermetic with tmp_path override in
tests).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from ..dispatch.classifier.models import (
    ClassifierConfig,
    TestConnectionRequest,
    TestConnectionResult,
)
from ..dispatch.classifier.service import ClassifierService
from ..dispatch.model.models import ModelRule
from ..dispatch.model.rules_store import ModelRulesCorruptError, ModelRulesStore


router = APIRouter()


def _harness_home() -> Path:
    env = os.environ.get("HARNESS_HOME", "")
    return Path(env) if env else (Path.home() / ".harness")


def _model_rules_path() -> Path:
    return _harness_home() / "model_rules.json"


def _classifier_config_path() -> Path:
    return _harness_home() / "classifier_config.json"


def _prompt_store_path() -> Path:
    return _harness_home() / "classifier_prompt.json"


# ---------------------------------------------------------------------------
# /api/settings/model_rules
# ---------------------------------------------------------------------------
@router.get("/api/settings/model_rules")
async def get_model_rules() -> list[dict[str, Any]]:
    store = ModelRulesStore(path=_model_rules_path())
    try:
        rules = store.load()
    except ModelRulesCorruptError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return [rule.model_dump(mode="json") for rule in rules]


@router.put("/api/settings/model_rules")
async def put_model_rules(request: Request) -> list[dict[str, Any]]:
    """Persist an entire list of ModelRule; return the stored list."""
    try:
        raw = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid JSON: {exc}") from exc

    if not isinstance(raw, list):
        raise HTTPException(
            status_code=422,
            detail={"error_code": "validation", "message": "payload must be a list"},
        )

    try:
        rules = [ModelRule.model_validate(item) for item in raw]
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "validation", "errors": exc.errors()},
        ) from exc

    path = _model_rules_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    store = ModelRulesStore(path=path)
    store.save(rules)
    return [rule.model_dump(mode="json") for rule in rules]


# ---------------------------------------------------------------------------
# /api/settings/classifier
# ---------------------------------------------------------------------------
def _load_classifier_config_from_disk() -> ClassifierConfig | None:
    path = _classifier_config_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ClassifierConfig.model_validate(data)
    except (ValueError, json.JSONDecodeError, ValidationError):
        return None


@router.get("/api/settings/classifier")
async def get_classifier_config() -> dict[str, Any]:
    cfg = _load_classifier_config_from_disk()
    if cfg is None:
        # Return a built-in GLM default.
        cfg = ClassifierConfig(
            enabled=False,
            provider="glm",
            base_url="https://open.bigmodel.cn/api/paas/v4/",
            model_name="glm-4-plus",
        )
    return cfg.model_dump(mode="json")


@router.put("/api/settings/classifier")
async def put_classifier_config(request: Request) -> dict[str, Any]:
    """Persist a ClassifierConfig; rejects plaintext api_key via pydantic forbid.

    T26: forbids ``api_key`` field (only ``api_key_ref`` is accepted); NFR-008
    defense + leak-detector on final payload.
    """
    try:
        raw = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid JSON: {exc}") from exc

    # pydantic extra="forbid" rejects plaintext api_key.
    try:
        cfg = ClassifierConfig.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "validation", "errors": exc.errors()},
        ) from exc

    path = _classifier_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(cfg.model_dump(mode="json"), ensure_ascii=False, indent=2)
    path.write_text(payload, encoding="utf-8")
    return cfg.model_dump(mode="json")


@router.post("/api/settings/classifier/test")
async def test_classifier_connection(request: Request) -> dict[str, Any]:
    """Run ClassifierService.test_connection against the supplied endpoint."""
    try:
        raw = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid JSON: {exc}") from exc

    try:
        req = TestConnectionRequest.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "validation", "errors": exc.errors()},
        ) from exc

    cfg = _load_classifier_config_from_disk() or ClassifierConfig(
        enabled=True,
        provider=req.provider,
        base_url=req.base_url,
        model_name=req.model_name,
    )
    svc = ClassifierService(config=cfg, prompt_store_path=_prompt_store_path())
    result: TestConnectionResult = await svc.test_connection(req)
    return result.model_dump(mode="json")


__all__ = ["router"]
