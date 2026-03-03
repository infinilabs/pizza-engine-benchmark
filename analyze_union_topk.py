#!/usr/bin/env python3
"""Per-query TOP_10 union analysis."""
import json
from collections import defaultdict

pizza = json.load(open('results/pizza-engine-0.1#TOP_10_results.json'))
lucene = json.load(open('results/lucene-9.9.2-bp#TOP_10_results.json'))

lucene_by_q = {}
for q in lucene:
    lucene_by_q[q['query']] = sorted(q['duration'])[len(q['duration'])//2]

results = []
for q in pizza:
    if 'union' in q['tags']:
        pmed = sorted(q['duration'])[len(q['duration'])//2]
        lmed = lucene_by_q.get(q['query'], 0)
        if lmed > 0:
            results.append((pmed/lmed, pmed, lmed, q['query']))

results.sort(reverse=True)
print(f"{'Ratio':>7s} {'Pizza':>8s} {'Lucene':>8s}  Query")
print("-" * 70)
for ratio, p, l, query in results[:25]:
    print(f"{ratio:7.2f}x {p:8.0f} {l:8.0f}  {query}")

print(f"\nTotal: {len(results)}")
wins = sum(1 for r,_,_,_ in results if r <= 1.0)
print(f"Pizza wins: {wins}/{len(results)} ({100*wins/len(results):.0f}%)")

# Also TOP_100
print("\n\n=== TOP_100 Union ===")
pizza100 = json.load(open('results/pizza-engine-0.1#TOP_100_results.json'))
lucene100 = json.load(open('results/lucene-9.9.2-bp#TOP_100_results.json'))

lucene100_by_q = {}
for q in lucene100:
    lucene100_by_q[q['query']] = sorted(q['duration'])[len(q['duration'])//2]

results100 = []
for q in pizza100:
    if 'union' in q['tags']:
        pmed = sorted(q['duration'])[len(q['duration'])//2]
        lmed = lucene100_by_q.get(q['query'], 0)
        if lmed > 0:
            results100.append((pmed/lmed, pmed, lmed, q['query']))

results100.sort(reverse=True)
print(f"{'Ratio':>7s} {'Pizza':>8s} {'Lucene':>8s}  Query")
print("-" * 70)
for ratio, p, l, query in results100[:25]:
    print(f"{ratio:7.2f}x {p:8.0f} {l:8.0f}  {query}")

print(f"\nTotal: {len(results100)}")
wins = sum(1 for r,_,_,_ in results100 if r <= 1.0)
print(f"Pizza wins: {wins}/{len(results100)} ({100*wins/len(results100):.0f}%)")
