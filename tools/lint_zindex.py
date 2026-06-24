#!/usr/bin/env python3
"""Backup linter for z-index values in Jinja templates and JavaScript.

Stylelint cannot parse HTML or JS, so this script enforces the same token
policy in:
  - app/templates/**/*.html — inline `style="z-index: N"` and `<style>` blocks
  - app/static/js/**/*.js    — `style.zIndex = 'N'` and template literals

It reads tools/zindex-tokens.json as the source of truth. Any integer value
in those files that is not one of the registered token values is reported.
`var(--z-...)` references are accepted by construction.

Exit code 0 on success, 1 if any violations are found.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
TOKENS_FILE = REPO_ROOT / "tools" / "zindex-tokens.json"
TEMPLATES_DIR = REPO_ROOT / "app" / "templates"
JS_DIR = REPO_ROOT / "app" / "static" / "js"

# Regexes ---------------------------------------------------------------------

# Inline style attribute: style="... z-index: 12345; ..."
INLINE_STYLE_RE = re.compile(
    r"""style\s*=\s*["'][^"']*\bz-index\s*:\s*(-?\d+)\b[^"']*["']""",
    re.IGNORECASE,
)

# Inside <style>...</style> blocks: z-index: 12345;
STYLE_BLOCK_RE = re.compile(
    r"""<style\b[^>]*>(?P<body>.*?)</style>""",
    re.IGNORECASE | re.DOTALL,
)
CSS_ZINDEX_RE = re.compile(r"""\bz-index\s*:\s*(-?\d+)\s*[;!]?""", re.IGNORECASE)

# JavaScript: style.zIndex = 'N' or = "N"
JS_STYLE_PROP_RE = re.compile(
    r"""(?:\.style\.zIndex|\[["']z-index["']\])\s*=\s*["'](-?\d+)["']""",
    re.IGNORECASE,
)

# JavaScript template literal containing `z-index: N`
JS_TEMPLATE_LITERAL_RE = re.compile(
    r"""`[^`]*\bz-index\s*:\s*(-?\d+)\b[^`]*`""",
    re.IGNORECASE,
)

# Allowed var(--z-*) form — present in CSS but we should not flag it as raw int.
VAR_REF_RE = re.compile(r"""\bvar\(\s*--z-""", re.IGNORECASE)


def load_token_values() -> set[int]:
    data = json.loads(TOKENS_FILE.read_text(encoding="utf-8"))
    return {int(v) for v in data["tokens"].values()}


def find_style_blocks(text: str) -> Iterable[tuple[int, str]]:
    """Yield (offset, body) for each <style>...</style> block in `text`."""
    for m in STYLE_BLOCK_RE.finditer(text):
        yield m.start("body"), m.group("body")


def line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def scan_html(path: Path, allowed: set[int]) -> list[tuple[int, int, str]]:
    text = path.read_text(encoding="utf-8")
    violations: list[tuple[int, int, str]] = []
    for m in INLINE_STYLE_RE.finditer(text):
        val = int(m.group(1))
        if val in allowed:
            continue
        violations.append((line_for_offset(text, m.start(1)), val, "inline style"))
    for offset, body in find_style_blocks(text):
        # Skip if the block uses var(--z-*) — but be precise: a block with raw
        # integers is still a violation; we don't try to silence the whole
        # block just because it has a var() somewhere.
        for cm in CSS_ZINDEX_RE.finditer(body):
            val = int(cm.group(1))
            if val in allowed:
                continue
            violations.append((line_for_offset(text, offset + cm.start(1)), val, "<style> block"))
    return violations


def scan_js(path: Path, allowed: set[int]) -> list[tuple[int, int, str]]:
    text = path.read_text(encoding="utf-8")
    violations: list[tuple[int, int, str]] = []
    for m in JS_STYLE_PROP_RE.finditer(text):
        val = int(m.group(1))
        if val in allowed:
            continue
        violations.append((line_for_offset(text, m.start(1)), val, "style.zIndex assignment"))
    for m in JS_TEMPLATE_LITERAL_RE.finditer(text):
        val = int(m.group(1))
        if val in allowed:
            continue
        violations.append((line_for_offset(text, m.start(1)), val, "template literal"))
    return violations


def main() -> int:
    allowed = load_token_values()

    html_files = sorted(TEMPLATES_DIR.rglob("*.html"))
    js_files = sorted(JS_DIR.rglob("*.js"))

    all_violations: list[tuple[Path, int, int, str]] = []
    for f in html_files:
        for line, val, kind in scan_html(f, allowed):
            all_violations.append((f, line, val, kind))
    for f in js_files:
        for line, val, kind in scan_js(f, allowed):
            all_violations.append((f, line, val, kind))

    if not all_violations:
        print(f"OK — scanned {len(html_files)} HTML files, {len(js_files)} JS files. No drift.")
        return 0

    print(f"z-index drift found in {len(all_violations)} location(s):\n")
    for f, line, val, kind in all_violations:
        rel = f.relative_to(REPO_ROOT)
        print(f"  {rel}:{line}  z-index: {val}  ({kind})")
    print(
        f"\nAll values must be in tools/zindex-tokens.json. "
        f"Either pick a registered token (var(--z-*)) or add a new token to "
        f"both tools/zindex-tokens.json and app/static/css/core/zindex.css."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
