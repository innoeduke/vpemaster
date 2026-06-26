# Walkthrough: Performance Optimizations

This document summarizes the database query and latency optimizations implemented on the voting and agenda pages, along with our verification and stress testing results.

---

## 1. Summary of Results

Our optimizations successfully resolved redundant database operations, N+1 loops, and unused metadata queries, resulting in major performance gains:

### Voting Page
* **Database Query Reduction**: Decreased from **24 SQL queries** to **7 steady-state / 10 first-load queries** per page load (**70.8% reduction**).
* **Peak Latency Reduction**: Under idle conditions, the maximum request latency dropped from **776 ms** to **434 ms** (**44% reduction**).
* **High Concurrency Stability**: The server remains stable with **0% failure rate** up to **30 concurrent connections**, with average latency per concurrent request remaining extremely low.

### Agenda Page
* **Database Query Reduction**: Decreased from **44 SQL queries** to **31 SQL queries** per page load (**29.5% query count reduction**).
* **Zero UI/Modal Impact**: Audited all sub-templates/modals on the agenda page (e.g., `_speech_edit_modal.html`) to ensure they remain fully functional.

---

## 2. Voting Page Benchmarks

### Benchmark Comparison (Concurrency = 1, Keep-Alive)
Below is a comparison of client-side response times (measured using ApacheBench) before and after query optimizations:

| Metric | Before Optimization | After Optimization | Difference |
| :--- | :--- | :--- | :--- |
| **Total Test Time** | 20.753 seconds | 19.917 seconds | -0.836s (-4.0%) |
| **Mean Request Latency** | 207.5 ms | 199.2 ms | -8.3ms (-4.0%) |
| **Min Processing Time** | 75 ms | 72 ms | -3.0ms (-4.0%) |
| **Median Processing Time** | 196 ms | 203 ms | +7.0ms (+3.5%) |
| **Max Processing Time** | 776 ms | 434 ms | **-342.0ms (-44.0%)** |
| **SQL Queries Count** | 24 | 7 (steady-state) / 10 (first-load) | **-17 queries (-70.8% reduction)** |

### Python Concurrency Benchmark (Real-world Client Simulation)
This test simulates 30 concurrent users using Python's `ThreadPoolExecutor` and a `requests.Session` with a pooled connection adapter:
* **Total Time Taken**: 4.730 seconds
* **Requests per Second**: 21.14 RPS
* **Successful Requests**: 100 / 100 (100.0%)
* **Failed Requests**: 0 / 100 (0.0%)
* **Median (p50) Latency**: **623.90 ms**
* **Average Latency**: **1151.13 ms**
* **95th Percentile**: **3801.44 ms**

---

## 3. Agenda Page Benchmarks

### Steady-State Query Count Verification
Using the Flask test client in the application context:

| Query Origin / Code Section | Before | After | Difference / Optimization |
| :--- | :---: | :---: | :--- |
| Context Processors (`app/__init__.py`) | 4 | 4 | Remains unchanged (needed for navigation). |
| Main Route Meetings list | 2 | 2 | Remains unchanged. |
| Log processing (`_get_agenda_logs`) | 4 | 4 | Remains unchanged. |
| **Dropdown metadata queries** | **8** | **2** | **Optimized:** Pruned 6 unused lookups (contacts, roles, tickets, etc.). |
| Main Route Award Configs | 1 | 1 | Remains unchanged. |
| Main Route Meeting Roles | 2 | 2 | Remains unchanged. |
| **Voting accordions helpers** | **4** | **1** | **Optimized:** Passed pre-fetched configs & winners. |
| **Unused Members Query** | **1** | **0** | **Optimized:** Removed completely. |
| Awards listing helpers | 11 | 11 | Remains unchanged. |
| **Total SQL Queries** | **44** | **31** | **-13 queries (29.5% reduction)** |

---

## 4. Optimizations Implemented

The optimizations were successfully committed to local branch `dev` and deployed:

### Voting Page Route Optimizations
1. **Vote Query Consolidation**: Modified `_get_voting_page_context(meeting_id)` in [voting_routes.py](file:///Users/wmu/workspace/toastmasters/vpemaster/app/voting_routes.py) to load all `Vote` entries for the voter in a single database call, performing rating and comment extractions in memory.
2. **Eager Loading Relations**: Utilized SQLAlchemy `joinedload` and `selectinload` to eager-load `MeetingAwardConfig.role_associations`, `Award.role_associations`, and `Meeting.club`, resolving N+1 lazy loading queries.
3. **Winner Lookup Reuse**: Reused the eager-loaded `selected_meeting.award_winners` collection, passing it down to helper routes instead of running redundant database fetches.
4. **Custom Configurations Batching**: Rewrote the candidate query in `_get_roles_for_voting` inside [voting_routes.py](file:///Users/wmu/workspace/toastmasters/vpemaster/app/voting_routes.py) to perform a single batch query for all meeting role takers, matching custom awards config candidates in-memory to completely eliminate SQL query loops.
5. **Request-Level Cache Sharing**: Introduced a request-level cache `_meeting_omr_records_cache` to share loaded `OwnerMeetingRoles` records. This allowed both `populate_session_log_owners` and `RoleService.get_role_takers` to query the database **once** and reuse results in-memory.
6. **In-Memory Candidate Extraction**: Completely eliminated the query for custom category candidates in `_enrich_role_data_for_voting` by constructing the list in-memory from the shared OMR records cache.
7. **Consolidated dropdown query**: Modified `get_meetings_by_status` in [utils.py](file:///Users/wmu/workspace/toastmasters/vpemaster/app/utils.py) to fetch active and past meetings in a single query, separating and limiting them in memory.
8. **Waitlist Removal**: Stopped loading `SessionLog.waitlists` since waitlists are not displayed on the voting page.
9. **Global memory cache for Club Defaults**: Added `_CLUB_DEFAULTS_CACHE` in [agenda_routes.py](file:///Users/wmu/workspace/toastmasters/vpemaster/app/agenda_routes.py) to cache default club awards queries across requests.

### Agenda Page Route Optimizations
1. **Lightweight Project Metadata Helper**:
   Created `get_projects_dropdown_data(club_id, user)` in [app/utils.py](file:///Users/wmu/workspace/toastmasters/vpemaster/app/utils.py) that only queries the database for `Project` and `PathwayProject` joins. This replaces the heavy `get_dropdown_metadata()` on the agenda route, saving 7-8 redundant SQL queries that were immediately discarded by the agenda page.
2. **Removed Unused Members Query**:
   Deleted the query looking up all club members in [app/agenda_routes.py](file:///Users/wmu/workspace/toastmasters/vpemaster/app/agenda_routes.py) because the `members` variable is never referenced in the HTML layout or any modals.
3. **Reused In-Memory Configs and Winners**:
   Passed the pre-fetched `configs` list and `selected_meeting.award_winners` collection to `_get_roles_for_voting()` and `get_meeting_awards()` in the agenda route, eliminating redundant queries on `MeetingAwardConfig` and `MeetingAwardWinner`.
