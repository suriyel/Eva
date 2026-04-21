#!/usr/bin/env python3
"""Harness 配置检查器 —— Worker 启动每个 feature 前调用。

读取 feature-list.json 的 required_configs[]，逐项核对：
- type == "env"  → 查 os.environ 是否存在且非空（从 .env 文件加载）
- type == "file" → 查 os.path.exists(path) 且文件非空

加载逻辑硬编码，不接受 --dotenv / --format 等格式标志。

用法:
    python scripts/check_configs.py feature-list.json
    python scripts/check_configs.py feature-list.json --feature 3

退出码:
    0 — 所有（或指定 feature 的）必需配置已满足
    1 — 存在未满足的配置（打印缺失列表 + check_hint）
    2 — feature-list.json 无法读取或格式错误
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(dotenv_path: Path) -> dict[str, str]:
    """最小 .env 加载器：KEY=VALUE，`#` 起注释，无引号剥离；空值视为未设。"""
    if not dotenv_path.exists():
        return {}
    loaded: dict[str, str] = {}
    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip()
        # 剥离首尾成对引号
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        if k:
            loaded[k] = v
    return loaded


def load_feature_list(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError, OSError) as exc:
        print(f"[check_configs] ERROR 无法读取 {path}: {exc}", file=sys.stderr)
        sys.exit(2)


def check_env(name: str, key: str, env_sources: dict[str, str]) -> tuple[bool, str]:
    # 优先级：进程 env > .env 文件；空字符串视为未设
    val = os.environ.get(key) or env_sources.get(key, "")
    if val and val.strip():
        return True, ""
    return False, f"env 变量 {key} 未设置或为空（name={name}）"


def check_file(name: str, path: str) -> tuple[bool, str]:
    # 支持相对路径（相对 repo 根）与绝对路径
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    if not p.exists():
        return False, f"文件不存在：{p} (name={name})"
    if p.is_file() and p.stat().st_size == 0:
        return False, f"文件为空：{p} (name={name})"
    return True, ""


def main() -> None:
    ap = argparse.ArgumentParser(description="Harness required_configs 检查器")
    ap.add_argument("feature_list", help="feature-list.json 路径")
    ap.add_argument(
        "--feature",
        type=int,
        default=None,
        help="仅检查被该 feature id 依赖的 config；不指定则检查全部",
    )
    args = ap.parse_args()

    fl_path = Path(args.feature_list).resolve()
    data = load_feature_list(fl_path)
    configs = data.get("required_configs", []) or []

    # 加载 .env（位于 repo 根）
    env_sources = load_dotenv(REPO_ROOT / ".env")

    # 过滤到指定 feature（若给定）
    if args.feature is not None:
        configs = [
            c
            for c in configs
            if isinstance(c, dict) and args.feature in (c.get("required_by") or [])
        ]

    missing: list[tuple[str, str]] = []
    checked = 0
    for cfg in configs:
        if not isinstance(cfg, dict):
            continue
        name = cfg.get("name", "<unnamed>")
        ctype = cfg.get("type")
        hint = cfg.get("check_hint") or cfg.get("description") or ""

        if ctype == "env":
            key = cfg.get("key") or name
            ok, err = check_env(name, key, env_sources)
        elif ctype == "file":
            path = cfg.get("path") or ""
            ok, err = check_file(name, path)
        else:
            ok, err = False, f"未知 type '{ctype}' (name={name})"

        checked += 1
        if not ok:
            missing.append((err, hint))

    if missing:
        scope = f"feature #{args.feature}" if args.feature is not None else "全部"
        print(f"[check_configs] FAIL ({scope}) —— {len(missing)} 项缺失：", file=sys.stderr)
        for err, hint in missing:
            print(f"  - {err}", file=sys.stderr)
            if hint:
                print(f"    hint: {hint}", file=sys.stderr)
        sys.exit(1)

    scope = f"feature #{args.feature}" if args.feature is not None else "全部"
    print(f"[check_configs] OK ({scope}) —— 已检查 {checked} 项 required_configs")
    sys.exit(0)


if __name__ == "__main__":
    main()
