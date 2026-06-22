# Front-end Z-Index Scale

This document defines the canonical z-index scale for `vpemaster` front-end components. CSS and inline `style="z-index: ..."` declarations must use values from this scale. Code that disagrees with this doc is wrong; update the code and the doc in the same change.

The scale is anchored on round numbers with breathing room inside each tier, so future additions slot in without renumbering the rest of the stack.

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

Any value `>= 9999` must be reserved for diagnostic overlays only. Production CSS must not depend on it. If you find yourself reaching for `z-index: 9999` to "force it on top," the right fix is to put the component in the correct tier (usually T7 or T8), not to escape the scale.

### Within-tier ordering

Each tier's range has 90–900 numbers of room. If two components within the same tier must have a guaranteed order, place the lower one at the tier's lower bound and the higher one at the tier's upper bound. Example: a backdrop at `1000` and its dialog at `1010`; a date picker dropdown at `2000` and its tooltip at `2010`.

---

## How to apply

1. Identify the role of the component (modal, popover, toast, sticky bar, etc.).
2. Pick a value inside the matching tier's range.
3. If the component is *inside* another component of a higher tier (e.g., a date picker inside a modal), make sure its value still sits above the outer component's tier — popovers must beat modals, modals must beat app chrome, etc.
4. Avoid magic numbers that don't correspond to a tier anchor. If you see `z-index: 1005` in a template, treat it as a drift from `1000` and consolidate.
5. When reviewing templates, flag any value that:
   - Lands outside the tier its component belongs in (a modal at `2001` is in the popover tier).
   - Lands in the right tier but breaks the *within-tier* ordering (a popover at `2100` shadowed by a popover at `2050` that should sit above it).
   - Uses a magic number where a tier anchor would do.
   - Stacks two components at the same value where their relationship matters.

---

## Mapping of existing values (audit baseline)

Found during the initial scan. Items flagged with `⚠` are drift and should be normalized.

| File | Line | Current value | Should be | Notes |
|------|------|---------------|-----------|-------|
| `app/static/css/checkin-mobile.css` | 63 | `5` | T3 inline | OK |
| `app/static/css/checkin-mobile.css` | 159 | `50` | T4 sticky | OK |
| `app/static/css/core/navigation.css` | 15, 195 | `100` | T5 app chrome | OK |
| `app/static/css/core/navigation.css` | 74, 237, 387 | `1`, `2` | T3 inline | OK |
| `app/static/css/core/navigation.css` | 491 | `102` | T5 app chrome | OK |
| `app/static/css/core/responsive.css` | 13 | `300` | T5 app chrome | OK |
| `app/static/css/core/responsive.css` | 111 | `100` | T5 app chrome | OK |
| `app/static/css/core/responsive.css` | 124 | `1` | T3 inline | OK |
| `app/static/css/core/responsive.css` | 135 | `2` | T3 inline | OK |
| `app/static/css/core/responsive.css` | 142 | `1002` | T6 modal | OK |
| `app/static/css/core/responsive.css` | 228 | `95` | T4 sticky | OK |
| `app/static/css/core/responsive.css` | 266 | `90` | T4 sticky | OK |
| `app/static/css/core/responsive.css` | 523, 593 | `102` | T5 app chrome | OK |
| `app/templates/_duplicate_modal.html` | 1 | `1005` | `1000` – `1010` | `⚠` Magic number, drift from `1000` |
| `app/templates/clubs.html` | 381 | `2000` | `1000` – `1999` (T6) | `⚠` Modal placed in popover tier |
| `app/templates/partials/_program_template_modal.html` | 97 | `2001` | `1000` – `1999` (T6) | `⚠` Modal placed in popover tier |
| `app/templates/partials/_user_modal.html` | 82 | `2001` | `1000` – `1999` (T6) | `⚠` Modal placed in popover tier |
| `app/static/js/settings.js` | 745 | `9999` | T8 toasts (or T9 if debug) | `⚠` Needs classification |
| `app/static/js/user_form.js` | 42 | `10000` | T8 toasts (or T9 if debug) | `⚠` Needs classification |

### Summary

- **Most values are in the correct tier.** Existing in-page stacking (T3, T4, T5) is consistent.
- **Modals are split across two tiers** — `_duplicate_modal.html` uses T6 (`1005`) while the other three modals sit in T7 (`2000`, `2001`). All four should be in T6.
- **Two JS files use `9999` / `10000`** — both look like "force on top" hacks rather than debug overlays. If they are not diagnostics, they should drop to T8.