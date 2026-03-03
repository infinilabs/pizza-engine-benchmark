#!/usr/bin/env python3
"""Deep analysis of Pizza vs Lucene bottlenecks."""
import json, os, statistics
from collections import defaultdict

# Load all results
results = {}
for f in os.listdir('results'):
    if f.endswith('_results.json'):
        engine_cmd = f.replace('_results.json', '')
        engine, cmd = engine_cmd.split('#', 1)
        with open(f'results/{f}') as fh:
            data = json.load(fh)
        results[(engine, cmd)] = {item['query']: item for item in data}

def get_us(item):
    """Get median duration in microseconds from a result item."""
    d = item.get('duration', [0])
    if isinstance(d, list) and d:
        return sorted(d)[len(d)//2]  # median of runs
    return d

def analyze_category(command, tag):
    pizza = results.get(('pizza-engine-0.1', command), {})
    lucene = results.get(('lucene-9.9.2-bp', command), {})
    tantivy = results.get(('tantivy-0.22', command), {})
    
    items = []
    for q, pdata in pizza.items():
        if tag not in pdata.get('tags', []):
            continue
        ldata = lucene.get(q)
        tdata = tantivy.get(q)
        if not ldata:
            continue
        pus = get_us(pdata)
        lus = get_us(ldata)
        ratio = pus / max(lus, 1)
        t_us = get_us(tdata) if tdata else 0
        items.append((ratio, pus, lus, t_us, q, len(q.split())))
    
    items.sort(reverse=True)
    return items

# === COUNT UNION analysis ===
print("=" * 100)
print("COUNT UNION — Top 25 slowest (Pizza vs Lucene)")
print("=" * 100)
items = analyze_category('COUNT', 'union')
print(f"{'Query':<55} {'#terms':>6} {'Pizza':>8} {'Lucene':>8} {'Tantivy':>8} {'Ratio':>8}")
print("-" * 100)
for ratio, pus, lus, tus, q, nterms in items[:25]:
    print(f"{q:<55} {nterms:>6} {pus:>8} {lus:>8} {tus:>8} {ratio:>8.1f}x")

p_all = [x[1] for x in items]
l_all = [x[2] for x in items]
t_all = [x[3] for x in items]
print(f"\nPizza   median={statistics.median(p_all):>6.0f}  mean={statistics.mean(p_all):>6.0f}  p95={sorted(p_all)[int(len(p_all)*0.95)]:>6.0f}")
print(f"Lucene  median={statistics.median(l_all):>6.0f}  mean={statistics.mean(l_all):>6.0f}  p95={sorted(l_all)[int(len(l_all)*0.95)]:>6.0f}")
print(f"Tantivy median={statistics.median(t_all):>6.0f}  mean={statistics.mean(t_all):>6.0f}  p95={sorted(t_all)[int(len(t_all)*0.95)]:>6.0f}")

# Correlation: does number of terms correlate with slowdown?
print(f"\n--- Term count vs ratio ---")
by_nterms = defaultdict(list)
for ratio, pus, lus, tus, q, nterms in items:
    by_nterms[nterms].append(ratio)
for nt in sorted(by_nterms.keys()):
    vals = by_nterms[nt]
    print(f"  {nt} terms: n={len(vals):>3}  median_ratio={statistics.median(vals):.2f}x  mean_ratio={statistics.mean(vals):.2f}x")

# === TOP_10 UNION analysis ===
print("\n" + "=" * 100)
print("TOP_10 UNION — Top 25 slowest (Pizza vs Lucene)")
print("=" * 100)
items10 = analyze_category('TOP_10', 'union')
print(f"{'Query':<55} {'#terms':>6} {'Pizza':>8} {'Lucene':>8} {'Tantivy':>8} {'Ratio':>8}")
print("-" * 100)
for ratio, pus, lus, tus, q, nterms in items10[:25]:
    print(f"{q:<55} {nterms:>6} {pus:>8} {lus:>8} {tus:>8} {ratio:>8.1f}x")

# === TOP_10 PHRASE — worst cases ===
print("\n" + "=" * 100)
print("TOP_10 PHRASE — Top 25 slowest (Pizza vs Lucene)")
print("=" * 100)
items_ph = analyze_category('TOP_10', 'phrase')
print(f"{'Query':<55} {'#terms':>6} {'Pizza':>8} {'Lucene':>8} {'Tantivy':>8} {'Ratio':>8}")
print("-" * 100)
for ratio, pus, lus, tus, q, nterms in items_ph[:25]:
    print(f"{q:<55} {nterms:>6} {pus:>8} {lus:>8} {tus:>8} {ratio:>8.1f}x")

# === Phrase queries: how many have quotes vs unquoted multi-word ===
print("\n" + "=" * 100)  
print("TOP_10 PHRASE — Quoted vs Unquoted breakdown")
print("=" * 100)
quoted = [(r, p, l, t, q, n) for r, p, l, t, q, n in items_ph if '"' in q]
unquoted = [(r, p, l, t, q, n) for r, p, l, t, q, n in items_ph if '"' not in q]
print(f"Quoted phrases: {len(quoted)}  (median ratio: {statistics.median([x[0] for x in quoted]):.2f}x)")
print(f"Unquoted multi-word: {len(unquoted)}  (median ratio: {statistics.median([x[0] for x in unquoted]) if unquoted else 0:.2f}x)")

if quoted:
    print(f"\n  Quoted — Pizza median: {statistics.median([x[1] for x in quoted]):.0f}  Lucene median: {statistics.median([x[2] for x in quoted]):.0f}")
if unquoted:
    print(f"  Unquoted — Pizza median: {statistics.median([x[1] for x in unquoted]):.0f}  Lucene median: {statistics.median([x[2] for x in unquoted]):.0f}")

# === Distribution of slowdowns ===
print("\n" + "=" * 100)
print("SLOWDOWN DISTRIBUTION — How many queries lose by how much?")
print("=" * 100)
for cmd in ['TOP_10', 'TOP_100', 'COUNT']:
    for tag in ['union', 'intersection', 'phrase']:
        items_dist = analyze_category(cmd, tag)
        if not items_dist:
            continue
        ratios = [x[0] for x in items_dist]
        wins = sum(1 for r in ratios if r < 1.0)
        close = sum(1 for r in ratios if 1.0 <= r < 1.5)
        slow2x = sum(1 for r in ratios if 1.5 <= r < 2.0)
        slow3x = sum(1 for r in ratios if 2.0 <= r < 3.0)
        slow3p = sum(1 for r in ratios if r >= 3.0)
        total = len(ratios)
        print(f"  {cmd:>7} {tag:<13} n={total:>3}  wins={wins:>3}({100*wins/total:.0f}%)  <1.5x={close:>3}  1.5-2x={slow2x:>3}  2-3x={slow3x:>3}  >3x={slow3p:>3}")
