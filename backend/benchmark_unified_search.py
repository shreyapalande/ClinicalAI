"""
Benchmarks POST /api/search/unified across all three routing tiers.
Sends 15 queries (5 structured, 5 semantic, 5 lookup), records the route
each was assigned and the response time, then outputs a routing distribution
table with per-tier latency stats.

Usage:
    .\\venv\\Scripts\\python backend/benchmark_unified_search.py

Against a deployed instance:
    .\\venv\\Scripts\\python backend/benchmark_unified_search.py --server=https://your-app.onrender.com
"""

import math
import sys
import time
from collections import defaultdict

import requests

SERVER = next(
    (a.split("=", 1)[1] for a in sys.argv if a.startswith("--server=")),
    "http://localhost:8000",
)
URL = f"{SERVER}/api/search/unified"

# ── 15 test queries, 5 per tier ───────────────────────────────────────────────
# expected_route is what the classifier should assign; we verify against the
# actual `route` field returned by the server.

QUERIES = [
    # ── Structured filter (5) ────────────────────────────────────────────────
    ("structured", "patients over 60",                     "age filter"),
    ("structured", "patients on Metformin",                "drug filter"),
    ("structured", "patients allergic to penicillin",      "allergy filter"),
    ("structured", "patients under 40",                    "age filter"),
    ("structured", "patients prescribed Atorvastatin",     "drug filter"),

    # ── Semantic concept (5) ─────────────────────────────────────────────────
    ("semantic",   "chest pain and cardiac symptoms",      "cardiovascular"),
    ("semantic",   "poorly controlled blood sugar",        "endocrine"),
    ("semantic",   "breathing difficulties in children",   "paediatric respiratory"),
    ("semantic",   "thyroid hormone deficiency",           "endocrine"),
    ("semantic",   "anxiety and sleep disturbance",        "mental health"),

    # ── Name / ID lookup (5) ─────────────────────────────────────────────────
    ("lookup",     "patient ID 1",                         "ID lookup"),
    ("lookup",     "patient #2",                           "ID lookup"),
    ("lookup",     "find patient 3",                       "ID lookup"),
    ("lookup",     "Sarah Nguyen",                         "name lookup"),
    ("lookup",     "Jake Mercer",                          "name lookup"),
]


def _stats(values: list[float]) -> dict:
    n = len(values)
    if n == 0:
        return {"n": 0, "avg": None, "min": None, "max": None, "std": None}
    avg = sum(values) / n
    mn = min(values)
    mx = max(values)
    std = math.sqrt(sum((x - avg) ** 2 for x in values) / n)
    return {"n": n, "avg": avg, "min": mn, "max": mx, "std": std}


