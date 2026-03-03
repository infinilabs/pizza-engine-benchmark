#!/usr/bin/env python3
import json

with open('results/pizza-engine-0.1-bmw#TOP_10_results.json') as f:
    bmw = json.load(f)
with open('results/pizza-engine-0.1#TOP_10_results.json') as f:
    nonbmw = json.load(f)

def tag_stats(data, tag_prefix):
    entries = [(e['query'], e['duration'][0]) for e in data if tag_prefix in e['tags'] and e['duration']]
    if not entries:
        return 0, 0
    avg = sum(d for _,d in entries) / len(entries)
    return len(entries), avg

for tag in ['phrase', 'union', 'intersection', 'term', 'two-phase-critic']:
    n_b, avg_b = tag_stats(bmw, tag)
    n_n, avg_n = tag_stats(nonbmw, tag)
    if n_b and n_n:
        print(f"{tag:30s}  BMW: n={n_b:3d} avg={avg_b:>8.0f}us | non-BMW: n={n_n:3d} avg={avg_n:>8.0f}us | ratio={avg_b/avg_n:.1f}x")
    elif n_b:
        print(f"{tag:30s}  BMW: n={n_b:3d} avg={avg_b:>8.0f}us | non-BMW: N/A")

# Compute weighted totals
print()
total_bmw = sum(e['duration'][0] for e in bmw if e['duration'])
total_nonbmw = sum(e['duration'][0] for e in nonbmw if e['duration'])
print(f"Total time: BMW={total_bmw}us  non-BMW={total_nonbmw}us  ratio={total_bmw/total_nonbmw:.1f}x")

# Time breakdown by tag for BMW
tag_totals = {}
for e in bmw:
    if not e['duration']:
        continue
    for tag in ['phrase', 'union', 'intersection', 'term', 'two-phase-critic']:
        if tag in e['tags']:
            tag_totals.setdefault(tag, 0)
            tag_totals[tag] += e['duration'][0]
            break

print()
print("BMW time breakdown:")
for tag, total in sorted(tag_totals.items(), key=lambda x: -x[1]):
    pct = total / total_bmw * 100
    print(f"  {tag:30s}  {total:>10d}us  ({pct:.1f}%)")
