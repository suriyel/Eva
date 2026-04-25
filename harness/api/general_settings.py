"""F23 · /api/settings/general GET + PUT (Design §6.2.4 GeneralSettings).

Persists to ``$HARNESS_HOME/config.json`` (defaults to ``~/.harness``).
Schema: a free-form object with at least ``ui_density`` (Design §6.2.4 minimal
field — Wave 3 may add more; ``extra='allow'`` keeps the surface stable).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, ValidationError


class GeneralSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    ui_density: str = "comfortable"


router = APIRouter()


def _config_path() -> Path:
    home = os.environ.get("HARNESS_HOME") or str(Path.home() / ".harness")
    return Path(home) / "config.json"


def _load_settings() -> GeneralSettings:
    path = _config_path()
    if not path.exists():
        return GeneralSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return GeneralSettings()
    try:
        return GeneralSettings.model_validate(data)
    except ValidationError:
        return GeneralSettings()


@router.get("/api/settings/general")
async def get_general() -> dict[str, Any]:
    return _load_settings().model_dump(mode="json")


@router.put("/api/settings/general")
async def put_general(request: Request) -> dict[str, Any]:
    raw = await request.json()
    try:
        settings = GeneralSettings.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400, detail={"error_code": "validation", "errors": exc.errors()}
        )
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(settings.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return settings.model_dump(mode="json")


__all__ = ["router", "GeneralSettings"]