def run():
    print(f"\nTarget : {URL}")
    print(f"Queries: {len(QUERIES)}\n")

    # column widths
    QW, EW, AW, NW = 40, 12, 12, 8

    header = (
        f"{'Query':<{QW}}{'Expected':>{EW}}{'Assigned':>{AW}}"
        f"{'Correct?':>{NW}}{'Results':>9}{'Time':>9}"
    )
    print(header)
    print("─" * len(header))

    rows = []

    for expected_route, query, label in QUERIES:
        short_q = (query if len(query) <= QW - 1 else query[:QW - 4] + "…")
        try:
            t0 = time.perf_counter()
            r = requests.post(URL, json={"q": query}, timeout=60)
            elapsed = time.perf_counter() - t0

            if r.status_code != 200:
                print(
                    f"{short_q:<{QW}}{expected_route:>{EW}}{'ERR ' + str(r.status_code):>{AW}}"
                    f"{'—':>{NW}}{'—':>9}{elapsed:>8.2f}s"
                )
                rows.append({
                    "expected": expected_route,
                    "assigned": None,
                    "correct": False,
                    "latency": elapsed,
                    "count": 0,
                    "label": label,
                })
                continue

            body = r.json()
            assigned = body.get("route", "?")
            count = body.get("count", len(body.get("results", [])))
            correct = assigned == expected_route
            tick = "✓" if correct else "✗"

            print(
                f"{short_q:<{QW}}{expected_route:>{EW}}{assigned:>{AW}}"
                f"{tick:>{NW}}{count:>9}{elapsed:>8.2f}s"
            )
            rows.append({
                "expected": expected_route,
                "assigned": assigned,
                "correct": correct,
                "latency": elapsed,
                "count": count,
                "label": label,
            })

        except requests.exceptions.Timeout:
            print(f"{short_q:<{QW}}{expected_route:>{EW}}{'TIMEOUT':>{AW}}{'—':>{NW}}{'—':>9}{'—':>9}")
            rows.append({"expected": expected_route, "assigned": None, "correct": False, "latency": None, "count": 0, "label": label})
        except requests.exceptions.ConnectionError:
            print(f"{short_q:<{QW}}{expected_route:>{EW}}{'NO CONN':>{AW}}{'—':>{NW}}{'—':>9}{'—':>9}")
            rows.append({"expected": expected_route, "assigned": None, "correct": False, "latency": None, "count": 0, "label": label})

    if not rows:
        print("\nNo results.")
        return

    # ── Routing distribution table ────────────────────────────────────────────
    tiers = ["structured", "semantic", "lookup"]

    by_expected: dict[str, list] = defaultdict(list)
    by_assigned: dict[str, list] = defaultdict(list)
    for row in rows:
        by_expected[row["expected"]].append(row)
        if row["assigned"]:
            by_assigned[row["assigned"]].append(row)

    print("\n\n  ROUTING DISTRIBUTION\n")
    dw = 14
    print(f"  {'Tier':<12} {'Expected':>{dw}} {'Assigned':>{dw}} {'Correct':>{dw}} {'Avg ms':>{dw}} {'Min ms':>{dw}} {'Max ms':>{dw}}")
    print("  " + "─" * (12 + dw * 6 + 6))

    for tier in tiers:
        expected_rows = by_expected[tier]
        assigned_rows = by_assigned.get(tier, [])
        correct = sum(1 for r in expected_rows if r["correct"])
        latencies_ms = [r["latency"] * 1000 for r in expected_rows if r["latency"] is not None]
        s = _stats(latencies_ms)

        avg_s = f"{s['avg']:.0f}" if s["avg"] is not None else "—"
        min_s = f"{s['min']:.0f}" if s["min"] is not None else "—"
        max_s = f"{s['max']:.0f}" if s["max"] is not None else "—"

        print(
            f"  {tier:<12} {len(expected_rows):>{dw}} {len(assigned_rows):>{dw}}"
            f" {correct}/{len(expected_rows):>{dw-2}} {avg_s:>{dw}} {min_s:>{dw}} {max_s:>{dw}}"
        )

    # ── Routing accuracy ──────────────────────────────────────────────────────
    valid = [r for r in rows if r["assigned"] is not None]
    correct_total = sum(1 for r in valid if r["correct"])
    print(f"\n  Routing accuracy : {correct_total}/{len(valid)} queries correctly classified")

    # Misrouted queries
    misrouted = [r for r in valid if not r["correct"]]
    if misrouted:
        print("\n  Misrouted queries:")
        for r in misrouted:
            # find the original query text
            q_text = next(q for (e, q, _) in QUERIES if e == r["expected"] and r["assigned"] != e)
            print(f"    [{r['expected']} → {r['assigned']}]  {q_text}")

    # ── Overall latency ───────────────────────────────────────────────────────
    all_latencies = [r["latency"] * 1000 for r in rows if r["latency"] is not None]
    s = _stats(all_latencies)
    if s["avg"] is not None:
        print(f"\n  Overall latency  : avg {s['avg']:.0f}ms  min {s['min']:.0f}ms  max {s['max']:.0f}ms  σ {s['std']:.0f}ms")
    print()


if __name__ == "__main__":
    run()
