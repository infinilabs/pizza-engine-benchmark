#!/usr/bin/env python3
import json, sys

with open("results.json") as f:
    data = json.load(f)

rows = []
for task in ['COUNT', 'TOP_10', 'TOP_100']:
    pizza_list = data.get(task, {}).get('pizza-engine-0.1', [])
    tantivy_list = data.get(task, {}).get('tantivy-0.22', [])
    
    # Build tantivy lookup by query
    tantivy_map = {}
    for entry in tantivy_list:
        q = entry['query']
        dur = entry['duration']
        tantivy_map[q] = min(dur) if dur else 999999
    
    for entry in pizza_list:
        q = entry['query']
        dur = entry['duration']
        tags = entry.get('tags', [])
        p = min(dur) if dur else 999999
        t = tantivy_map.get(q, None)
        if t and t > 0:
            ratio = p / t
            rows.append((ratio, p, t, task, tags, q))

print("=== Queries where pizza is SLOWEST relative to tantivy (ratio > 1 = pizza slower) ===")
rows_sorted = sorted(rows, key=lambda x: -x[0])
for ratio, p, t, task, tags, query in rows_sorted[:30]:
    tag_str = ",".join(tags)
    print(f"  ratio={ratio:.2f}x  pizza={p}us  tantivy={t}us  [{task}] [{tag_str}] {query}")

print()
print("=== Queries with highest absolute pizza latency ===")
rows_sorted2 = sorted(rows, key=lambda x: -x[1])
for ratio, p, t, task, tags, query in rows_sorted2[:30]:
    tag_str = ",".join(tags)
    print(f"  pizza={p}us  tantivy={t}us  ratio={ratio:.2f}x  [{task}] [{tag_str}] {query}")

print()
print("=== Per-tag worst ratio (median) ===")
from collections import defaultdict
tag_ratios = defaultdict(list)
for ratio, p, t, task, tags, query in rows:
    for tag in tags:
        tag_ratios[(task, tag)].append(ratio)

tag_medians = []
for (task, tag), ratios in tag_ratios.items():
    ratios.sort()
    med = ratios[len(ratios)//2]
    avg = sum(ratios)/len(ratios)
    worst = max(ratios)
    tag_medians.append((avg, med, worst, task, tag, len(ratios)))

tag_medians.sort(reverse=True)
for avg, med, worst, task, tag, n in tag_medians[:30]:
    print(f"  [{task}] {tag:30s}  avg={avg:.2f}x  med={med:.2f}x  worst={worst:.2f}x  n={n}")
