#!/usr/bin/env python3
"""Analyze phrase query characteristics to find patterns in slow queries."""
import json

with open("results.json") as f:
    data = json.load(f)

# Focus on phrase queries in TOP_100
cmd = "TOP_100"
pizza_qs = {q["query"]: q for q in data.get(cmd, {}).get("pizza-engine-0.1", [])}
tantivy_qs = {q["query"]: q for q in data.get(cmd, {}).get("tantivy-0.22", [])}

rows = []
for query, pq in pizza_qs.items():
    if "phrase" not in ",".join(pq.get("tags", [])):
        continue
    tq = tantivy_qs.get(query)
    if not tq:
        continue
    pd = pq["duration"][-1] if pq["duration"] else 0
    td = tq["duration"][-1] if tq["duration"] else 0
    ratio = pd / td if td > 0 else 999
    count = pq.get("count", 0)
    rows.append((ratio, pd, td, count, query))

# Sort by ratio descending (worst first)
rows.sort(key=lambda x: -x[0])
print(f"{'Ratio':>7s} {'Pizza':>8s} {'Tantivy':>8s} {'Count':>8s}  Query")
for ratio, pd, td, count, query in rows[:30]:
    marker = " <<<" if ratio > 1.0 else ""
    print(f"{ratio:>6.2f}x {pd:>7d}us {td:>7d}us {count:>8d}  {query}{marker}")

print(f"\n--- Correlation analysis ---")
# Check if slow queries correlate with low count (few matches)
slower = [r for r in rows if r[0] > 1.0]
faster = [r for r in rows if r[0] <= 1.0]
if slower:
    avg_count_slower = sum(r[3] for r in slower) / len(slower)
    avg_count_faster = sum(r[3] for r in faster) / len(faster) if faster else 0
    print(f"Avg count (pizza slower): {avg_count_slower:.0f}")
    print(f"Avg count (pizza faster): {avg_count_faster:.0f}")
    avg_time_slower = sum(r[1] for r in slower) / len(slower)
    print(f"Avg pizza time (slower): {avg_time_slower:.0f}us")
