#!/usr/bin/env python3
"""
Analyze token usage of long-task-agent skill files.

Reports token estimates for each skill file to help optimize prompt size.
Uses a simple word-based approximation (1 token ≈ 0.75 words for English,
adjusted for markdown/code which tends to have more tokens per word).

Usage:
    python analyze-tokens.py [skill-dir]

If skill-dir is not specified, defaults to the parent directory of this script's location.
"""

import os
import sys


def estimate_tokens(text: str) -> int:
    """Estimate token count. Rough approximation: ~1.3 tokens per word for mixed content."""
    words = len(text.split())
    chars = len(text)
    # Use a blend: word-based and char-based estimates
    word_estimate = int(words * 1.3)
    char_estimate = int(chars / 4)  # ~4 chars per token average
    return (word_estimate + char_estimate) // 2


def analyze_directory(root_dir: str):
    """Analyze all markdown and code files in the skill directory."""
    results = []
    total_tokens = 0

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip hidden dirs and __pycache__
        dirnames[:] = [d for d in dirnames if not d.startswith('.') and d != '__pycache__']

        for filename in sorted(filenames):
            if not any(filename.endswith(ext) for ext in ['.md', '.py', '.sh', '.ps1', '.json', '.js']):
                continue

            filepath = os.path.join(dirpath, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
            except (UnicodeDecodeError, PermissionError):
                continue

            tokens = estimate_tokens(content)
            lines = content.count('\n') + 1
            rel_path = os.path.relpath(filepath, root_dir)
            results.append((rel_path, tokens, lines, len(content)))
            total_tokens += tokens

    return results, total_tokens


def main():
    if len(sys.argv) > 1:
        root = sys.argv[1]
    else:
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')

    root = os.path.abspath(root)
    print(f"=== Token Analysis: {root} ===\n")

    results, total = analyze_directory(root)

    if not results:
        print("No files found.")
        return

    # Sort by token count descending
    results.sort(key=lambda x: x[1], reverse=True)

    # Print table
    print(f"{'File':<55} {'Tokens':>8} {'Lines':>7} {'Chars':>8} {'%':>6}")
    print("-" * 86)

    for rel_path, tokens, lines, chars in results:
        pct = (tokens / total * 100) if total > 0 else 0
        print(f"{rel_path:<55} {tokens:>8,} {lines:>7,} {chars:>8,} {pct:>5.1f}%")

    print("-" * 86)
    print(f"{'TOTAL':<55} {total:>8,}")

    # Warnings for large files
    print("\n=== Size Warnings ===")
    warnings = [(r, t) for r, t, _, _ in results if t > 2000]
    if warnings:
        for rel_path, tokens in warnings:
            print(f"  WARNING: {rel_path} (~{tokens:,} tokens) — consider splitting or summarizing")
    else:
        print("  All files within reasonable size limits.")

    # Category breakdown
    print("\n=== Category Breakdown ===")
    categories = {}
    for rel_path, tokens, _, _ in results:
        parts = rel_path.replace('\\', '/').split('/')
        cat = parts[0] if len(parts) > 1 else 'root'
        categories[cat] = categories.get(cat, 0) + tokens

    for cat in sorted(categories, key=categories.get, reverse=True):
        pct = (categories[cat] / total * 100) if total > 0 else 0
        print(f"  {cat:<25} {categories[cat]:>8,} tokens ({pct:.1f}%)")


if __name__ == "__main__":
    main()
