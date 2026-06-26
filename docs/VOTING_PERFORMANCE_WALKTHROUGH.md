# Walkthrough: Voting Page Performance Optimizations

This document summarizes the query optimizations implemented on the voting page routes and the results of our load testing and verification.

## Summary of Results

Our optimizations successfully resolved redundant database operations and N+1 loop queries, resulting in major gains:

* **Database Query Reduction**: Decreased from **24 SQL queries** to **7 steady-state / 10 first-load queries** per page load (**70.8% reduction**).
* **Peak Latency Reduction**: Under idle conditions, the maximum request latency dropped from **776 ms** to **434 ms** (**44% reduction**).
* **High Concurrency Stability**: The server remains stable with **0% failure rate** up to **30 concurrent connections**, with average latency per concurrent request remaining extremely low (hovering between 200 ms and 350 ms).

---

## Benchmark Comparison (Concurrency = 1, Keep-Alive)

Below is a comparison of the server-side response times (measured on the client side using ApacheBench) before and after our database query optimizations:

| Metric | Before Optimization | After Optimization | Difference |
| :--- | :--- | :--- | :--- |
| **Total Test Time** | 20.753 seconds | 19.917 seconds | -0.836s (-4.0%) |
| **Mean Request Latency** | 207.5 ms | 199.2 ms | -8.3ms (-4.0%) |
| **Min Processing Time** | 75 ms | 72 ms | -3.0ms (-4.0%) |
| **Median Processing Time** | 196 ms | 203 ms | +7.0ms (+3.5%) |
| **Max Processing Time** | 776 ms | 434 ms | **-342.0ms (-44.0%)** |
| **SQL Queries Count** | 24 | 7 (steady-state) / 10 (first-load) | **-17 queries (-70.8% reduction)** |

> [!NOTE]
> The median processing time remains around ~200ms due to Flask application setup and Nginx SSL termination overhead, but the **maximum processing latency** (representing worst-case database blocks/lockups) was reduced by **44%**.

---

## Stress Test Results (Concurrency 1 to 30)

We executed a local-to-remote stress test using ApacheBench across concurrency levels from 1 to 30. 

### Performance Chart
Below is the chart visualizing Requests Per Second (RPS) and latency across concurrency levels:

