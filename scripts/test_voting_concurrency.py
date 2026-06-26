#!/usr/bin/env python3
import argparse
import sys
import time
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

# Suppress insecure request warnings if verify=False is used
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def send_request(session, url, req_id, timeout, keep_alive):
    start = time.perf_counter()
    try:
        if keep_alive:
            # Reuses connections from the session pool
            response = session.get(url, timeout=timeout, verify=False)
        else:
            # Creates a new connection per request by bypassing session pooling
            with requests.Session() as s:
                response = s.get(url, timeout=timeout, verify=False)
        
        latency = time.perf_counter() - start
        return {
            "id": req_id,
            "status_code": response.status_code,
            "latency_ms": latency * 1000,
            "length": len(response.content),
            "success": response.status_code == 200
        }
    except Exception as e:
        latency = time.perf_counter() - start
        return {
            "id": req_id,
            "status_code": None,
            "latency_ms": latency * 1000,
            "length": 0,
            "success": False,
            "error": str(type(e).__name__) + ": " + str(e)
        }

def run_benchmark(url, concurrency, total_requests, timeout, keep_alive, warmup_pool=False):
    print("=" * 60)
    print(f"STARTING CONCURRENCY BENCHMARK")
    print("=" * 60)
    print(f"Target URL:        {url}")
    print(f"Concurrency:       {concurrency}")
    print(f"Total Requests:    {total_requests}")
    print(f"Timeout:           {timeout}s")
    print(f"HTTP Keep-Alive:   {'Enabled' if keep_alive else 'Disabled'}")
    print(f"Warmup Pool:       {'Enabled' if (keep_alive and warmup_pool) else 'Disabled'}")
    print("=" * 60)

    # Initialize session
    session = requests.Session()
    if keep_alive:
        adapter = requests.adapters.HTTPAdapter(pool_connections=concurrency, pool_maxsize=concurrency)
        session.mount('https://', adapter)
        session.mount('http://', adapter)

    if keep_alive and warmup_pool:
        print(f"Pre-warming connection pool with {concurrency} concurrent requests...")
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            warmup_futures = [executor.submit(send_request, session, url, -100-i, timeout, keep_alive) for i in range(concurrency)]
            for future in as_completed(warmup_futures):
                future.result()
        print("Warmup pool connections established.")
    else:
        print("Sending a single warmup request to establish connection...")
        warmup = send_request(session, url, -1, timeout, keep_alive)
        if warmup["success"]:
            print(f"Warmup successful! Latency: {warmup['latency_ms']:.2f} ms, Response Length: {warmup['length']} bytes")
        else:
            print(f"Warmup failed! Status: {warmup['status_code']}, Error: {warmup.get('error')}")
            print("Continuing with benchmark anyway...")
    
    print("\nExecuting stress test...")
    start_time = time.perf_counter()
    results = []
    
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(send_request, session, url, i, timeout, keep_alive) for i in range(total_requests)]
        for future in as_completed(futures):
            results.append(future.result())
            
    total_time = time.perf_counter() - start_time
    
    # Calculate statistics
    success_count = sum(1 for r in results if r["success"])
    failures = [r for r in results if not r["success"]]
    latencies = [r["latency_ms"] for r in results]
    
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    latencies.sort()
    
    p50 = latencies[int(len(latencies) * 0.5)] if latencies else 0
    p90 = latencies[int(len(latencies) * 0.9)] if latencies else 0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0
    
    # Latency distribution
    brackets = {
        "< 100ms": 0,
        "100ms - 200ms": 0,
        "200ms - 500ms": 0,
        "500ms - 1000ms": 0,
        "1000ms - 2000ms": 0,
        "> 2000ms": 0
    }
    for lat in latencies:
        if lat < 100:
            brackets["< 100ms"] += 1
        elif lat < 200:
            brackets["100ms - 200ms"] += 1
        elif lat < 500:
            brackets["200ms - 500ms"] += 1
        elif lat < 1000:
            brackets["500ms - 1000ms"] += 1
        elif lat < 2000:
            brackets["1000ms - 2000ms"] += 1
        else:
            brackets["> 2000ms"] += 1

    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    print(f"Total Time Taken:     {total_time:.3f} seconds")
    print(f"Requests per Second:  {total_requests / total_time:.2f} RPS")
    print(f"Successful Requests:  {success_count} / {total_requests} ({success_count/total_requests*100:.1f}%)")
    print(f"Failed Requests:      {len(failures)} / {total_requests} ({len(failures)/total_requests*100:.1f}%)")
    
    if failures:
        print("\nFailure Breakdown:")
        err_counts = {}
        for f in failures:
            err_msg = f.get('error') or f"HTTP Status {f['status_code']}"
            err_counts[err_msg] = err_counts.get(err_msg, 0) + 1
        for err, count in err_counts.items():
            print(f"  - {err}: {count} occurrence(s)")
            
    print("\nLatency Distribution:")
    for bracket, count in brackets.items():
        percentage = (count / total_requests) * 100 if total_requests else 0
        bar = "#" * int(percentage / 5)
        print(f"  {bracket:<16}: {count:>3} ({percentage:>5.1f}%)  {bar}")

    print("\nClient-side Latency Stats:")
    print(f"  Minimum:            {latencies[0]:.2f} ms" if latencies else "  Minimum: N/A")
    print(f"  Average:            {avg_latency:.2f} ms")
    print(f"  Median (p50):       {p50:.2f} ms")
    print(f"  90th percentile:    {p90:.2f} ms")
    print(f"  95th percentile:    {p95:.2f} ms")
    print(f"  99th percentile:    {p99:.2f} ms")
    print(f"  Maximum:            {latencies[-1]:.2f} ms" if latencies else "  Maximum: N/A")
    print("=" * 60)

    # Return summary stats for automated usage if needed
    return {
        "total_time": total_time,
        "rps": total_requests / total_time,
        "success_rate": success_count / total_requests,
        "avg_latency": avg_latency,
        "p50": p50,
        "p95": p95,
        "failures": len(failures)
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test performance at high concurrency levels.")
    parser.add_argument("--url", default="https://dev.moleqode.com/voting?club_id=2", help="URL to benchmark")
    parser.add_argument("-c", "--concurrency", type=int, default=30, help="Concurrency level")
    parser.add_argument("-n", "--requests", type=int, default=100, help="Total number of requests")
    parser.add_argument("--timeout", type=float, default=10.0, help="Timeout per request in seconds")
    parser.add_argument("--no-keepalive", dest="keep_alive", action="store_false", help="Disable HTTP Keep-Alive")
    parser.add_argument("--keepalive", dest="keep_alive", action="store_true", help="Enable HTTP Keep-Alive (default)")
    parser.add_argument("--warmup-pool", action="store_true", help="Pre-establish all concurrent connections before starting the test")
    parser.set_defaults(keep_alive=True)

    args = parser.parse_args()
    run_benchmark(
        url=args.url,
        concurrency=args.concurrency,
        total_requests=args.requests,
        timeout=args.timeout,
        keep_alive=args.keep_alive,
        warmup_pool=args.warmup_pool
    )
