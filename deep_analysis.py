#!/usr/bin/env python3
"""Deep analysis of pizza-engine-0.1 vs pizza-memory issues."""
import re

with open('cross_check_report.txt') as f:
    lines = f.readlines()

target = 'pizza-engine-0.1 vs pizza-memory'

# Categorize issues
categories = {
    'low_overlap': [],
    'common_diff': [],
    'score_only': [],
    'reorder': [],
    'other': [],
}

i = 0
while i < len(lines):
    hdr = re.match(r'\[(TOP_10|TOP_100|COUNT)\] Query #(\d+): (.*?) \[(.+)\]', lines[i])
    if hdr:
        cmd = hdr.group(1)
        qnum = hdr.group(2)
        query = hdr.group(3)
        qtags = hdr.group(4)
        j = i + 1
        while j < len(lines) and not lines[j].startswith('['):
            if target + ':' in lines[j]:
                detail = lines[j].strip()
                entry = (cmd, query, qtags, detail)
                if 'low doc overlap' in detail:
                    categories['low_overlap'].append(entry)
                elif 'common,' in detail:
                    categories['common_diff'].append(entry)
                elif 'same doc order but' in detail:
                    categories['score_only'].append(entry)
                elif 'same doc set but different order' in detail:
                    categories['reorder'].append(entry)
                else:
                    categories['other'].append(entry)
            j += 1
    i += 1

for cat, entries in categories.items():
    top10 = [e for e in entries if e[0] == 'TOP_10']
    top100 = [e for e in entries if e[0] == 'TOP_100']
    print(f"\n=== {cat}: {len(entries)} total (TOP_10: {len(top10)}, TOP_100: {len(top100)}) ===")
    for e in top10[:8]:
        print(f"  [{e[0]}] {e[1]} [{e[2]}]")
        print(f"    {e[3]}")

print("\n\n=== Distribution of 'only in' count for TOP_10 common_diff ===")
only_dist = {}
for e in categories['common_diff']:
    if e[0] != 'TOP_10':
        continue
    m = re.search(r'(\d+) common, (\d+) only in', e[3])
    if m:
        common = int(m.group(1))
        only = int(m.group(2))
        key = f"{common} common, {only} differ"
        only_dist[key] = only_dist.get(key, 0) + 1
for k, v in sorted(only_dist.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

print("\n=== Distribution of overlap for TOP_10 low_overlap ===")
ov_dist = {}
for e in categories['low_overlap']:
    if e[0] != 'TOP_10':
        continue
    m = re.search(r'(\d+)/(\d+)', e[3])
    if m:
        ov = f"{m.group(1)}/{m.group(2)}"
        ov_dist[ov] = ov_dist.get(ov, 0) + 1
for k, v in sorted(ov_dist.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

print("\n=== Query type for TOP_10 low_overlap ===")
qt_dist = {}
for e in categories['low_overlap']:
    if e[0] != 'TOP_10':
        continue
    qt_dist[e[2]] = qt_dist.get(e[2], 0) + 1
for k, v in sorted(qt_dist.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

# Also check: pizza-memory-multi-core vs pizza-memory
print("\n\n========================================")
print("=== pizza-memory-multi-core vs pizza-memory ===")
target2 = 'pizza-memory-multi-core vs pizza-memory'
categories2 = {'low_overlap': [], 'common_diff': [], 'score_only': [], 'reorder': [], 'other': []}
i = 0
while i < len(lines):
    hdr = re.match(r'\[(TOP_10|TOP_100|COUNT)\] Query #(\d+): (.*?) \[(.+)\]', lines[i])
    if hdr:
        cmd = hdr.group(1)
        query = hdr.group(3)
        qtags = hdr.group(4)
        j = i + 1
        while j < len(lines) and not lines[j].startswith('['):
            if target2 + ':' in lines[j]:
                detail = lines[j].strip()
                entry = (cmd, query, qtags, detail)
                if 'low doc overlap' in detail:
                    categories2['low_overlap'].append(entry)
                elif 'common,' in detail:
                    categories2['common_diff'].append(entry)
                elif 'same doc order but' in detail:
                    categories2['score_only'].append(entry)
                elif 'same doc set but different order' in detail:
                    categories2['reorder'].append(entry)
                else:
                    categories2['other'].append(entry)
            j += 1
    i += 1

for cat, entries in categories2.items():
    top10 = [e for e in entries if e[0] == 'TOP_10']
    top100 = [e for e in entries if e[0] == 'TOP_100']
    if len(entries) > 0:
        print(f"\n  {cat}: {len(entries)} total (TOP_10: {len(top10)}, TOP_100: {len(top100)})")
        for e in top10[:5]:
            print(f"    [{e[0]}] {e[1]} [{e[2]}]")
            print(f"      {e[3]}")

# Query type breakdown for pizza-memory-multi-core vs pizza-memory TOP_10
print("\n  Query type for TOP_10:")
qt_dist2 = {}
all_top10_2 = []
for entries in categories2.values():
    all_top10_2.extend([e for e in entries if e[0] == 'TOP_10'])
for e in all_top10_2:
    qt_dist2[e[2]] = qt_dist2.get(e[2], 0) + 1
for k, v in sorted(qt_dist2.items(), key=lambda x: -x[1]):
    print(f"    {k}: {v}")
