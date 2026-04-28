"""ConfigStore.workdirs 持久化 + helper 单测。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.config.schema import HarnessConfig
from harness.config.store import ConfigStore


def _store(tmp: Path) -> ConfigStore:
    return ConfigStore(tmp / "config.json")


def test_default_config_has_empty_workdirs() -> None:
    cfg = HarnessConfig.default()
    assert cfg.workdirs == []
    assert cfg.current_workdir is None


def test_old_config_loads_with_default_workdirs(tmp_path: Path) -> None:
    """旧 config.json（不含 workdirs）→ pydantic 默认值填充。"""
    p = tmp_path / "config.json"
    p.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "provider_refs": {},
                "retention_run_count": 20,
                "ui_density": "comfortable",
            }
        ),
        encoding="utf-8",
    )
    cfg = ConfigStore(p).load()
    assert cfg.workdirs == []
    assert cfg.current_workdir is None


def test_add_workdir_dedupes_and_persists(tmp_path: Path) -> None:
    s = _store(tmp_path)
    s.add_workdir("/a")
    s.add_workdir("/b")
    cfg = s.add_workdir("/a")  # dedup
    assert cfg.workdirs == ["/a", "/b"]

    # 重新 load 读盘验证持久化
    cfg2 = _store(tmp_path).load()
    assert cfg2.workdirs == ["/a", "/b"]


def test_set_current_must_be_in_workdirs(tmp_path: Path) -> None:
    s = _store(tmp_path)
    s.add_workdir("/x")
    cfg = s.set_current_workdir("/x")
    assert cfg.current_workdir == "/x"

    with pytest.raises(ValueError):
        s.set_current_workdir("/not-registered")


def test_set_current_to_none_is_ok(tmp_path: Path) -> None:
    s = _store(tmp_path)
    s.add_workdir("/y")
    s.set_current_workdir("/y")
    cfg = s.set_current_workdir(None)
    assert cfg.current_workdir is None


def test_remove_workdir_clears_current_when_match(tmp_path: Path) -> None:
    s = _store(tmp_path)
    s.add_workdir("/p")
    s.add_workdir("/q")
    s.set_current_workdir("/p")
    cfg = s.remove_workdir("/p")
    assert cfg.workdirs == ["/q"]
    assert cfg.current_workdir is None


def test_remove_workdir_keeps_current_when_unrelated(tmp_path: Path) -> None:
    s = _store(tmp_path)
    s.add_workdir("/m")
    s.add_workdir("/n")
    s.set_current_workdir("/m")
    cfg = s.remove_workdir("/n")
    assert cfg.workdirs == ["/m"]
    assert cfg.current_workdir == "/m"
