#!/usr/bin/env python3
"""
Concurrency Stress Test — Template
=====================================
Simulates N concurrent users hitting a page to measure real-world
latency and throughput. Uses requests.Session with connection pooling
for realistic behavior.

Usage:
    python scripts/test_page_concurrency.py \
        --url "https://your-server.com/page" \
        --concurrency 30 \
        --total 100
"""

import argparse
import time
import statistics
import requests
from concurrent.futures import ThreadPoolExecutor


def run_concurrency_test(base_url, target_path, concurrency, total_requests,
                         username=None, password=None, login_path="/auth/login"):
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=concurrency,
        pool_maxsize=concurrency
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # Login if credentials provided
    if username and password:
        login_url = f"{base_url}{login_path}"
        print(f"Logging in at {login_url}...")
        resp = session.post(login_url, data={
            "email": username,
            "password": password
        }, allow_redirects=True)
        if resp.status_code != 200:
            print(f"Login failed with status {resp.status_code}")
            return

    target_url = f"{base_url}{target_path}"
    print(f"\nTarget: {target_url}")
    print(f"Concurrency: {concurrency}")
    print(f"Total requests: {total_requests}")
    print("-" * 60)

    latencies = []
    failures = 0

    def make_request(_):
        nonlocal failures
        start = time.time()
        try:
            resp = session.get(target_url, timeout=30)
            elapsed = time.time() - start
            if resp.status_code != 200:
                failures += 1
            return elapsed, resp.status_code
        except Exception as e:
            failures += 1
            return time.time() - start, str(e)

    start_time = time.time()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(make_request, range(total_requests)))
    total_time = time.time() - start_time

    latencies = [r[0] for r in results]
    latencies.sort()

    # Calculate percentiles
    p50 = latencies[len(latencies) // 2]
    p95_idx = int(len(latencies) * 0.95)
    p95 = latencies[p95_idx] if p95_idx < len(latencies) else latencies[-1]

    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"Total Time:        {total_time:.3f} seconds")
    print(f"Requests/Second:   {total_requests / total_time:.2f} RPS")
    print(f"Successful:        {total_requests - failures} / {total_requests} "
          f"({(total_requests - failures) / total_requests * 100:.1f}%)")
    print(f"Failed:            {failures} / {total_requests} "
          f"({failures / total_requests * 100:.1f}%)")
    print(f"Min Latency:       {min(latencies) * 1000:.2f} ms")
    print(f"Median (p50):      {p50 * 1000:.2f} ms")
    print(f"Average:           {statistics.mean(latencies) * 1000:.2f} ms")
    print(f"95th Percentile:   {p95 * 1000:.2f} ms")
    print(f"Max Latency:       {max(latencies) * 1000:.2f} ms")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Concurrency stress test for a web page")
    parser.add_argument("--url", required=True, help="Base URL (e.g. https://example.com)")
    parser.add_argument("--path", required=True, help="Target path (e.g. /voting?meeting_id=1)")
    parser.add_argument("--concurrency", type=int, default=30, help="Concurrent connections")
    parser.add_argument("--total", type=int, default=100, help="Total requests to send")
    parser.add_argument("--username", help="Login username/email")
    parser.add_argument("--password", help="Login password")
    parser.add_argument("--login-path", default="/auth/login", help="Login endpoint path")
    args = parser.parse_args()

    run_concurrency_test(
        base_url=args.url,
        target_path=args.path,
        concurrency=args.concurrency,
        total_requests=args.total,
        username=args.username,
        password=args.password,
        login_path=args.login_path
    )
