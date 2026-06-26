#!/usr/bin/env python3
"""
Query Diagnostic Script — Template
====================================
Instruments a Flask route to trace every SQL query back to its source
file, line number, and function. Use this to produce a baseline query
count and identify optimization targets.

Usage:
    python scripts/diagnose_page_queries.py \
        --route "/agenda" \
        --params "club_id=1&meeting_id=42"
"""

import sys
import os
import argparse
import traceback

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app import create_app, db
from app.models import Meeting, User
from sqlalchemy import event


def run_diagnostic(route, params, warmup=True):
    app = create_app()
    query_traced = []

    with app.app_context():
        @event.listens_for(db.engine, "before_cursor_execute")
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

        # Set up authenticated test client
        user = User.query.first()
        meeting = Meeting.query.filter_by(status='running').first()
        if not meeting:
            meeting = Meeting.query.filter_by(status='finished').first()
        if not meeting:
            meeting = Meeting.query.first()

        if not meeting:
            print("No meetings found.")
            sys.exit(1)

        club_id = meeting.club_id
        client = app.test_client()

        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['current_club_id'] = club_id

        url = f"{route}?{params}" if params else route

        # Warm-up request (fills caches, compiles templates)
        if warmup:
            print(f"Warm-up request: GET {url}")
            client.get(url)

        # Reset and run target request
        query_traced.clear()
        print(f"Target request:  GET {url}")
        resp = client.get(url)
        print(f"Response status: {resp.status_code}")

        # Report
        print(f"\n{'='*80}")
        print(f"TOTAL SQL QUERIES: {len(query_traced)}")
        print(f"{'='*80}")
        print("SQL QUERY ORIGIN TRACE")
        print(f"{'='*80}")

        # Group by origin
        origins = {}
        for idx, q in enumerate(query_traced, 1):
            key = (q['file'], q['line'], q['func'], q['code'])
            origins.setdefault(key, []).append((idx, q['statement']))

        sorted_origins = sorted(origins.items(), key=lambda item: item[1][0][0])

        for (file, line, func, code), instances in sorted_origins:
            print(f"\n📍 File: {file}:{line} in `{func}()`")
            print(f"   Code: {code}")
            print(f"   Executed {len(instances)} time(s) at query index(es): "
                  f"{[inst[0] for inst in instances]}")
            clean_stmt = " ".join(instances[0][1].split())
            print(f"   SQL: {clean_stmt[:180]}...")

        return len(query_traced)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Diagnose SQL queries for a Flask route")
    parser.add_argument("--route", default="/agenda", help="Route path (e.g. /agenda)")
    parser.add_argument("--params", default="", help="Query string params (e.g. club_id=1&meeting_id=42)")
    parser.add_argument("--no-warmup", action="store_true", help="Skip warm-up request")
    args = parser.parse_args()
    run_diagnostic(args.route, args.params, warmup=not args.no_warmup)
