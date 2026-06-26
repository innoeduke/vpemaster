---
name: SQL Performance Optimization
description: >
  Systematic workflow for diagnosing and reducing SQL query count on any
  Flask + SQLAlchemy page in the vpemaster project. Trigger this skill
  when the user asks to "speed up", "optimize", "reduce queries", or
  "improve performance" of a page/route.
---

# SQL Performance Optimization — Flask + SQLAlchemy

## Overview

This skill guides you through a **four-phase** process for reducing
database round-trips and latency on a page served by Flask/SQLAlchemy:

1. **Diagnose** — instrument the route, count queries, trace origins.
2. **Classify** — group queries into actionable categories.
3. **Optimize** — apply proven patterns (see checklist below).
4. **Verify** — re-count queries, run concurrency tests, confirm UI.

> [!IMPORTANT]
> Always read [docs/PERFORMANCE_WALKTHROUGH.md](file:///Users/wmu/workspace/toastmasters/vpemaster/docs/PERFORMANCE_WALKTHROUGH.md)
> first. It documents past optimizations and benchmarks for the voting
> and agenda pages — avoid re-doing work or breaking existing fixes.

---

## Phase 1 — Diagnose

### 1.1 Create a query-tracing diagnostic script

Use `scripts/` or a scratch file. The script should:

```python
# Pattern: SQLAlchemy before_cursor_execute listener with stack tracing
from sqlalchemy import event
import traceback, os

query_traced = []

@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    stack = traceback.extract_stack()
    app_frame = None
    for frame in reversed(stack):
        if 'vpemaster/app' in frame.filename:
            app_frame = frame
            break
    query_traced.append({
        'statement': statement,
        'file': os.path.relpath(app_frame.filename, PROJECT_ROOT) if app_frame else 'external',
        'line': app_frame.lineno if app_frame else 0,
        'func': app_frame.name if app_frame else 'unknown',
        'code': app_frame.line if app_frame else ''
    })
```

### 1.2 Run the diagnostic

1. Do a **warm-up request** first (fills caches, loads modules).
2. Clear `query_traced`, then issue the **target request**.
3. Group results by `(file, line, func)` and sort by first-appearance
   index to see the execution order.

### 1.3 Record the baseline

Document the **total query count** and a table like:

| Query Origin / Code Section | Count | Notes |
|:---|:---:|:---|
| Context processors (`app/__init__.py`) | 4 | Navigation, session |
| Main route body | N | ... |
| Helper function X | N | ... |
| **Total** | **N** | |

---

## Phase 2 — Classify

Put every query into one of these buckets:

| Category | Description | Action |
|:---|:---|:---|
| **N+1 loops** | Same query executed inside a `for` loop | Batch or eager-load |
| **Unused data** | Result assigned but never read by template/caller | Remove entirely |
| **Redundant re-fetch** | Same rows loaded again in a helper | Pass data as parameter |
| **Heavy umbrella helper** | Utility function loads 8+ tables, caller uses 2 | Create lightweight alternative |
| **Unchanging data** | Club defaults, role lists, etc. | Cache (request-level or global) |
| **Required** | Legitimately needed, no way to avoid | Leave alone |

---

## Phase 3 — Optimize

Apply these patterns in priority order (highest impact first):

### 3.1 Remove unused queries

If a query result is never referenced in the template or downstream
code, **delete it**. Check all partial templates / modals loaded by the
page before removing — use `grep` to search for variable names across
all `.html` files in `app/templates/`.

```bash
# Verify a variable is unused before removing its query
grep -rn "variable_name" app/templates/
```

### 3.2 Replace heavy helpers with lightweight alternatives

When a utility (e.g., `get_dropdown_metadata()`) queries many tables but
the caller only needs a subset, create a scoped helper:

```python
# Before — loads contacts, roles, pathways, projects, tickets...
metadata = get_dropdown_metadata()

# After — loads only the 2 tables the agenda page actually uses
projects_data = get_projects_dropdown_data(club_id, user)
```

Reference: [get_projects_dropdown_data](file:///Users/wmu/workspace/toastmasters/vpemaster/app/utils.py#L164-L199)

### 3.3 Pass pre-fetched data to helpers (eliminate re-queries)

When a helper re-queries data that the caller already has:

```python
# Before — helper fetches configs and winners again
awards = get_meeting_awards(meeting)

# After — pass pre-fetched data
configs = selected_meeting.award_configs  # already eager-loaded
winners = selected_meeting.award_winners  # already in memory
awards = get_meeting_awards(meeting, configs=configs, winners=winners)
```

### 3.4 Eager-load relations with `joinedload` / `selectinload`

Use SQLAlchemy eager-loading options on the **primary query** to avoid
lazy-load N+1 hits:

```python
from sqlalchemy.orm import joinedload, selectinload

selected_meeting = Meeting.query.options(
    joinedload(Meeting.club),                    # 1:1 or M:1
    selectinload(Meeting.award_configs)           # 1:N
        .joinedload(MeetingAwardConfig.role_associations),  # nested
).populate_existing().get(meeting_id)
```

**Rules of thumb:**
- `joinedload` for to-one or small to-many (emits a JOIN).
- `selectinload` for large to-many (emits a second IN query).
- Chain `.joinedload(...)` off `selectinload` for nested relations.

Reference: [voting_routes.py#L647-L650](file:///Users/wmu/workspace/toastmasters/vpemaster/app/voting_routes.py#L647-L650)

### 3.5 Request-level caching (Flask `request` object)

For data loaded by **multiple helpers** within the same request, cache
on `flask.request`:

```python
from flask import request, has_request_context

def get_meeting_omr_records(meeting_id):
    if has_request_context():
        cache = getattr(request, '_meeting_omr_records_cache', None)
        if cache is None:
            cache = request._meeting_omr_records_cache = {}
        if meeting_id in cache:
            return cache[meeting_id]

    records = db.session.query(...).filter(...).all()

    if has_request_context():
        request._meeting_omr_records_cache[meeting_id] = records
    return records
```

Reference: [voting_routes.py#L83-L103](file:///Users/wmu/workspace/toastmasters/vpemaster/app/voting_routes.py#L83-L103)

### 3.6 Global in-memory caching (module-level dict)

For **rarely-changing** lookup data (club default awards, role
definitions), use a module-level dict with a TTL or cache key:

```python
_CLUB_DEFAULTS_CACHE = {}

# Inside the route:
cache_key = f"{club_id}"
if cache_key in _CLUB_DEFAULTS_CACHE:
    club_defaults = _CLUB_DEFAULTS_CACHE[cache_key]
else:
    club_defaults = Award.query.filter_by(...).all()
    _CLUB_DEFAULTS_CACHE[cache_key] = club_defaults
```

Reference: [agenda_routes.py#L22](file:///Users/wmu/workspace/toastmasters/vpemaster/app/agenda_routes.py#L22)

> [!WARNING]
> Module-level caches persist across requests in production (gunicorn
> workers). Only cache truly static / rarely-mutated data. Add a TTL or
> invalidation hook if the data can change during normal operation.

### 3.7 Batch queries (replace loops)

Replace per-item queries inside loops with a single batch query:

```python
# Before — N queries inside a loop
for config in configs:
    candidates = OwnerMeetingRoles.query.filter_by(
        role_id=config.role_id
    ).all()

# After — 1 query, then filter in memory
all_omr = get_meeting_omr_records(meeting_id)  # cached
for config in configs:
    candidates = [r for r in all_omr if r.role_id == config.role_id]
```

### 3.8 Consolidate split queries

If two queries fetch the same table with different filters, merge them
and split in memory:

```python
# Before — 2 queries
active = Meeting.query.filter_by(status='active').limit(10).all()
past = Meeting.query.filter_by(status='past').limit(10).all()

# After — 1 query
all_meetings = Meeting.query.filter(
    Meeting.status.in_(['active', 'past'])
).order_by(Meeting.Meeting_Date.desc()).all()
active = [m for m in all_meetings if m.status == 'active'][:10]
past = [m for m in all_meetings if m.status == 'past'][:10]
```

---

## Phase 4 — Verify

### 4.1 Re-count queries

Re-run the diagnostic script from Phase 1. Document the new count in
the same table format. Target: **≤ 50% of original count** or a
concrete number agreed with the user.

### 4.2 Verify UI correctness

- Load the page in a browser and confirm all sections render correctly.
- Check **partial modals** (edit forms, detail popups) — they often rely
  on variables you may have removed.
- Run any existing unit/integration tests:

```bash
python -m pytest tests/ -k "test_<page_name>"
```

### 4.3 Concurrency stress test

Use the Python concurrency test script pattern:

```python
from concurrent.futures import ThreadPoolExecutor
import requests, time

URL = "https://your-server/page?params"
CONCURRENCY = 30
TOTAL_REQUESTS = 100

session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=CONCURRENCY,
    pool_maxsize=CONCURRENCY
)
session.mount("https://", adapter)

# ... login, set cookies ...

def make_request(_):
    start = time.time()
    resp = session.get(URL)
    return time.time() - start, resp.status_code

with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
    results = list(pool.map(make_request, range(TOTAL_REQUESTS)))

# Report: RPS, p50, p95, avg latency, failure rate
```

> [!TIP]
> Avoid ApacheBench (`ab`) on macOS — it's unreliable for high
> concurrency due to socket/TLS queuing issues. The Python
> `ThreadPoolExecutor` approach above gives more accurate results.

Reference script: `scripts/test_voting_concurrency.py`

### 4.4 Document results

Update [docs/PERFORMANCE_WALKTHROUGH.md](file:///Users/wmu/workspace/toastmasters/vpemaster/docs/PERFORMANCE_WALKTHROUGH.md) with:
- Before/after query counts.
- Benchmark numbers (latency, RPS).
- Summary of optimizations applied.

---

## Quick Reference — Optimization Checklist

Use this checklist when optimizing any page:

- [ ] Run diagnostic script, record baseline query count
- [ ] Identify and remove unused queries (grep templates first)
- [ ] Replace heavy utility helpers with scoped alternatives
- [ ] Pass pre-fetched data to sub-helpers (don't re-query)
- [ ] Add `joinedload`/`selectinload` to primary queries
- [ ] Add request-level caching for shared cross-helper data
- [ ] Add global caching for static lookup tables
- [ ] Batch per-item loop queries into single queries
- [ ] Consolidate split queries on the same table
- [ ] Re-run diagnostic, verify query reduction
- [ ] Verify all templates and modals still render correctly
- [ ] Run concurrency stress test
- [ ] Update `docs/PERFORMANCE_WALKTHROUGH.md`
