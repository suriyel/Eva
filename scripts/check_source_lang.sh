#!/usr/bin/env bash
# NFR-010 source-language guard — only Simplified Chinese allowed in user-visible strings.
# Wrapper delegating to Python implementation for robust tokenization + whitelist handling.
# Exit 0 when clean, 1 when violation detected.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "${ROOT}/scripts/check_source_lang.py" "$@"
