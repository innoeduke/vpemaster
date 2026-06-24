"""Tests for tools/lint_zindex.py — the Python backup linter."""
from __future__ import annotations

from pathlib import Path

import pytest

from tools import lint_zindex

REPO_ROOT = Path(__file__).resolve().parent.parent
ALLOWED = lint_zindex.load_token_values()


def test_load_token_values_includes_documented_tokens():
    # Sanity check the JSON parses and includes the canonical token names.
    json_text = lint_zindex.TOKENS_FILE.read_text()
    for name in ("z-modal", "z-popover", "z-toast", "z-debug", "z-bg"):
        assert name in json_text, f"token {name} missing from {lint_zindex.TOKENS_FILE}"
    # Real assertion: the loaded set has the expected integer values.
    assert 1000 in ALLOWED  # z-modal
    assert 2000 in ALLOWED  # z-popover
    assert 3000 in ALLOWED  # z-toast
    assert 9999 in ALLOWED  # z-debug
    assert -1 in ALLOWED    # z-bg


def test_scan_html_inline_style_in_range(tmp_path):
    p = tmp_path / "ok.html"
    p.write_text('<div style="z-index: 1000;">x</div>')
    assert lint_zindex.scan_html(p, ALLOWED) == []


def test_scan_html_inline_style_drift(tmp_path):
    p = tmp_path / "bad.html"
    p.write_text('<div style="z-index: 12345;">x</div>')
    violations = lint_zindex.scan_html(p, ALLOWED)
    assert len(violations) == 1
    line, val, kind = violations[0]
    assert val == 12345
    assert kind == "inline style"


def test_scan_html_style_block_in_range(tmp_path):
    p = tmp_path / "ok_block.html"
    p.write_text(
        "<style>\n"
        "  .x { z-index: var(--z-modal); }\n"
        "  .y { z-index: 1000; }\n"
        "</style>"
    )
    assert lint_zindex.scan_html(p, ALLOWED) == []


def test_scan_html_style_block_drift(tmp_path):
    p = tmp_path / "bad_block.html"
    p.write_text(
        "<style>\n"
        "  .x { z-index: 5000; }\n"
        "</style>"
    )
    violations = lint_zindex.scan_html(p, ALLOWED)
    assert len(violations) == 1
    line, val, kind = violations[0]
    assert val == 5000
    assert kind == "<style> block"


def test_scan_js_style_zindex_in_range(tmp_path):
    p = tmp_path / "ok.js"
    p.write_text("el.style.zIndex = '1000';")
    assert lint_zindex.scan_js(p, ALLOWED) == []


def test_scan_js_style_zindex_drift(tmp_path):
    p = tmp_path / "bad.js"
    p.write_text("el.style.zIndex = '99999';")
    violations = lint_zindex.scan_js(p, ALLOWED)
    assert len(violations) == 1
    line, val, kind = violations[0]
    assert val == 99999
    assert kind == "style.zIndex assignment"


def test_scan_js_template_literal_in_range(tmp_path):
    p = tmp_path / "ok_tmpl.js"
    p.write_text("html += `<div style='z-index: 2000;'>x</div>`;")
    assert lint_zindex.scan_js(p, ALLOWED) == []


def test_scan_js_template_literal_drift(tmp_path):
    p = tmp_path / "bad_tmpl.js"
    p.write_text("html += `<div style='z-index: 12345;'>x</div>`;")
    violations = lint_zindex.scan_js(p, ALLOWED)
    assert len(violations) == 1
    line, val, kind = violations[0]
    assert val == 12345
    assert kind == "template literal"


def test_scan_html_multiple_violations(tmp_path):
    p = tmp_path / "multi.html"
    p.write_text(
        '<div style="z-index: 1000;">a</div>\n'  # OK
        '<div style="z-index: 5000;">b</div>\n'  # drift
        '<div style="z-index: 8000;">c</div>\n'  # drift
    )
    violations = lint_zindex.scan_html(p, ALLOWED)
    assert len(violations) == 2
    assert [v[1] for v in violations] == [5000, 8000]


def test_real_repo_has_no_drift_after_normalization():
    """After the drift fixes land, running the linter against the real tree
    should produce zero violations. If this fails, the drift in the repo is
    out of sync with the token allowlist."""
    violations = []
    for f in lint_zindex.TEMPLATES_DIR.rglob("*.html"):
        for line, val, kind in lint_zindex.scan_html(f, ALLOWED):
            violations.append((f, line, val, kind))
    for f in lint_zindex.JS_DIR.rglob("*.js"):
        for line, val, kind in lint_zindex.scan_js(f, ALLOWED):
            violations.append((f, line, val, kind))
    if violations:
        msgs = [f"  {f.relative_to(REPO_ROOT)}:{l}  z-index: {v}  ({k})" for f, l, v, k in violations]
        pytest.fail("z-index drift remains in repo:\n" + "\n".join(msgs))
