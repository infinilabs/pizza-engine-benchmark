#!/usr/bin/env python3
"""Latency comparison: pizza-engine-0.1 vs lucene-10.4-bp.
   Runs all queries.txt queries for TOP_10, measuring wall-clock per query.
   Reports P50, P90, P99, mean, and per-tag breakdowns.
"""

import subprocess
import json
import sys
import time
from os import path
from collections import defaultdict

WARMUP_ROUNDS = 3


class Engine:
    def __init__(self, name):
        self.name = name
        cwd = path.join(path.dirname(path.abspath(__file__)), "engines", name)
        self.process = subprocess.Popen(
            ["make", "--no-print-directory", "serve"],
            cwd=cwd, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def query(self, cmd, q):
        line = f"{cmd}\t{q}\n"
        self.process.stdin.write(line.encode())
        self.process.stdin.flush()
        resp = self.process.stdout.readline().strip().decode()
        return resp

    def timed_query(self, cmd, q):
        line = f"{cmd}\t{q}\n"
        start = time.monotonic()
        self.process.stdin.write(line.encode())
        self.process.stdin.flush()
        resp = self.process.stdout.readline().strip().decode()
        elapsed_us = (time.monotonic() - start) * 1e6
        return resp, elapsed_us

    def close(self):
        try: self.process.stdin.close()
        except: pass
        try: self.process.terminate(); self.process.wait(timeout=5)
        except: pass


def percentile(sorted_list, p):
    if not sorted_list: return 0
    idx = int(len(sorted_list) * p / 100)
    idx = min(idx, len(sorted_list) - 1)
    return sorted_list[idx]


def main():
    queries_file = sys.argv[1] if len(sys.argv) > 1 else "queries.txt"
    with open(queries_file) as f:
        queries = [json.loads(line) for line in f if line.strip()]

    print(f"Loaded {len(queries)} queries from {queries_file}")

    for cmd in ["TOP_10", "TOP_100", "COUNT"]:
        print(f"\n{'='*70}")
        print(f"  COMMAND: {cmd}")
        print(f"{'='*70}")

        pizza = Engine("pizza-engine-0.1")
        lucene = Engine("lucene-10.4-bp")

        # Warmup
        print(f"  Warming up ({WARMUP_ROUNDS} rounds)...", file=sys.stderr)
        for _ in range(WARMUP_ROUNDS):
            for q in queries:
                pizza.query(cmd, q["query"])
                lucene.query(cmd, q["query"])

        # Timed run
        pizza_times = {}
        lucene_times = {}
        tag_pizza = defaultdict(list)
        tag_lucene = defaultdict(list)

        for q in queries:
            qstr = q["query"]
            tags = q.get("tags", [])

            _, pt = pizza.timed_query(cmd, qstr)
            _, lt = lucene.timed_query(cmd, qstr)

            pizza_times[qstr] = pt
            lucene_times[qstr] = lt

            for tag in tags:
                tag_pizza[tag].append(pt)
                tag_lucene[tag].append(lt)

        pizza.close()
        lucene.close()

        # Overall stats
        p_all = sorted(pizza_times.values())
        l_all = sorted(lucene_times.values())

        print(f"\n  {'Metric':<12} {'Pizza (µs)':>12} {'Lucene (µs)':>12} {'Ratio':>8}")
        print(f"  {'-'*12} {'-'*12} {'-'*12} {'-'*8}")
        for label, p_val, l_val in [
            ("Mean", sum(p_all)/len(p_all), sum(l_all)/len(l_all)),
            ("P50", percentile(p_all, 50), percentile(l_all, 50)),
            ("P90", percentile(p_all, 90), percentile(l_all, 90)),
            ("P99", percentile(p_all, 99), percentile(l_all, 99)),
            ("Max", max(p_all), max(l_all)),
        ]:
            ratio = p_val / l_val if l_val > 0 else float('inf')
            marker = "  <-- FASTER" if ratio < 1.0 else ""
            print(f"  {label:<12} {p_val:>12.0f} {l_val:>12.0f} {ratio:>7.2f}x{marker}")

        # Per-tag breakdown
        all_tags = sorted(set(list(tag_pizza.keys()) + list(tag_lucene.keys())))
        # Filter to interesting tags
        interesting = [t for t in all_tags if t in (
            "term", "union", "intersection", "phrase",
            "union:num_tokens_2", "union:num_tokens_3",
            "intersection:num_tokens_2", "intersection:num_tokens_3",
            "phrase:num_tokens_2", "phrase:num_tokens_3", "global",
        )]
        if interesting:
            print(f"\n  Per-tag mean latency:")
            print(f"  {'Tag':<30} {'Pizza (µs)':>12} {'Lucene (µs)':>12} {'Ratio':>8} {'N':>5}")
            print(f"  {'-'*30} {'-'*12} {'-'*12} {'-'*8} {'-'*5}")
            for tag in interesting:
                pt_list = tag_pizza.get(tag, [])
                lt_list = tag_lucene.get(tag, [])
                if not pt_list or not lt_list: continue
                pm = sum(pt_list)/len(pt_list)
                lm = sum(lt_list)/len(lt_list)
                ratio = pm / lm if lm > 0 else float('inf')
                marker = " FASTER" if ratio < 1.0 else ""
                print(f"  {tag:<30} {pm:>12.0f} {lm:>12.0f} {ratio:>7.2f}x{marker} {len(pt_list):>5}")

        # Worst queries for pizza (slowest relative to Lucene)
        print(f"\n  Top 10 worst queries (highest pizza/lucene ratio):")
        ratios = []
        for qstr in pizza_times:
            pt = pizza_times[qstr]
            lt = lucene_times[qstr]
            r = pt / lt if lt > 1 else pt
            ratios.append((r, pt, lt, qstr))
        ratios.sort(reverse=True)
        for r, pt, lt, qstr in ratios[:10]:
            print(f"    {r:>6.1f}x  pizza={pt:>8.0f}µs  lucene={lt:>8.0f}µs  '{qstr}'")

        # Best queries for pizza (fastest relative to Lucene)
        print(f"\n  Top 10 best queries (lowest pizza/lucene ratio):")
        ratios.sort()
        for r, pt, lt, qstr in ratios[:10]:
            print(f"    {r:>6.2f}x  pizza={pt:>8.0f}µs  lucene={lt:>8.0f}µs  '{qstr}'")


if __name__ == "__main__":
    main()