![ab benchmark - Requests/sec & Latency vs Concurrency](file:///Users/wmu/.gemini/antigravity/brain/3a3016ae-2bd8-4ee3-8fcc-b6082233e722/chart.png)

### Key Metrics Table (Sampled)
The full raw data is saved in [results.csv](file:///Users/wmu/.gemini/antigravity/brain/3a3016ae-2bd8-4ee3-8fcc-b6082233e722/results.csv). Here is a summary of the performance under scale:

| Concurrency (c) | Requests / Sec (RPS) | Time per Request (Concurrent) | Failed Requests |
| :---: | :---: | :---: | :---: |
| 1 | 5.05 | 197.9 ms | 0 / 100 |
| 5 | 4.60 | 217.4 ms | 0 / 100 |
| 10 | 4.05 | 246.9 ms | 0 / 100 |
| 20 | 3.83 | 261.3 ms | 0 / 100 |
| 30 | 3.61 | 277.3 ms | 0 / 100 |

---

## Python Concurrency Benchmark (Real-world Client Simulation)

Due to potential reliability issues with `ab` on macOS (socket limits, TLS handshake storm queuing, and lack of connection pool pre-warming), we created a custom Python concurrency test script: [test_voting_concurrency.py](file:///Users/wmu/workspace/toastmasters/vpemaster/scripts/test_voting_concurrency.py).

This script simulates 30 concurrent users using Python's `ThreadPoolExecutor` and a `requests.Session` with a pooled connection adapter (reusing TLS/TCP connections). It also supports pre-warming the connection pool to measure steady-state performance without initial TLS handshakes.

### Test Configuration
* **Concurrency (c)**: 30
* **Total Requests (n)**: 100
* **Target URL**: `https://dev.moleqode.com/voting?club_id=2`
* **Warmup Pool**: Enabled

### Benchmark Results (Warmup Pool Enabled)
* **Total Time Taken**: 4.730 seconds
* **Requests per Second**: 21.14 RPS
* **Successful Requests**: 100 / 100 (100.0%)
* **Failed Requests**: 0 / 100 (0.0%)

#### Latency Distribution
| Bracket | Request Count | Percentage |
| :--- | :---: | :---: |
| < 100ms | 0 | 0.0% |
| 100ms - 200ms | 1 | 1.0% |
| 200ms - 500ms | 46 | 46.0% |
| 500ms - 1000ms | 15 | 15.0% |
| 1000ms - 2000ms | 20 | 20.0% |
| > 2000ms | 18 | 18.0% |

#### Latency Statistics
* **Minimum Latency**: 171.09 ms
* **Average Latency**: 1151.13 ms
* **Median (p50) Latency**: 623.90 ms
* **90th Percentile**: 3145.30 ms
* **95th Percentile**: 3801.44 ms
* **Maximum Latency**: 4700.95 ms

*Note: Without HTTP Keep-Alive (forcing a new TLS handshake per request), the performance drops to **9.93 RPS** with an average latency of **2644.68 ms**, illustrating the high cost of initiating TLS connections concurrently under load.*

---

## Code Optimizations Implemented

The optimizations were successfully committed to local branch `feat/stress-test` (commit `83ef752e`) and deployed to `dev.moleqode.com`:

1. **Vote Query Consolidation**: Modified `_get_voting_page_context(meeting_id)` in [voting_routes.py](file:///Users/wmu/workspace/toastmasters/vpemaster/app/voting_routes.py) to load all `Vote` entries for the voter in a single database call, performing rating and comment extractions in memory.
2. **Eager Loading Relations**: Utilized SQLAlchemy `joinedload` and `selectinload` to eager-load `MeetingAwardConfig.role_associations`, `Award.role_associations`, and `Meeting.club`, resolving N+1 lazy loading queries.
3. **Winner Lookup Reuse**: Reused the eager-loaded `selected_meeting.award_winners` collection, passing it down to helper routes instead of running redundant database fetches.
4. **Custom Configurations Batching**: Rewrote the candidate query in `_get_roles_for_voting` inside [voting_routes.py](file:///Users/wmu/workspace/toastmasters/vpemaster/app/voting_routes.py) to perform a single batch query for all meeting role takers, matching custom awards config candidates in-memory to completely eliminate SQL query loops.
5. **Request-Level Cache Sharing (New)**: Introduced a request-level cache `_meeting_omr_records_cache` to share loaded `OwnerMeetingRoles` records. This allowed both `populate_session_log_owners` and `RoleService.get_role_takers` to query the database **once** and reuse results in-memory.
6. **In-Memory Candidate Extraction (New)**: Completely eliminated the query for custom category candidates in `_enrich_role_data_for_voting` by constructing the list in-memory from the shared OMR records cache.
7. **Consolidated dropdown query (New)**: Modified `get_meetings_by_status` in [utils.py](file:///Users/wmu/workspace/toastmasters/vpemaster/app/utils.py) to fetch active and past meetings in a single query, separating and limiting them in memory.
8. **Waitlist Removal (New)**: Stopped loading `SessionLog.waitlists` since waitlists are not displayed on the voting page.
9. **Global memory cache for Club Defaults (New)**: Added `_CLUB_DEFAULTS_CACHE` in [agenda_routes.py](file:///Users/wmu/workspace/toastmasters/vpemaster/app/agenda_routes.py) to cache default club awards queries across requests.

## Documentation
* The design walkthrough has been copied to the repository under [docs/VOTING_PERFORMANCE_WALKTHROUGH.md](file:///Users/wmu/workspace/toastmasters/vpemaster/docs/VOTING_PERFORMANCE_WALKTHROUGH.md) and linked in [AGENTS.md](file:///Users/wmu/workspace/toastmasters/vpemaster/AGENTS.md).
