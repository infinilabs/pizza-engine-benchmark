#!/usr/bin/env python3
"""Show specific examples of cross-check issues for analysis."""
import re
import sys

with open('cross_check_report.txt') as f:
    lines = f.readlines()

# Show first 5 examples of pizza-engine-0.1 vs pizza-memory for different query types
target_pair = 'pizza-engine-0.1 vs pizza-memory'
target_cmd = 'TOP_10'

examples = []
i = 0
while i < len(lines):
    hdr = re.match(r'\[(TOP_10|TOP_100|COUNT)\] Query #(\d+): (.*?) \[(.+)\]', lines[i])
    if hdr:
        cmd = hdr.group(1)
        qnum = hdr.group(2)
        query = hdr.group(3)
        qtags = hdr.group(4)
        # Gather all pairs for this query+cmd
        j = i + 1
        while j < len(lines) and not lines[j].startswith('['):
            if target_pair + ':' in lines[j]:
                # Collect details
                details = []
                details.append(lines[j].rstrip())
                k = j + 1
                while k < len(lines) and not lines[k].startswith('[') and not re.match(r'  \S+ vs \S+:', lines[k]):
                    details.append(lines[k].rstrip())
                    k += 1
                examples.append({
                    'cmd': cmd,
                    'query': query,
                    'qtags': qtags,
                    'details': details
                })
                break
            j += 1
    i += 1

# Show first 10 TOP_10 examples
print(f"=== {target_pair}: TOP_10 examples (showing first 10 of {sum(1 for e in examples if e['cmd']=='TOP_10')}) ===\n")
shown = 0
for ex in examples:
    if ex['cmd'] != 'TOP_10':
        continue
    if shown >= 10:
        break
    print(f"Query: {ex['query']} [{ex['qtags']}]")
    for d in ex['details']:
        print(d)
    print()
    shown += 1

# Count by overlap level for pizza-engine vs pizza-memory TOP_10
print(f"\n=== Overlap distribution for {target_pair} TOP_10 ===")
overlap_dist = {}
for ex in examples:
    if ex['cmd'] != 'TOP_10':
        continue
    for d in ex['details']:
        m = re.search(r'Overlap: (\d+)/(\d+)', d)
        if m:
            overlap = f"{m.group(1)}/{m.group(2)}"
            overlap_dist[overlap] = overlap_dist.get(overlap, 0) + 1
for overlap, cnt in sorted(overlap_dist.items(), key=lambda x: -x[1]):
    print(f"  {overlap}: {cnt}")

# Also show pizza-hybrid-multi-core vs pizza-engine-0.1 - just overlap distribution 
target_pair2 = 'pizza-hybrid-multi-core vs pizza-engine-0.1'
examples2 = []
i = 0
while i < len(lines):
    hdr = re.match(r'\[(TOP_10|TOP_100|COUNT)\] Query #(\d+): (.*?) \[(.+)\]', lines[i])
    if hdr:
        cmd = hdr.group(1)
        j = i + 1
        while j < len(lines) and not lines[j].startswith('['):
            if target_pair2 + ':' in lines[j]:
                details = []
                details.append(lines[j].rstrip())
                k = j + 1
                while k < len(lines) and not lines[k].startswith('[') and not re.match(r'  \S+ vs \S+:', lines[k]):
                    details.append(lines[k].rstrip())
                    k += 1
                examples2.append({
                    'cmd': cmd,
                    'details': details
                })
                break
            j += 1
    i += 1

print(f"\n=== Overlap distribution for {target_pair2} TOP_10 ===")
overlap_dist2 = {}
for ex in examples2:
    if ex['cmd'] != 'TOP_10':
        continue
    for d in ex['details']:
        m = re.search(r'Overlap: (\d+)/(\d+)', d)
        if m:
            overlap = f"{m.group(1)}/{m.group(2)}"
            overlap_dist2[overlap] = overlap_dist2.get(overlap, 0) + 1
for overlap, cnt in sorted(overlap_dist2.items(), key=lambda x: -x[1]):
    print(f"  {overlap}: {cnt}")

# Show a few hybrid examples with worst overlap
print(f"\n=== {target_pair2}: TOP_10 worst overlap examples (first 5) ===")
shown = 0
for ex in examples2:
    if ex['cmd'] != 'TOP_10':
        continue
    for d in ex['details']:
        m = re.search(r'Overlap: (\d+)/(\d+)', d)
        if m and int(m.group(1)) <= 3:
            print(f"  " + "\n  ".join(ex['details']))
            print()
            shown += 1
            break
    if shown >= 5:
        break

# Also check: what is the score diff pattern for pizza-engine-0.1 vs pizza-memory
# Are they score ties (same lowest score)?
print(f"\n=== Score boundary analysis for {target_pair} TOP_10 ===")
tie_count = 0
non_tie_count = 0
for ex in examples:
    if ex['cmd'] != 'TOP_10':
        continue
    detail_text = '\n'.join(ex['details'])
    # Look for "only in A" and "only in B" scores
    only_a_scores = re.findall(r'Only in \S+: doc_id=\d+ score=([\d.]+)', detail_text)
    only_b_scores = re.findall(r'Only in \S+: doc_id=\d+ score=([\d.]+)', detail_text)
    # This is harder without knowing the format. Let's just count
    has_only = 'Only in' in detail_text
    if has_only:
        non_tie_count += 1
    else:
        tie_count += 1
print(f"  Issues with 'Only in' differences: {non_tie_count}")
print(f"  Issues without 'Only in': {tie_count}")
