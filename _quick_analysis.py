#!/usr/bin/env python3
"""Quick analysis of pizza-memory vs lucene-10.4-bp after optimizations."""
import json, statistics

with open('docs/results.json') as f:
    data = json.load(f)

modes = ['COUNT', 'TOP_10', 'TOP_100']
for mode in modes:
    pizza = {r['query']: statistics.median(r['duration']) for r in data[mode].get('pizza-memory', [])}
    lucene = {r['query']: statistics.median(r['duration']) for r in data[mode].get('lucene-10.4-bp', [])}

    # Find union queries (multi-word, no quotes, no +)
    union_qs = [q for q in pizza if ' ' in q and not q.startswith('"') and '+' not in q]

    if not union_qs:
        continue

    ratios = []
    worst = []
    for q in union_qs:
        if q in lucene and lucene[q] > 0:
            r = pizza[q] / lucene[q]
            ratios.append(r)
            worst.append((r, pizza[q], lucene[q], q))

    avg_ratio = sum(ratios) / len(ratios) if ratios else 0
    wins = sum(1 for r in ratios if r <= 1.0)
    losses = sum(1 for r in ratios if r > 1.0)
    print(f'=== {mode} Union queries: pizza-memory vs lucene-10.4-bp ===')
    print(f'  Avg ratio: {avg_ratio:.2f}x  (wins: {wins}, losses: {losses})')

    worst.sort(key=lambda x: -x[0])
    print(f'  Top 5 worst:')
    for ratio, p, l, q in worst[:5]:
        print(f'    {ratio:5.2f}x  pizza={p:8.0f}us  lucene={l:8.0f}us  "{q}"')

    worst.sort(key=lambda x: x[0])
    print(f'  Top 5 best:')
    for ratio, p, l, q in worst[:5]:
        print(f'    {ratio:5.2f}x  pizza={p:8.0f}us  lucene={l:8.0f}us  "{q}"')
    print()

# Global summary: all query types
print("=== GLOBAL SUMMARY (all queries, all types) ===")
for mode in modes:
    pizza_all = {r['query']: statistics.median(r['duration']) for r in data[mode].get('pizza-memory', [])}
    lucene_all = {r['query']: statistics.median(r['duration']) for r in data[mode].get('lucene-10.4-bp', [])}
    common = set(pizza_all.keys()) & set(lucene_all.keys())
    p_total = sum(pizza_all[q] for q in common)
    l_total = sum(lucene_all[q] for q in common)
    ratio = p_total / l_total if l_total > 0 else 0
    wins = sum(1 for q in common if pizza_all[q] <= lucene_all[q])
    losses = sum(1 for q in common if pizza_all[q] > lucene_all[q])
    print(f'  {mode}: total_ratio={ratio:.2f}x  wins={wins}  losses={losses}')
