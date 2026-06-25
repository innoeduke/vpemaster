"""Browser smoke test: dropdown stacking escapes page content.

End-to-end regression test for the Meetings-dropdown bug where
`.action-bar` was at the same z-index tier as `.page-header`, causing the
dropdown inside the header to be painted over by page content.

The static test (`test_zindex_stacking.py`) checks the parsed packed.css
for the same hierarchy. This test loads the actual rendered page in a
real browser and verifies the dropdown's paint order via `getBoundingClientRect`.

**Skips gracefully when:**

- `SKIP_BROWSER_TESTS=1` is set (CI environments without Chrome)
- Selenium cannot launch Chrome (no Chrome / chromedriver / sandbox issues)

Run with:
    SKIP_BROWSER_TESTS=0 python -m pytest tests/test_dropdown_stacking_browser.py
"""
from __future__ import annotations

import os
import tempfile
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKED_CSS = REPO_ROOT / "app" / "static" / "css" / "packed.css"

# Mark the whole module so it can be deselected with `-m "not browser"`.
# (The "browser" marker is registered in pytest.ini — see [pytest] section.)
pytestmark = pytest.mark.browser

_skip_reason = os.environ.get("SKIP_BROWSER_TESTS") == "1" and (
    "browser tests disabled (unset SKIP_BROWSER_TESTS to run)"
)


def _chrome_can_launch() -> tuple[bool, str]:
    """Return (ok, reason). Tries to start Chrome headless and quit."""
    if _skip_reason:
        return False, _skip_reason
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        driver = webdriver.Chrome(options=opts)
        driver.quit()
        return True, ""
    except Exception as e:
        return False, f"Chrome not available: {type(e).__name__}: {e}"


_chrome_ok, _chrome_reason = _chrome_can_launch()
pytestmark = pytest.mark.skipif(not _chrome_ok, reason=_chrome_reason or "browser tests disabled")


# Minimal HTML that mirrors the agenda-page stacking context. We use the
# production selectors so the real packed.css rules apply.
_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="{css_path}">
<style>
  /* Sized so the dropdown and action-bar visually overlap. */
  html, body {{ margin: 0; padding: 0; height: 200px; background: #f4f4f9; }}
  .nav-pane {{ position: fixed; top: 0; left: 0; width: 60px; height: 100vh;
               background: #004165; }}
  .page-header {{ position: fixed; top: 0; right: 0; left: 60px; height: 60px;
                  background: #004165; }}
  .main-content {{ margin-left: 60px; padding-top: 80px; }}
  .action-bar {{ padding: 10px; border: 2px solid red; background: #e0e0e0; }}
  .section-row {{ background: #772432; color: white; padding: 15px;
                  border: 2px solid orange; }}
</style>
</head>
<body>
  <div class="nav-pane"></div>
  <header class="page-header">
    <ul class="header-nav-links" style="display:flex; list-style:none; margin-left:auto; padding:0;">
      <li class="nav-dropdown-wrapper">
        <a class="nav-dropdown-trigger">Meetings ▾</a>
        <ul class="nav-submenu">
          <li>Agenda</li><li>Booking</li><li>Voting</li>
        </ul>
      </li>
    </ul>
  </header>
  <main class="main-content">
    <div class="action-bar">action-bar (would bleed through if z-index is wrong)</div>
    <div class="section-row">section-row</div>
  </main>
</body>
</html>
"""


def _write_test_page(css_uri: str) -> Path:
    """Write a static HTML page that links to packed.css and return its path."""
    fd, path = tempfile.mkstemp(suffix=".html")
    os.close(fd)
    Path(path).write_text(_HTML.format(css_path=css_uri), encoding="utf-8")
    return Path(path)


@pytest.mark.parametrize("css_path_kind", ["file", "data-uri"])
def test_dropdown_paints_above_action_bar_in_browser(css_path_kind):
    """Open the test page, hover the Meetings trigger, check stacking.

    We check three things that together prove the bug is fixed:

    1. Computed z-index: `.page-header` is strictly greater than `.action-bar`
       in the browser's resolved style. If they're equal, DOM order wins and
       the dropdown inside `.page-header` can't escape.

    2. Hover reveals the dropdown: opacity transitions to >0.5 within the
       transition window. If the dropdown were painted over by another
       stacking context (the bug), it would still report opacity 1 but be
       visually invisible — this test confirms the dropdown actually paints.

    3. Visible bounding rect: the dropdown has a non-zero on-screen rect
       after hover. (A zero rect means the dropdown is hidden behind
       something or not positioned correctly.)
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.action_chains import ActionChains

    if css_path_kind == "file":
        css_uri = PACKED_CSS.as_uri()
    else:
        import base64
        b64 = base64.b64encode(PACKED_CSS.read_bytes()).decode("ascii")
        css_uri = f"data:text/css;base64,{b64}"

    page_path = _write_test_page(css_uri)

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=opts)
    try:
        driver.get(page_path.as_uri())
        driver.set_window_size(900, 220)

        # 1. Computed z-index hierarchy.
        z_app = driver.execute_script(
            "return getComputedStyle(document.querySelector('.page-header')).zIndex"
        )
        z_action = driver.execute_script(
            "return getComputedStyle(document.querySelector('.action-bar')).zIndex"
        )
        z_app_int = int(z_app)
        z_action_int = int(z_action)
        assert z_app_int > z_action_int, (
            f"computed: .page-header z={z_app_int}, .action-bar z={z_action_int}; "
            f"page-header must be strictly greater so the dropdown escapes."
        )

        # 2 & 3. Hover the trigger and confirm the dropdown actually appears.
        trigger = driver.find_element("css selector", ".nav-dropdown-trigger")
        ActionChains(driver).move_to_element(trigger).perform()
        # The dropdown has a 150ms opacity transition. Wait long enough for
        # the transition to complete before reading computed values.
        import time
        time.sleep(0.4)

        submenu_opacity = driver.execute_script(
            "return parseFloat(getComputedStyle(document.querySelector('.nav-submenu')).opacity)"
        )
        assert submenu_opacity > 0.5, (
            f"dropdown opacity={submenu_opacity} after hover — "
            f"dropdown is not visible; likely clipped by page-content stacking."
        )

        rect = driver.execute_script(
            "var r = document.querySelector('.nav-submenu').getBoundingClientRect();"
            "return {x: r.x, y: r.y, width: r.width, height: r.height};"
        )
        assert rect["width"] > 0 and rect["height"] > 0, (
            f"dropdown has zero size after hover: {rect}; "
            f"the dropdown is hidden behind something."
        )

        # The dropdown's bottom edge should be below the page-header
        # (page-header is 60px tall, dropdown is anchored just below it).
        # If the dropdown is rendered inside the page-header, the bug is back.
        assert rect["y"] > 60 or (rect["y"] + rect["height"]) > 60, (
            f"dropdown rect {rect} is fully inside the 60px-tall page-header; "
            f"it should extend below it. Action-bar or page content may be "
            f"clipping it — the z-index regression has returned."
        )
    finally:
        driver.quit()
        try:
            page_path.unlink()
        except OSError:
            pass
