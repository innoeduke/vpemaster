# Front-end Z-Index Scale

This document defines the canonical z-index scale for `vpemaster` front-end components. CSS, Jinja templates, and JavaScript must use **named tokens from the scale** — never raw integers. Code that disagrees with this doc is wrong; update the code and the doc in the same change.

The scale is anchored on round numbers with breathing room inside each tier, so future additions slot in without renumbering the rest of the stack.

---

## Tier token system

Every z-index value in the codebase must reference one of the tokens defined in
[`app/static/css/core/zindex.css`](../app/static/css/core/zindex.css). The JSON
manifest in [`tools/zindex-tokens.json`](../tools/zindex-tokens.json) is the
single source of truth for the lint rule and the Python backup linter; the CSS
file is its human-readable mirror and must stay in sync.

```css
:root {
  --z-bg-back:     -2;  /* T1 deepest */
  --z-bg:          -1;  /* T1: behind flow */
  --z-base:         0;  /* T2: default */
  --z-inline:       1;  /* T3 low */
  --z-inline-high:  9;  /* T3 high */
  --z-sticky:      10;  /* T4 low */
  --z-sticky-high: 90;  /* T4 high */
  --z-app:        100;  /* T5 low: nav, sidebar */
  --z-app-mid:    300;  /* T5 mid: drawer, FAB */
  --z-app-high:   999;  /* T5 high: banner alerts */
  --z-modal:     1000;  /* T6 low: modal backdrop / dialog */
  --z-modal-mid: 1100;  /* T6 high: nested modal */
  --z-popover:   2000;  /* T7 low: dropdown, tooltip, date picker */
  --z-popover-mid:  2100;  /* T7 mid: popover above popover */
  --z-popover-high: 2500;  /* T7 high: stacked popovers */
  --z-toast:     3000;  /* T8: flash messages and transient feedback */
  --z-debug:     9999;  /* T9: dev-only — never allowed in production CSS */
}
```

---

## Tiers

| Tier | Range | Role | Example components |
|------|-------|------|--------------------|
| **T1 — Below flow** | `< 0` | Decorative layers rendered *behind* in-flow content. | Background gradients behind transparent text, image underlays. |
| **T2 — Default** | `0` | Normal document flow. | Page body, cards, lists, tables. |
| **T3 — Inline** | `1` – `9` | Tiny within-component stacking. | Avatar overlap on a row, badge inside a card, focused-input ring. |
| **T4 — Sticky** | `10` – `99` | Elements pinned during scroll within their container. | Sticky table headers, sticky filter/segmented bar. |
| **T5 — App chrome** | `100` – `999` | Persistent app-level UI that floats above content. | Top nav, sidebar, mobile drawer, FAB, banner alerts. |
| **T6 — Modal** | `1000` – `1999` | Focus-capturing dialogs (backdrop + dialog). | `.modal`, `.planner-modal`, off-canvas panels, lightbox. |
| **T7 — Popovers** | `2000` – `2999` | Floating UI that must escape modal clipping. | Dropdowns, date pickers, tooltips, autocomplete, context menus. |
| **T8 — Toasts** | `3000` – `3999` | Top-most system feedback. | Flask flash messages, error toasts, transient notifications. |
| **T9 — Debug** | `9999+` | Reserved for diagnostics. Never ship in production CSS. | Performance overlay, dev-only panels. |

---

## Design decisions

### Popovers sit *above* modals (T7 > T6)

When a popover (date picker, dropdown, tooltip) is rendered inside a modal, it must remain visible — otherwise the modal's stacking context would clip it. The recently-fixed date range picker bug is the same family of problem.

Components that always appear *over* modals belong in T7, not T6. T6 is reserved for the modal itself (backdrop and dialog).

### T9 (debug) is off-limits in production

`var(--z-debug)` is only legal in CSS files matching the dev-file pattern
(`**/*-dev.css`, `**/debug*.css`, `**/dev-*.css`). Production CSS must not use
it. If you find yourself reaching for `z-index: 9999` to "force it on top," the
right fix is to pick the correct tier (usually T7 or T8), not to escape the
scale.

### Within-tier ordering

Each tier's range has 90–900 numbers of room. If two components within the
same tier must have a guaranteed order, use the low and high anchors for that
tier (e.g. `--z-popover` and `--z-popover-high`). The token system only
exposes the anchors we actually need; if a new within-tier ordering
requirement shows up, add a new token to both `zindex.css` and
`zindex-tokens.json`.

---

## How to apply

1. Identify the role of the component (modal, popover, toast, sticky bar, etc.).
2. Pick the matching token from the table above.
3. Use it in CSS as `z-index: var(--z-<token>);` or in templates/JS as a
   string in the corresponding `style="..."` or `element.style.zIndex = ...`.
4. **Never** use a raw integer. The lint will reject it.
5. If a new tier is needed, add it to:
   - `app/static/css/core/zindex.css` (the CSS variable definition)
   - `tools/zindex-tokens.json` (the JSON manifest for the linter)
   - This doc (the table)
   All three in the same change.

---

## Linter

Two linters enforce the policy:

- **`make lint-css`** — Stylelint with the custom rule
  `vpe/zindex-token` (see [`tools/stylelint-plugin-vpe-zindex/`](../tools/stylelint-plugin-vpe-zindex/)).
  Walks every file under `app/static/css/`.
- **`make lint-zindex`** — Python script
  ([`tools/lint_zindex.py`](../tools/lint_zindex.py)) that greps
  `app/templates/**/*.html` and `app/static/js/**/*.js`. Catches inline
  `style="z-index: N"` and `element.style.zIndex = 'N'` that Stylelint can't
  see.

Both run as part of `make lint` (which also runs flake8 on Python code).
Add new tiers, lint, and the existing CI will catch drift.
