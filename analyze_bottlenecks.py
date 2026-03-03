#!/usr/bin/env python3
"""Analyze per-query-type bottlenecks to identify remaining optimization opportunities."""
import json
import statistics

data = json.load(open('results.json'))

def get_engine_data(task, engine):
    return data.get(task, {}).get(engine, [])

def median(vals):
    return statistics.median(vals) if vals else 0

print("=" * 80)
print("  INTERSECTION: TOP_10 vs TOP_100 comparison")
print("=" * 80)

for task in ['TOP_10', 'TOP_100']:
    pizza = {r['query']: r['duration'][0] for r in get_engine_data(task, 'pizza-engine-0.1')}
    tantivy = {r['query']: r['duration'][0] for r in get_engine_data(task, 'tantivy-0.22')}
    tags_map = {r['query']: r['tags'] for r in get_engine_data(task, 'pizza-engine-0.1')}
    
    rows = []
    for q, pd in pizza.items():
        tags = tags_map.get(q, [])
        if 'intersection' in tags and q in tantivy:
            td = tantivy[q]
            ratio = pd / td if td > 0 else 0
            rows.append((pd, td, ratio, q))
    
    rows.sort(key=lambda x: -x[0])
    print(f"\n  {task} — Top 15 slowest intersection queries:")
    for pd, td, ratio, q in rows[:15]:
        print(f"    {pd:7d}us / {td:7d}us = {ratio:.2f}x  {q}")
    
    ratios = [r[2] for r in rows]
    print(f"  Median ratio: {median(ratios):.3f}x")

print("\n" + "=" * 80)
print("  PHRASE: TOP_10 vs TOP_100 comparison")
print("=" * 80)

for task in ['TOP_10', 'TOP_100']:
    pizza = {r['query']: r['duration'][0] for r in get_engine_data(task, 'pizza-engine-0.1')}
    tantivy = {r['query']: r['duration'][0] for r in get_engine_data(task, 'tantivy-0.22')}
    tags_map = {r['query']: r['tags'] for r in get_engine_data(task, 'pizza-engine-0.1')}
    
    rows = []
    for q, pd in pizza.items():
        tags = tags_map.get(q, [])
        if 'phrase' in tags and q in tantivy:
            td = tantivy[q]
            ratio = pd / td if td > 0 else 0
            rows.append((pd, td, ratio, q))
    
    rows.sort(key=lambda x: -x[0])
    print(f"\n  {task} — Top 15 slowest phrase queries:")
    for pd, td, ratio, q in rows[:15]:
        print(f"    {pd:7d}us / {td:7d}us = {ratio:.2f}x  {q}")
    
    ratios = [r[2] for r in rows]
    print(f"  Median ratio: {median(ratios):.3f}x")

print("\n" + "=" * 80)
print("  WHERE TANTIVY BEATS PIZZA (ratio > 1.0)")
print("=" * 80)

for task in ['COUNT', 'TOP_10', 'TOP_100']:
    pizza = {r['query']: r['duration'][0] for r in get_engine_data(task, 'pizza-engine-0.1')}
    tantivy = {r['query']: r['duration'][0] for r in get_engine_data(task, 'tantivy-0.22')}
    tags_map = {r['query']: r['tags'] for r in get_engine_data(task, 'pizza-engine-0.1')}
    
    rows = []
    for q, pd in pizza.items():
        if q in tantivy:
            td = tantivy[q]
            ratio = pd / td if td > 0 else 0
            if ratio > 1.0:
                tags = tags_map.get(q, [])
                rows.append((pd, td, ratio, tags, q))
    
    rows.sort(key=lambda x: -x[2])
    if rows:
        print(f"\n  {task} — {len(rows)} queries where tantivy is faster:")
        for pd, td, ratio, tags, q in rows[:15]:
            tag_str = ','.join(tags)
            print(f"    {pd:7d}us / {td:7d}us = {ratio:.2f}x  [{tag_str}]  {q}")
    else:
        print(f"\n  {task} — none! pizza is faster on every query")

print("\n" + "=" * 80)
print("  LATENCY DISTRIBUTION (percentiles)")
print("=" * 80)

for task in ['COUNT', 'TOP_10', 'TOP_100']:
    pizza_durations = [r['duration'][0] for r in get_engine_data(task, 'pizza-engine-0.1')]
    tantivy_durations = [r['duration'][0] for r in get_engine_data(task, 'tantivy-0.22')]
    
    if pizza_durations and tantivy_durations:
        pizza_durations.sort()
        tantivy_durations.sort()
        n = len(pizza_durations)
        print(f"\n  {task} (n={n}):")
        for pct in [50, 75, 90, 95, 99]:
            idx = min(int(n * pct / 100), n - 1)
            pv = pizza_durations[idx]
            tv = tantivy_durations[idx]
            print(f"    p{pct:02d}: pizza={pv:7d}us  tantivy={tv:7d}us  ratio={pv/tv:.2f}x")
