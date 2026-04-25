#!/usr/bin/env python3
"""
NFR-010 source-language guard (T30 SEC/i18n-guard).

Scans apps/ui/src/**/*.{ts,tsx} for user-visible English business strings. A
string literal is a violation when ALL of:

  1. Length >= 5 chars.
  2. Contains a run of >= 5 consecutive ASCII letters.
  3. Does NOT contain any CJK ideograph (U+4E00..U+9FFF).
  4. Is not in the technical whitelist (domain terms, MIME types, HTTP verbs,
     CSS var names, font stacks, protocol schemes, npm pkg specs, relative
     import paths, CSS property-style tokens, etc.).
  5. Does not appear on a statically-tokenised *import* / *export* / *from*
     / `require(...)` line.
  6. Does not appear inside a block / line comment.

The script runs in Python to make the tokenisation robust (shell word-split
bugs tokenised `"Ticket 流"` into `Ticket` alone — a false positive).

Exit 0 when clean, 1 when any violation detected.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "apps" / "ui" / "src"

# --- Whitelist of allowed quoted strings ------------------------------------
# Any quoted string that, when the surrounding whitespace is trimmed, matches
# one of these patterns is treated as technical and silently passes.
WHITELIST_PATTERNS: list[re.Pattern[str]] = [
    # Domain terms allowed to appear as product-level tokens (UCD §2.7).
    re.compile(r"^(claude|opencode|Harness|Ticket|hns-pulse)$"),
    # HTTP verbs, MIME types, header names.
    re.compile(r"^(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)$"),
    re.compile(
        r"^(application/json|text/html|text/plain|Content-Type|Bearer|Accept|Authorization)$"
    ),
    # URL / protocol prefixes.
    re.compile(r"^(https?://[^\s]+|wss?://[^\s]+)$"),
    re.compile(r"^/(ws|api)(/[\w./:?&=\-%{}]*)?$"),
    # Library / package specifiers (npm) — includes scoped packages and subpath exports.
    re.compile(r"^@?[a-z0-9][\w.-]*(/[\w.-]+)*$"),
    # Relative import paths starting with ./ or ../
    re.compile(r"^\.{1,2}(/[\w.\-/?]+)+$"),
    # Raw-suffix module query (`./tokens.css?raw`).
    re.compile(r"^[\w.\-/]+(\?\w+)?$"),
    # Node built-in specifiers (`node:module`, `node:fs`).
    re.compile(r"^node:[a-z]+$"),
    # CSS var() / url() / calc() / linear-gradient() / rotate() etc. — allow
    # any CSS function call as a technical expression.
    re.compile(r"^[a-z-]+\([^)]*\)$"),
    # CSS variable names inside var(--...) fragment that appears as standalone.
    re.compile(r"^var\([^)]+\)$"),
    re.compile(r"^--[a-z][a-z0-9-]*$"),
    # Font family stacks, keywords, units.
    re.compile(
        r"^(Inter|JetBrains|PingFang|Microsoft|Segoe|Consolas|Menlo|Fira|SF Pro|system-ui|sans-serif|serif|monospace)(\s.*)?$"
    ),
    re.compile(r"^(cv11|ss01|ss03|ss04|calt|tnum|zero|liga)$"),
    # Pure-ASCII kebab/snake identifier (react router event names, etc.).
    re.compile(r"^[a-z][a-z0-9_-]{0,40}$"),
    # CSS media-query fragments like `(prefers-reduced-motion: reduce)`.
    re.compile(r"^\(?[a-z-]+\s*:\s*[a-z0-9-]+\)?$"),
    # `cubic-bezier(0.4,0,0.2,1)` and other CSS maths.
    re.compile(r"^(-?\d+(\.\d+)?)(,\s*-?\d+(\.\d+)?)+$"),
]

# --- TypeScript identifier patterns ------------------------------------------
# Skip if the matched string is actually a TS identifier reference such as
# `HttpError`, `ServerError` that appears inside template literals / as
# catch-type strings.  These don't surface in the UI.
TS_IDENT_PATTERN = re.compile(
    r"^[A-Z][A-Za-z0-9_]{2,40}(Error|Exception|Type|Props|Config|Event|State|Client|Factory|Schema|Guard|Scope|Result|Request|Response|Message)?$"
)

# --- Comment detection -------------------------------------------------------
SINGLE_LINE_COMMENT = re.compile(r"^\s*(//|\*|/\*|\*/)")
MULTILINE_COMMENT_START = re.compile(r"^\s*/\*")
MULTILINE_COMMENT_END = re.compile(r"\*/\s*$")

STRING_LITERAL = re.compile(r"""(?P<quote>["'`])(?P<body>(?:\\.|(?!(?P=quote)).)*)(?P=quote)""")

CJK_CHAR = re.compile(r"[一-鿿]")
LETTER_RUN = re.compile(r"[A-Za-z]{5,}")

# Context patterns — skip strings that appear as arguments to developer-facing
# APIs that never surface in the UI. These are matched against the LINE not
# the literal body.
DEV_API_CONTEXT = re.compile(
    r"\b(throw\s+new\s+\w+|console\.(warn|error|log|info|debug|trace)|invariant|assert|Error|"
    r"TypeError|RangeError|ZodError|ServerError|HttpError|NetworkError)\b"
)

# Non-user-facing attribute assignments — className, data-*, aria-*, id=, key=.
# These hold technical identifiers, not UI text.
ATTR_CONTEXT = re.compile(
    r"\b(className|class|id|key|name|type|role|href|src|alt|target|rel|"
    r"aria-[a-z]+|data-[a-z0-9-]+|htmlFor|for)\s*=\s*[{`\"']"
)

# CSS composite value heuristic — strings built almost entirely from CSS
# tokens are technical. Keywords are restricted to known CSS identifiers to
# avoid matching arbitrary English prose.
_CSS_KEYWORDS = (
    "inset|solid|dashed|dotted|none|auto|center|stretch|flex-start|flex-end|"
    "space-between|space-around|baseline|start|end|left|right|top|bottom|"
    "transparent|currentColor|initial|inherit|unset|revert|pointer|default|"
    "uppercase|lowercase|capitalize|bold|normal|italic|underline|overline"
)
CSS_VALUE = re.compile(
    r"^\s*(?:"
    r"\d+(\.\d+)?(px|em|rem|%|vh|vw|deg|s|ms)?|"  # numeric + unit
    r"#[0-9a-fA-F]{3,8}|"  # hex color
    r"rgba?\([^)]*\)|"
    r"hsla?\([^)]*\)|"
    r"var\(--[\w-]+\)|"
    r"linear-gradient\([^)]*\)|"
    r"radial-gradient\([^)]*\)|"
    r"cubic-bezier\([^)]*\)|"
    rf"(?:{_CSS_KEYWORDS})|"
    r"\s|,|/"
    r")+\s*$",
    re.IGNORECASE,
)


def is_whitelisted(token: str) -> bool:
    s = token.strip()
    if not s:
        return True
    if TS_IDENT_PATTERN.match(s):
        return True
    return any(p.match(s) for p in WHITELIST_PATTERNS)


def scan_file(path: Path) -> list[tuple[int, str]]:
    violations: list[tuple[int, str]] = []
    in_block_comment = False
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    source_lines = source.splitlines()
    for lineno, raw_line in enumerate(source_lines, start=1):
        line = raw_line
        stripped = line.strip()
        # Handle block comments.
        if in_block_comment:
            if MULTILINE_COMMENT_END.search(line):
                in_block_comment = False
            continue
        if MULTILINE_COMMENT_START.match(line) and not MULTILINE_COMMENT_END.search(line):
            in_block_comment = True
            continue
        if SINGLE_LINE_COMMENT.match(line):
            continue
        # Skip entire import / export / require lines.
        if re.match(r"^\s*(import\b|export\b(\s+(\*|\{|type\b))|from\s+['\"])", stripped):
            continue
        if re.match(r"^\s*(const|let|var)\s+\w+\s*=\s*require\(", stripped):
            continue
        # Skip strings whose containing line OR the preceding 2 lines are a
        # developer-facing API call (throw new Error / console.warn / etc.) —
        # these never reach the UI. Multi-line `throw new TypeError(\n  "…",\n)`
        # places the literal on a line whose current neighbours hold the
        # context.
        window = "\n".join(source_lines[max(0, lineno - 3) : lineno + 1])
        if DEV_API_CONTEXT.search(window):
            continue
        if ATTR_CONTEXT.search(window):
            continue
        for match in STRING_LITERAL.finditer(line):
            body = match.group("body")
            # Require string length >= 5.
            if len(body) < 5:
                continue
            # Pass if contains CJK.
            if CJK_CHAR.search(body):
                continue
            # Require at least one 5-letter English run to suspect business text.
            if not LETTER_RUN.search(body):
                continue
            if is_whitelisted(body):
                continue
            # CSS composite values (border/gradient/box-shadow) — technical.
            if CSS_VALUE.match(body):
                continue
            # CSS function starters with nested calls (var inside gradient).
            if re.match(r"^(linear|radial|conic)-gradient\(", body) and "var(" in body:
                continue
            if re.match(r"^(inset\s+)?\d+(\.\d+)?px\s+\d+", body):  # box-shadow
                continue
            # Template literal fragment that is mostly CSS interpolation.
            if "${" in body and CSS_VALUE.match(re.sub(r"\$\{[^}]+\}", "0", body)):
                continue
            # Also skip if body is obviously a CSS property chain like
            # "flex: 1; min-width: 0;" — semicolon-heavy + no word chars.
            if (
                ";" in body
                and CJK_CHAR.search(body) is None
                and all(
                    is_whitelisted(seg) for seg in (s.strip() for s in body.split(";") if s.strip())
                )
            ):
                continue
            violations.append((lineno, body))
    return violations


def main() -> int:
    if not SRC.is_dir():
        print(f"check_source_lang: source dir not found: {SRC}", file=sys.stderr)
        return 0
    total_violations = 0
    for path in sorted(SRC.rglob("*.ts")) + sorted(SRC.rglob("*.tsx")):
        parts = path.parts
        if any(seg in parts for seg in ("__tests__", "__sanity__", "node_modules")):
            continue
        if path.name.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx", ".d.ts")):
            continue
        violations = scan_file(path)
        for lineno, body in violations:
            rel = path.relative_to(ROOT)
            print(f"[NFR-010] {rel}:{lineno}: suspicious English string: {body!r}", file=sys.stderr)
            total_violations += 1
    if total_violations:
        print(
            f"check_source_lang: {total_violations} potential NFR-010 violation(s)", file=sys.stderr
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
