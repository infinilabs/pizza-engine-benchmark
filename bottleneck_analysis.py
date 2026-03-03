#!/usr/bin/env python3
"""Analyze TOP_100 bottleneck patterns in detail."""
import json, sys
from collections import defaultdict

with open("results.json") as f:
    data = json.load(f)

# Build lookup: (query, command) -> {engine: latency_us}
results = defaultdict(dict)
for cmd, engines_data in data.items():
    for engine, queries in engines_data.items():
        for q in queries:
            key = (q["query"], cmd)
            dur = q["duration"]
            if isinstance(dur, list) and len(dur) > 0:
                results[key][engine] = dur[-1]
            elif isinstance(dur, (int, float)):
                results[key][engine] = dur

# Collect TOP_100 regressions (pizza > tantivy)
regressions = []
for (query, cmd), engines in results.items():
    if cmd != "TOP_100":
        continue
    p = engines.get("pizza-engine-0.1")
    t = engines.get("tantivy-0.22")
    if p is None or t is None or t == 0:
        continue
    ratio = p / t
    excess = p - t  # microseconds pizza is slower
    if ratio > 1.5:  # only consider meaningful regressions
        regressions.append({
            "query": query, "pizza": p, "tantivy": t,
            "ratio": ratio, "excess": excess
        })

regressions.sort(key=lambda x: -x["excess"])

print("=== TOP_100 regressions sorted by EXCESS TIME (pizza - tantivy) ===")
total_excess = 0
for r in regressions[:40]:
    total_excess += r["excess"]
    print(f"  excess={r['excess']:>8}us  ratio={r['ratio']:>5.1f}x  pizza={r['pizza']:>8}us  tantivy={r['tantivy']:>6}us  {r['query']}")

print(f"\nTotal excess across {len(regressions)} regressed queries: {sum(r['excess'] for r in regressions)}us")
print(f"Top 40 account for: {total_excess}us")

# Categorize by query type
print("\n=== Pattern analysis ===")
by_type = defaultdict(list)
for r in regressions:
    q = r["query"]
    if q.startswith('"'):
        qtype = "phrase"
    elif q.startswith('+'):
        qtype = "intersection"
    else:
        qtype = "union"
    by_type[qtype].append(r)

for qtype in sorted(by_type.keys()):
    items = by_type[qtype]
    total = sum(x["excess"] for x in items)
    avg_ratio = sum(x["ratio"] for x in items) / len(items)
    print(f"\n{qtype}: {len(items)} queries, total excess={total}us, avg_ratio={avg_ratio:.1f}x")
    # Show top 5
    for r in sorted(items, key=lambda x: -x["excess"])[:5]:
        print(f"    excess={r['excess']:>8}us  ratio={r['ratio']:>5.1f}x  {r['query']}")

# Special analysis: look at queries where tantivy < 1000us but pizza > 5000us
print("\n=== Small query blowups (tantivy < 1ms, pizza > 5ms) ===")
blowups = [r for r in regressions if r["tantivy"] < 1000 and r["pizza"] > 5000]
blowups.sort(key=lambda x: -x["ratio"])
for r in blowups:
    print(f"  ratio={r['ratio']:>5.1f}x  pizza={r['pizza']:>8}us  tantivy={r['tantivy']:>6}us  {r['query']}")
print(f"Total: {len(blowups)} queries")

# Also look at whether intersection TOP_100 might be broken
print("\n=== Intersection TOP_100 accuracy (spot check) ===")
for (query, cmd), engines in results.items():
    if cmd != "TOP_100" or not query.startswith('+'):
        continue
    p = engines.get("pizza-engine-0.1")
    t = engines.get("tantivy-0.11")
    if p and t and p / t > 20:
        # Check if COUNT for same query exists
        count_key = (query, "COUNT")
        if count_key in results:
            pc = results[count_key].get("pizza-engine-0.1", 0)
            tc = results[count_key].get("tantivy-0.11", 0)
            print(f"  {query}")
            print(f"    TOP_100: pizza={p}us tantivy={t}us ratio={p/t:.1f}x")
            print(f"    COUNT:   pizza={pc}us tantivy={tc}us match={pc==tc}")
