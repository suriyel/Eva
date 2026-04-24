#!/usr/bin/env bash
# T26 / AC#7 — tokens.css byte-identical :root block vs prototype.
# Fails when :root content of apps/ui/src/theme/tokens.css drifts from
# docs/design-bundle/eava2/project/styles/tokens.css (the allowed additions — §2.5
# Chinese typography + §2.2 prefers-reduced-motion — live OUTSIDE :root so they are
# ignored here). Exit 0 on match, 1 on drift.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROTO="${ROOT}/docs/design-bundle/eava2/project/styles/tokens.css"
OURS="${ROOT}/apps/ui/src/theme/tokens.css"
[ -f "${PROTO}" ] || { echo "prototype tokens.css not found: ${PROTO}" >&2; exit 1; }
[ -f "${OURS}" ] || { echo "our tokens.css not found: ${OURS}" >&2; exit 1; }

extract_root() {
  awk '/:root[[:space:]]*\{/{flag=1} flag{print} /}/{if(flag){flag=0; exit}}' "$1"
}

diff <(extract_root "${PROTO}") <(extract_root "${OURS}") >/dev/null && exit 0
echo "tokens :root drift detected" >&2
diff <(extract_root "${PROTO}") <(extract_root "${OURS}") >&2 || true
exit 1
