#!/usr/bin/env python3
"""Detailed per-query comparison for union COUNT between pizza and lucene."""
import json, os
from collections import defaultdict

def load_results(path):
    with open(path) as f:
        return json.load(f)

pizza_count = load_results('results/pizza-engine-0.1#COUNT_results.json')
lucene_count = load_results('results/lucene-9.9.2-bp#COUNT_results.json')

# Build lookup by query text
lucene_by_q = {}
for q in lucene_count:
    lucene_by_q[q['query']] = sorted(q['duration'])[len(q['duration'])//2]

# Find worst union queries
union_queries = []
for q in pizza_count:
    if 'union' in q['tags']:
        pmed = sorted(q['duration'])[len(q['duration'])//2]
        lmed = lucene_by_q.get(q['query'], 0)
        if lmed > 0:
            union_queries.append((pmed/lmed, pmed, lmed, q['query'], q.get('count', 0)))

# Sort by ratio descending (worst first)
union_queries.sort(reverse=True)
print(f"{'Ratio':>7s} {'Pizza':>8s} {'Lucene':>8s} {'Count':>10s}  Query")
print("-" * 80)
for ratio, p, l, query, count in union_queries[:30]:
    print(f"{ratio:7.2f}x {p:8.0f} {l:8.0f} {count:10d}  {query}")

print(f"\n--- Summary ---")
print(f"Total union queries: {len(union_queries)}")
wins = sum(1 for r,_,_,_,_ in union_queries if r <= 1.0)
print(f"Pizza wins: {wins}/{len(union_queries)} ({100*wins/len(union_queries):.0f}%)")

# Also check phrase queries
print("\n\n=== TOP_10 Phrase Queries ===")
pizza_top10 = load_results('results/pizza-engine-0.1#TOP_10_results.json')
lucene_top10 = load_results('results/lucene-9.9.2-bp#TOP_10_results.json')

lucene_t10 = {}
for q in lucene_top10:
    lucene_t10[q['query']] = sorted(q['duration'])[len(q['duration'])//2]

phrase_queries = []
for q in pizza_top10:
    if 'phrase' in q['tags']:
        pmed = sorted(q['duration'])[len(q['duration'])//2]
        lmed = lucene_t10.get(q['query'], 0)
        if lmed > 0:
            phrase_queries.append((pmed/lmed, pmed, lmed, q['query']))

phrase_queries.sort(reverse=True)
print(f"{'Ratio':>7s} {'Pizza':>8s} {'Lucene':>8s}  Query")
print("-" * 70)
for ratio, p, l, query in phrase_queries[:20]:
    print(f"{ratio:7.2f}x {p:8.0f} {l:8.0f}  {query}")

print(f"\nTotal phrase queries: {len(phrase_queries)}")
wins = sum(1 for r,_,_,_ in phrase_queries if r <= 1.0)
print(f"Pizza wins: {wins}/{len(phrase_queries)} ({100*wins/len(phrase_queries):.0f}%)")
