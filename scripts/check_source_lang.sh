#!/usr/bin/env bash
# NFR-010 source-language guard — only Simplified Chinese allowed in user-visible strings.
# Scans apps/ui/src/**/*.{ts,tsx} for suspicious English business strings (length >=5 alpha runs
# inside quoted strings). Excludes: imports, CSS var refs, technical identifier whitelist, tests,
# type-only declarations.
# Exit 0 when clean, 1 when violation detected.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${ROOT}/apps/ui/src"
if [ ! -d "${SRC}" ]; then
  echo "check_source_lang: source dir not found: ${SRC}" >&2
  exit 0
fi

# Whitelist of technical tokens that are allowed to appear as quoted strings.
WHITELIST='^(claude|opencode|hns-pulse|Harness|http://|ws://|/ws/|/api/|application/json|text/html|Content-Type|Bearer|Accept|react-router-dom|react-query|Inter|JetBrains|PingFang|Microsoft|Segoe|Consolas|Menlo|Fira|cv11|ss01|ss03|calt|GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)$'

violations=0
while IFS= read -r file; do
  # Skip tests and __tests__/__sanity__ directories.
  if [[ "${file}" == *"__tests__"* || "${file}" == *"__sanity__"* || "${file}" == *".test."* || "${file}" == *".spec."* ]]; then
    continue
  fi
  # Extract quoted strings with >=5 consecutive letters, skip import / require / export lines.
  while IFS= read -r line_with_match; do
    # Skip CSS var(--…) usages and path-like strings and imports.
    if echo "${line_with_match}" | grep -Eq '^[[:space:]]*(import|export)[[:space:]]'; then
      continue
    fi
    candidate="$(echo "${line_with_match}" | grep -oE '"[^"]{5,}"|'\''[^'\'']{5,}'\'' ' || true)"
    for tok in ${candidate}; do
      stripped="$(echo "${tok}" | sed -e 's/^["'\'']//' -e 's/["'\'']$//')"
      # Require: 5+ consecutive English letters (business text smell)
      if ! echo "${stripped}" | grep -Eq '[A-Za-z]{5,}'; then
        continue
      fi
      # Skip if matches whitelist entirely
      if echo "${stripped}" | grep -Eq "${WHITELIST}"; then
        continue
      fi
      # Skip if contains CJK (so it's Chinese with some English mixed in — OK)
      if echo "${stripped}" | grep -Pq '[\x{4e00}-\x{9fff}]'; then
        continue
      fi
      # Skip kebab/snake technical ids
      if echo "${stripped}" | grep -Eq '^[a-z][a-z0-9_-]*$' && [ ${#stripped} -lt 20 ]; then
        continue
      fi
      echo "[NFR-010] suspect English business string in ${file}: ${stripped}" >&2
      violations=$((violations + 1))
    done
  done < <(grep -En '["'\''][^"'\'']{5,}["'\'']' "${file}" 2>/dev/null || true)
done < <(find "${SRC}" -type f \( -name '*.ts' -o -name '*.tsx' \) -not -path '*/node_modules/*')

if [ "${violations}" -gt 0 ]; then
  echo "check_source_lang: ${violations} potential NFR-010 violation(s)" >&2
  exit 1
fi
exit 0
