"""F23 · /api/settings/general GET + PUT (Design §6.2.4 GeneralSettings).

Persists to ``$HARNESS_HOME/config.json`` (defaults to ``~/.harness``).
Schema: a free-form object with at least ``ui_density`` (Design §6.2.4 minimal
field — Wave 3 may add more; ``extra='allow'`` keeps the surface stable).

F22 IAPI-002 / IAPI-014 / NFR-008 surface contract:
  * GET response always carries ``keyring_backend`` ∈ {'native','keyrings.alt','fail'}
    + ``api_key_masked`` (string starting with '***' or null) + ``api_key_ref``.
  * PUT accepts ``api_key_plaintext`` in the request body (lifecycle: request only).
    The PUT response NEVER echoes the plaintext field; it is masked to '***xxx'
    and persisted via keyring (IFR-006), with disk config.json carrying only
    ``api_key_ref`` (NFR-008 measurement: grep config dir → no plaintext).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, ValidationError


_PLAINTEXT_FIELD = "api_key_plaintext"
_DEFAULT_KEYRING_SERVICE = "harness-classifier"
_DEFAULT_KEYRING_USER = "default"


class GeneralSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    ui_density: str = "comfortable"


router = APIRouter()


def _config_path() -> Path:
    home = os.environ.get("HARNESS_HOME") or str(Path.home() / ".harness")
    return Path(home) / "config.json"


def _detect_keyring_backend() -> str:
    """Probe keyring backend; 'native' on macOS/Windows/freedesktop, else 'keyrings.alt' / 'fail'."""
    try:
        import keyring

        kr = keyring.get_keyring()
        name = type(kr).__module__ + "." + type(kr).__name__
        # Native backends (macOS Keychain / freedesktop SecretService / Win Credential)
        if any(
            sig in name.lower()
            for sig in ("macos", "secretservice", "windows", "wincred", "kwallet")
        ):
            return "native"
        if (
            "keyrings.alt" in name.lower()
            or "plaintext" in name.lower()
            or "encrypted" in name.lower()
        ):
            return "keyrings.alt"
        if "fail" in name.lower() or "null" in name.lower():
            return "fail"
        # Default conservative fallback when shape is unknown
        return "keyrings.alt"
    except Exception:
        return "fail"


def _mask_plaintext(plaintext: str | None) -> str | None:
    """Return '***' + last 3 chars (or all if shorter)."""
    if not plaintext:
        return None
    suffix = plaintext[-3:] if len(plaintext) >= 3 else plaintext
    return f"***{suffix}"


def _persist_keyring(plaintext: str, ref: dict[str, str]) -> None:
    """Best-effort keyring write; swallow backend errors (FE only sees ref/masked)."""
    try:
        import keyring

        keyring.set_password(ref["service"], ref["user"], plaintext)
    except Exception:
        # Backend may be `fail` or unavailable — caller still proceeds with
        # masked-only response; NFR-008 disk-write filter strips plaintext.
        pass


def _load_settings_dict() -> dict[str, Any]:
    """Load raw settings dict from disk (config.json); never raises."""
    path = _config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _build_response(stored: dict[str, Any]) -> dict[str, Any]:
    """Compose the FE-consumed surface from disk + keyring detection.

    Output always includes: ui_density, keyring_backend, api_key_ref, api_key_masked.
    NEVER includes api_key_plaintext.
    """
    out: dict[str, Any] = {
        "ui_density": stored.get("ui_density", "comfortable"),
    }
    # Carry through any extra fields the user persisted, except plaintext.
    for k, v in stored.items():
        if k == _PLAINTEXT_FIELD:
            continue
        if k not in out:
            out[k] = v
    out["keyring_backend"] = _detect_keyring_backend()
    out["api_key_ref"] = stored.get("api_key_ref")
    out["api_key_masked"] = stored.get("api_key_masked")
    return out


@router.get("/api/settings/general")
async def get_general() -> dict[str, Any]:
    return _build_response(_load_settings_dict())


@router.put("/api/settings/general")
async def put_general(request: Request) -> dict[str, Any]:
    raw = await request.json()
    if not isinstance(raw, dict):
        raise HTTPException(
            status_code=400, detail={"error_code": "validation", "message": "body must be object"}
        )
    plaintext = raw.pop(_PLAINTEXT_FIELD, None)

    # Validate the rest with the (extra='allow') schema for forward-compat.
    try:
        settings = GeneralSettings.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400, detail={"error_code": "validation", "errors": exc.errors()}
        )

    on_disk = settings.model_dump(mode="json")
    # When plaintext is supplied, derive masked + ref and persist via keyring.
    if isinstance(plaintext, str) and plaintext:
        ref = {"service": _DEFAULT_KEYRING_SERVICE, "user": _DEFAULT_KEYRING_USER}
        _persist_keyring(plaintext, ref)
        on_disk["api_key_ref"] = ref
        on_disk["api_key_masked"] = _mask_plaintext(plaintext)
    else:
        # Preserve previously stored ref/masked when caller did not change them.
        prev = _load_settings_dict()
        if "api_key_ref" not in on_disk and "api_key_ref" in prev:
            on_disk["api_key_ref"] = prev["api_key_ref"]
        if "api_key_masked" not in on_disk and "api_key_masked" in prev:
            on_disk["api_key_masked"] = prev["api_key_masked"]

    # NFR-008: never write plaintext to disk.
    on_disk.pop(_PLAINTEXT_FIELD, None)

    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(on_disk, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # Response shape: never echo plaintext.
    return _build_response(on_disk)


__all__ = ["router", "GeneralSettings"]
