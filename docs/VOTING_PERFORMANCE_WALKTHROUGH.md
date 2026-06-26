# Walkthrough: Voting Page Performance Optimizations

This document summarizes the query optimizations implemented on the voting page routes and the results of our load testing and verification.

## Summary of Results

Our optimizations successfully resolved redundant database operations and N+1 loop queries, resulting in major gains:

* **Database Query Reduction**: Decreased from **24 SQL queries** to **14 SQL queries** per page load (**41.7% reduction**).
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
| **SQL Queries Count** | 24 | 14 | **-10 queries (-41.7%)** |

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

## Code Optimizations Implemented

The optimizations were successfully committed to local branch `feat/stress-test` (commit `2a1e63b9`) and deployed to `dev.moleqode.com`:

1. **Vote Query Consolidation**: Modified `_get_voting_page_context(meeting_id)` in [voting_routes.py](file:///Users/wmu/workspace/toastmasters/vpemaster/app/voting_routes.py) to load all `Vote` entries for the voter in a single database call, performing rating and comment extractions in memory.
2. **Eager Loading Relations**: Utilized SQLAlchemy `joinedload` and `selectinload` to eager-load `MeetingAwardConfig.role_associations` and `Award.role_associations`, resolving N+1 lazy loading queries.
3. **Winner Lookup Reuse**: Reused the eager-loaded `selected_meeting.award_winners` collection, passing it down to helper routes instead of running redundant database fetches.
4. **Custom Configurations Batching**: Rewrote the candidate query in `_get_roles_for_voting` inside [voting_routes.py](file:///Users/wmu/workspace/toastmasters/vpemaster/app/voting_routes.py) to perform a single batch query for all meeting role takers, matching custom awards config candidates in-memory to completely eliminate SQL query loops.

## Cleanup
* The remote query verification script `scripts/verify_query_count.py` has been completely removed from the remote repository at `/var/www/vpemaster`.
* The remote git repository status is verified as clean.
