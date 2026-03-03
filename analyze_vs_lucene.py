#!/usr/bin/env python3
"""Compare Pizza vs Lucene-BP benchmark results."""
import json, os, sys

def classify(query):
    if query.startswith('"'):
        return 'phrase'
    elif query.startswith('+'):
        return 'intersection'
    elif ' ' in query:
        return 'union'
    else:
        return 'term'

def load_results(engine, mode):
    path = f'results/{engine}#{mode}_results.json'
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        data = json.load(f)
    out = {}
    for item in data:
        q = item['query']
        durations = item.get('duration', [])
        if durations:
            s = sorted(durations)
            out[q] = s[len(s) // 2]
    return out

engines = {
    'lucene-bp': 'lucene-9.9.2-bp',
    'lucene': 'lucene-9.9.2',
    'pizza': 'pizza-engine-0.1',
    'tantivy': 'tantivy-0.22',
}

modes = ['TOP_10', 'TOP_100', 'COUNT']
query_types = ['intersection', 'phrase', 'term', 'union']

print("=" * 90)
print("PIZZA vs LUCENE-BP  —  Median Comparison (us)")
print("=" * 90)
print(f"{'Mode':<10} {'Type':<15} {'Pizza':>10} {'Lucene-BP':>12} {'Ratio':>8} {'Pizza Wins':>12}")
print("-" * 90)

for mode in modes:
    pizza_data = load_results(engines['pizza'], mode)
    lucene_data = load_results(engines['lucene-bp'], mode)
    if not pizza_data or not lucene_data:
        print(f"{mode}: missing data")
        continue

    for qt in query_types:
        shared = [(q, pizza_data[q], lucene_data[q])
                  for q in pizza_data if q in lucene_data and classify(q) == qt]
        if not shared:
            continue
        shared.sort(key=lambda x: x[1])  # sort by pizza time
        p_med = sorted([x[1] for x in shared])[len(shared) // 2]
        l_med = sorted([x[2] for x in shared])[len(shared) // 2]
        ratio = p_med / l_med if l_med > 0 else 999
        wins = sum(1 for x in shared if x[1] < x[2])
        marker = " ✅" if ratio < 1.0 else " ❌" if ratio > 1.5 else " ⚠️"
        print(f"{mode:<10} {qt:<15} {p_med:>10} {l_med:>12} {ratio:>7.2f}x {wins:>5}/{len(shared)}{marker}")
    print()

# Detailed slow queries
print("\n" + "=" * 90)
print("QUERIES WHERE PIZZA > 2x SLOWER THAN LUCENE-BP (TOP_10)")
print("=" * 90)
pizza_data = load_results(engines['pizza'], 'TOP_10')
lucene_data = load_results(engines['lucene-bp'], 'TOP_10')

slow = []
for q in pizza_data:
    if q in lucene_data and lucene_data[q] > 0:
        ratio = pizza_data[q] / lucene_data[q]
        if ratio > 2.0:
            slow.append((q, pizza_data[q], lucene_data[q], ratio))

slow.sort(key=lambda x: -x[3])
if slow:
    print(f"{'Query':<55} {'Pizza':>8} {'Lucene':>8} {'Ratio':>8}")
    for q, p, l, r in slow[:20]:
        print(f"{q:<55} {p:>8} {l:>8} {r:>7.1f}x")
else:
    print("(none)")

# Detailed slow queries for TOP_100
print("\n" + "=" * 90)
print("QUERIES WHERE PIZZA > 2x SLOWER THAN LUCENE-BP (TOP_100)")
print("=" * 90)
pizza_data = load_results(engines['pizza'], 'TOP_100')
lucene_data = load_results(engines['lucene-bp'], 'TOP_100')

slow = []
for q in pizza_data:
    if q in lucene_data and lucene_data[q] > 0:
        ratio = pizza_data[q] / lucene_data[q]
        if ratio > 2.0:
            slow.append((q, pizza_data[q], lucene_data[q], ratio))

slow.sort(key=lambda x: -x[3])
if slow:
    print(f"{'Query':<55} {'Pizza':>8} {'Lucene':>8} {'Ratio':>8}")
    for q, p, l, r in slow[:20]:
        print(f"{q:<55} {p:>8} {l:>8} {r:>7.1f}x")
else:
    print("(none)")

# Detailed slow queries for COUNT
print("\n" + "=" * 90)
print("QUERIES WHERE PIZZA > 2x SLOWER THAN LUCENE-BP (COUNT)")
print("=" * 90)
pizza_data = load_results(engines['pizza'], 'COUNT')
lucene_data = load_results(engines['lucene-bp'], 'COUNT')

slow = []
for q in pizza_data:
    if q in lucene_data and lucene_data[q] > 0:
        ratio = pizza_data[q] / lucene_data[q]
        if ratio > 2.0:
            slow.append((q, pizza_data[q], lucene_data[q], ratio))

slow.sort(key=lambda x: -x[3])
if slow:
    print(f"{'Query':<55} {'Pizza':>8} {'Lucene':>8} {'Ratio':>8}")
    for q, p, l, r in slow[:20]:
        print(f"{q:<55} {p:>8} {l:>8} {r:>7.1f}x")
else:
    print("(none)")

# Also show all-engines comparison for context
print("\n" + "=" * 90)
print("THREE-WAY COMPARISON: Pizza vs Lucene-BP vs Tantivy (median us)")
print("=" * 90)
print(f"{'Mode':<10} {'Type':<15} {'Pizza':>8} {'Lucene-BP':>10} {'Tantivy':>10} {'P/L':>8} {'P/T':>8}")
print("-" * 90)

for mode in modes:
    pd = load_results(engines['pizza'], mode)
    ld = load_results(engines['lucene-bp'], mode)
    td = load_results(engines['tantivy'], mode)

    for qt in query_types:
        shared = [q for q in pd if q in ld and q in td and classify(q) == qt]
        if not shared:
            continue
        p_vals = sorted([pd[q] for q in shared])
        l_vals = sorted([ld[q] for q in shared])
        t_vals = sorted([td[q] for q in shared])
        n = len(shared)
        p_med = p_vals[n // 2]
        l_med = l_vals[n // 2]
        t_med = t_vals[n // 2]
        pr_l = p_med / l_med if l_med > 0 else 999
        pr_t = p_med / t_med if t_med > 0 else 999
        print(f"{mode:<10} {qt:<15} {p_med:>8} {l_med:>10} {t_med:>10} {pr_l:>7.2f}x {pr_t:>7.2f}x")
    print()
