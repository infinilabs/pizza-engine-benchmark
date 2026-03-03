#!/usr/bin/env python3
"""Deep-dive into the worst-case queries to understand patterns."""
import json
from collections import defaultdict

with open("results.json") as f:
    data = json.load(f)

# Collect all per-query data
all_queries = {}
for task in ['COUNT', 'TOP_10', 'TOP_100']:
    pizza_list = data.get(task, {}).get('pizza-engine-0.1', [])
    tantivy_list = data.get(task, {}).get('tantivy-0.22', [])
    lucene_list = data.get(task, {}).get('lucene-9.9.2', [])
    
    tantivy_map = {e['query']: e for e in tantivy_list}
    lucene_map = {e['query']: e for e in lucene_list}
    
    for entry in pizza_list:
        q = entry['query']
        tags = entry.get('tags', [])
        p = min(entry['duration'])
        t_entry = tantivy_map.get(q)
        l_entry = lucene_map.get(q)
        t = min(t_entry['duration']) if t_entry else None
        l = min(l_entry['duration']) if l_entry else None
        
        key = q
        if key not in all_queries:
            all_queries[key] = {'tags': tags}
        all_queries[key][f'{task}_pizza'] = p
        all_queries[key][f'{task}_tantivy'] = t
        all_queries[key][f'{task}_lucene'] = l
        if t and t > 0:
            all_queries[key][f'{task}_ratio'] = p / t

# Focus on specific worst cases
print("=" * 80)
print("DEEP DIVE: Worst-case queries (ratio > 1.5 or absolute > 10ms)")
print("=" * 80)

worst = []
for q, d in all_queries.items():
    for task in ['COUNT', 'TOP_10', 'TOP_100']:
        ratio = d.get(f'{task}_ratio', 0)
        p = d.get(f'{task}_pizza', 0)
        if ratio > 1.2 or p > 10000:
            worst.append((ratio, p, task, q, d))

worst.sort(key=lambda x: -x[0])
seen = set()
for ratio, p, task, q, d in worst[:40]:
    if q in seen:
        continue
    seen.add(q)
    print(f"\nQuery: {q}")
    print(f"  Tags: {d['tags']}")
    for t in ['COUNT', 'TOP_10', 'TOP_100']:
        pp = d.get(f'{t}_pizza')
        tt = d.get(f'{t}_tantivy')
        ll = d.get(f'{t}_lucene')
        rr = d.get(f'{t}_ratio', 0)
        if pp:
            marker = " <<<" if rr > 1.0 else ""
            print(f"  {t:8s}  pizza={pp:8d}us  tantivy={tt:8d}us  lucene={ll:8d}us  ratio={rr:.2f}x{marker}")

# Category analysis
print("\n" + "=" * 80)
print("CATEGORY BREAKDOWN: Where pizza loses")
print("=" * 80)

categories = defaultdict(list)
for q, d in all_queries.items():
    for task in ['COUNT', 'TOP_10', 'TOP_100']:
        ratio = d.get(f'{task}_ratio', 0)
        p = d.get(f'{task}_pizza', 0)
        if ratio > 1.0:  # pizza slower
            # Categorize
            tags = d['tags']
            if 'phrase' in tags and 'num_tokens_3' in str(tags):
                cat = 'phrase:3tok'
            elif 'phrase' in tags and '>3' in str(tags):
                cat = 'phrase:>3tok'
            elif 'phrase' in tags:
                cat = 'phrase:2tok'
            elif 'union' in tags and 'global' in tags:
                cat = 'union:global'
            elif 'intersection' in tags and 'global' in tags:
                cat = 'intersection:global'
            elif 'union' in tags:
                cat = 'union'
            elif 'intersection' in tags:
                cat = 'intersection'
            else:
                cat = 'other'
            categories[(task, cat)].append((ratio, p, q))

for (task, cat), items in sorted(categories.items(), key=lambda x: -max(r for r,_,_ in x[1])):
    items.sort(reverse=True)
    total_excess = sum(p - p/r for r, p, _ in items)
    print(f"\n[{task}] {cat}: {len(items)} queries slower, max_ratio={items[0][0]:.2f}x, total_excess={total_excess:.0f}us")
    for ratio, p, q in items[:5]:
        print(f"    {ratio:.2f}x  {p:8d}us  {q}")

# Summary
print("\n" + "=" * 80)
print("SUMMARY: Top bottleneck categories by total excess time")
print("=" * 80)
cat_excess = []
for (task, cat), items in categories.items():
    total_excess = sum(p - p/r for r, p, _ in items)
    count = len(items)
    max_ratio = max(r for r, _, _ in items)
    cat_excess.append((total_excess, task, cat, count, max_ratio))
cat_excess.sort(reverse=True)
for excess, task, cat, count, max_ratio in cat_excess:
    print(f"  [{task:8s}] {cat:25s}  excess={excess:10.0f}us  queries={count:3d}  max_ratio={max_ratio:.2f}x")
