#!/usr/bin/env python3
"""Compare pizza-engine COUNT results vs tantivy to identify mismatch patterns."""
import json
from collections import Counter

with open('results.json') as f:
    data = json.load(f)

pizza = data['COUNT']['pizza-engine-0.1']
tantivy = data['COUNT']['tantivy-0.22']

mismatches = []
matches = 0
for p, t in zip(pizza, tantivy):
    pq = p['query']
    tq = t['query']
    assert pq == tq, "query mismatch: %s vs %s" % (pq, tq)
    pc = p['count']
    tc = t['count']
    if pc != tc:
        mismatches.append((pq, p.get('tags', []), pc, tc))
    else:
        matches += 1

print("Matches: %d, Mismatches: %d" % (matches, len(mismatches)))
print("")
print("First 40 mismatches (query, tags, pizza_count, tantivy_count):")
for q, tags, pc, tc in mismatches[:40]:
    diff = pc - tc
    pct = (diff / tc * 100) if tc > 0 else float('inf')
    print("  %+8d (%+6.1f%%)  pizza=%-10d tantivy=%-10d  tags=%-50s  q=%r" % (diff, pct, pc, tc, str(tags), q))

# Categorize
more = sum(1 for _, _, p, t in mismatches if p > t)
less = sum(1 for _, _, p, t in mismatches if p < t)
print("")
print("Pizza returns MORE: %d queries" % more)
print("Pizza returns LESS: %d queries" % less)

# By tag
tag_counts = Counter()
for q, tags, pc, tc in mismatches:
    for tag in tags:
        tag_counts[tag] += 1
print("")
print("Mismatch by tag:")
for tag, cnt in tag_counts.most_common(20):
    print("  %s: %d" % (tag, cnt))

# Check: which tags are fully correct?
all_tag_counts = Counter()
for p in pizza:
    for tag in p.get('tags', []):
        all_tag_counts[tag] += 1
print("")
print("Mismatch rate by tag:")
for tag in sorted(all_tag_counts.keys()):
    total = all_tag_counts[tag]
    bad = tag_counts.get(tag, 0)
    print("  %-40s %3d / %3d mismatched (%.1f%%)" % (tag, bad, total, 100.0 * bad / total))
