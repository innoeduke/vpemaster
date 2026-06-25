"""Static regression test for z-index stacking hierarchy.

The original bug: `.action-bar` was at `var(--z-app)` (T5, 100) — the same
tier as `.page-header` — so the Meetings dropdown inside the page-header
couldn't escape the header's stacking context (T7 inside T5 paints at T5
in body context, and the action-bar's later-in-DOM T5 won the tie).

This test parses the **built** packed.css and asserts the z-index hierarchy
that the bug violated. It catches regressions cheaply, with no browser.

The rule is: page chrome (`.page-header`, `.nav-pane`) must be in a strictly
higher tier than any per-page chrome (`.action-bar`, sticky page elements).
If they tie, the later-in-DOM wins, and our dropdowns stop working.

Run with: `make test-file FILE=tests/test_zindex_stacking.py`
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKED_CSS = REPO_ROOT / "app" / "static" / "css" / "packed.css"
TOKENS_FILE = REPO_ROOT / "tools" / "zindex-tokens.json"


def _load_token_values() -> dict[str, int]:
    """Return {token-name: integer-value} from tools/zindex-tokens.json."""
    data = json.loads(TOKENS_FILE.read_text(encoding="utf-8"))
    return {name: int(value) for name, value in data["tokens"].items()}


def _resolve_token(value: str, tokens: dict[str, int]) -> int | None:
    """Return the integer value for a z-index declaration.

    Accepts: raw integer ("100"), var(--z-...) ("var(--z-app)"), or
    "auto"/"inherit" (returns None).
    """
    value = value.strip()
    if value.lower() in ("auto", "inherit", "initial", "unset"):
        return None
    # The token name in the JSON file is `z-app` (not just `app`), so prepend
    # the `z-` prefix we strip in the regex.
    m = re.match(r"^var\(\s*--z-([a-z0-9-]+)\s*\)", value)
    if m:
        return tokens.get("z-" + m.group(1))
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return None


def _find_z_index(css_text: str, selector: str) -> str | None:
    """Return the z-index declaration value for any rule matching `selector`.

    Minified CSS can define the same selector multiple times (e.g. once in
    `core/navigation.css` for the base rule, again in `core/responsive.css`
    for a media-query override). We scan every occurrence and return the
    first one that actually declares a z-index — the override without
    z-index doesn't tell us anything about stacking.
    """
    needle = selector + "{"
    start = 0
    while True:
        idx = css_text.find(needle, start)
        if idx < 0:
            return None
        depth = 0
        end = idx
        for i in range(idx, len(css_text)):
            c = css_text[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        block = css_text[idx:end + 1]
        # In minified CSS the final declaration of a block is terminated by
        # `}` rather than `;`, so accept either terminator.
        m = re.search(r"z-index\s*:\s*([^;}]+?)[;}]", block)
        if m:
            return m.group(1).strip()
        start = idx + len(needle)


# --- The actual rule under test --------------------------------------------


def test_packed_css_has_required_chrome_selectors():
    """Sanity check: packed.css should contain all chrome selectors we test."""
    css = PACKED_CSS.read_text(encoding="utf-8") if PACKED_CSS.exists() else ""
    if not css:
        pytest.skip("packed.css not built yet — run `make run` once to build it")
    for sel in (".page-header", ".action-bar", ".nav-submenu", ".nav-pane"):
        assert sel in css, f"selector {sel!r} missing from packed.css"


def test_page_header_zindex_strictly_above_action_bar():
    """Regression: `.page-header` (app chrome) must paint above `.action-bar`.

    Both are siblings in the body's stacking context. If they share a tier
    (same z-index value), DOM order decides paint order and the dropdown
    inside `.page-header` stops working.
    """
    css = PACKED_CSS.read_text(encoding="utf-8") if PACKED_CSS.exists() else ""
    if not css:
        pytest.skip("packed.css not built yet — run `make run` once to build it")

    tokens = _load_token_values()
    ph_raw = _find_z_index(css, ".page-header")
    ab_raw = _find_z_index(css, ".action-bar")
    assert ph_raw is not None, "no z-index on .page-header"
    assert ab_raw is not None, "no z-index on .action-bar"

    ph = _resolve_token(ph_raw, tokens)
    ab = _resolve_token(ab_raw, tokens)
    assert ph is not None, f".page-header z-index {ph_raw!r} did not resolve"
    assert ab is not None, f".action-bar z-index {ab_raw!r} did not resolve"

    assert ph > ab, (
        f".page-header (z-index={ph_raw} → {ph}) must be strictly greater "
        f"than .action-bar (z-index={ab_raw} → {ab}); "
        f"otherwise the Meetings dropdown (z-popover, inside .page-header) "
        f"cannot escape the header's stacking context."
    )


def test_nav_pane_and_page_header_share_tier_or_higher():
    """`.nav-pane` (left sidebar) should be in the same or higher tier as `.page-header`.

    Both are app chrome. They can sit at the same z-index without colliding
    because they don't visually overlap; if they ever did, the test below
    would catch the regression.
    """
    css = PACKED_CSS.read_text(encoding="utf-8") if PACKED_CSS.exists() else ""
    if not css:
        pytest.skip("packed.css not built yet — run `make run` once to build it")

    tokens = _load_token_values()
    np_raw = _find_z_index(css, ".nav-pane")
    ph_raw = _find_z_index(css, ".page-header")
    if np_raw is None or ph_raw is None:
        pytest.skip("nav-pane or page-header z-index missing")
    np = _resolve_token(np_raw, tokens)
    ph = _resolve_token(ph_raw, tokens)
    assert np is not None and ph is not None
    # Both are app chrome — both must be in T5 or above. If either has slipped
    # below T5, the test fails loud.
    assert np >= 100, f".nav-pane at z-index={np_raw} → {np} should be ≥ 100 (T5)"
    assert ph >= 100, f".page-header at z-index={ph_raw} → {ph} should be ≥ 100 (T5)"


def test_dropdown_submenu_above_app_chrome():
    """`.nav-submenu` lives inside `.page-header` and must be T7 (≥ 2000).

    Even though z-popover inside a T5 stacking context paints at T5 in body
    context, the rule itself must reference T7 — that's what makes the
    dropdown *want* to escape. If someone reverts it to a lower tier, the
    styling intent is lost.
    """
    css = PACKED_CSS.read_text(encoding="utf-8") if PACKED_CSS.exists() else ""
    if not css:
        pytest.skip("packed.css not built yet — run `make run` once to build it")

    tokens = _load_token_values()
    raw = _find_z_index(css, ".nav-submenu")
    assert raw is not None, "no z-index on .nav-submenu"
    resolved = _resolve_token(raw, tokens)
    assert resolved is not None, f".nav-submenu z-index {raw!r} did not resolve"
    assert resolved >= 2000, (
        f".nav-submenu z-index={raw} → {resolved}; expected ≥ 2000 (T7 popover). "
        f"Lowering this tier makes the dropdown invisible against page chrome."
    )
