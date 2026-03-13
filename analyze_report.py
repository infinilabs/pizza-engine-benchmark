#!/usr/bin/env python3
"""Analyze cross_check_report.txt: break down by engine pair and command type."""
import re

pair_cmd = {}
with open('cross_check_report.txt') as f:
    current_cmd = None
    for line in f:
        hdr = re.match(r'\[(TOP_10|TOP_100|COUNT)\]', line)
        if hdr:
            current_cmd = hdr.group(1)
        m = re.match(r'  (\S+ vs \S+):', line)
        if m and current_cmd:
            key = (m.group(1), current_cmd)
            pair_cmd[key] = pair_cmd.get(key, 0) + 1

# Aggregate by pair across commands
pairs = {}
for (pair, cmd), c in pair_cmd.items():
    if pair not in pairs:
        pairs[pair] = {}
    pairs[pair][cmd] = c

focus = [
    'pizza-engine-0.1 vs pizza-memory',
    'pizza-memory-multi-core vs pizza-memory',
    'pizza-memory-multi-core vs pizza-engine-0.1',
    'pizza-hybrid-multi-core vs pizza-engine-0.1',
    'pizza-hybrid-multi-core vs pizza-memory',
    'pizza-hybrid-multi-core vs pizza-memory-multi-core',
    'lucene-10.4 vs pizza-engine-0.1',
    'lucene-10.4 vs pizza-memory',
    'lucene-10.4 vs lucene-10.4-bp',
    'tantivy-0.25 vs tantivy-0.22',
    'tantivy-0.25 vs pizza-engine-0.1',
]

print(f"{'Pair':52s} {'COUNT':>7s} {'TOP_10':>7s} {'TOP_100':>7s} {'TOTAL':>7s}")
print('-' * 80)
for p in focus:
    d = pairs.get(p, {})
    cnt = d.get('COUNT', 0)
    t10 = d.get('TOP_10', 0)
    t100 = d.get('TOP_100', 0)
    total = cnt + t10 + t100
    print(f'{p:52s} {cnt:7d} {t10:7d} {t100:7d} {total:7d}')

# Now break down COUNT issues for pizza pairs
print("\n\n=== COUNT issues breakdown (pizza-internal) ===")
count_pairs = [
    'pizza-engine-0.1 vs pizza-memory',
    'pizza-memory-multi-core vs pizza-memory',
    'pizza-memory-multi-core vs pizza-engine-0.1',
    'pizza-hybrid-multi-core vs pizza-engine-0.1',
    'pizza-hybrid-multi-core vs pizza-memory',
    'pizza-hybrid-multi-core vs pizza-memory-multi-core',
]
for p in count_pairs:
    d = pairs.get(p, {})
    cnt = d.get('COUNT', 0)
    if cnt > 0:
        print(f"  {p}: {cnt} COUNT issues")

# Parse query types for pizza-hybrid-multi-core vs pizza-engine-0.1  
print("\n\n=== Issue types for pizza-hybrid-multi-core vs pizza-engine-0.1 ===")
qtype_counts = {}
with open('cross_check_report.txt') as f:
    current_cmd = None
    current_qtags = None
    for line in f:
        hdr = re.match(r'\[(TOP_10|TOP_100|COUNT)\] Query #\d+: .* \[(.+)\]', line)
        if hdr:
            current_cmd = hdr.group(1)
            current_qtags = hdr.group(2)
        m = re.match(r'  pizza-hybrid-multi-core vs pizza-engine-0.1:', line)
        if m and current_cmd and current_qtags:
            key = (current_cmd, current_qtags)
            qtype_counts[key] = qtype_counts.get(key, 0) + 1
for (cmd, qtags), c in sorted(qtype_counts.items(), key=lambda x: -x[1]):
    print(f"  [{cmd}] {qtags}: {c}")

# Parse query types for pizza-engine-0.1 vs pizza-memory
print("\n\n=== Issue types for pizza-engine-0.1 vs pizza-memory ===")
qtype_counts2 = {}
with open('cross_check_report.txt') as f:
    current_cmd = None
    current_qtags = None
    for line in f:
        hdr = re.match(r'\[(TOP_10|TOP_100|COUNT)\] Query #\d+: .* \[(.+)\]', line)
        if hdr:
            current_cmd = hdr.group(1)
            current_qtags = hdr.group(2)
        m = re.match(r'  pizza-engine-0.1 vs pizza-memory:', line)
        if m and current_cmd and current_qtags:
            key = (current_cmd, current_qtags)
            qtype_counts2[key] = qtype_counts2.get(key, 0) + 1
for (cmd, qtags), c in sorted(qtype_counts2.items(), key=lambda x: -x[1]):
    print(f"  [{cmd}] {qtags}: {c}")

# Count COUNT issues specifically for hybrid
print("\n\n=== COUNT issues for hybrid-multi-core vs each engine ===")
count_issues = {}
with open('cross_check_report.txt') as f:
    current_cmd = None
    for line in f:
        hdr = re.match(r'\[(COUNT)\]', line)
        if hdr:
            current_cmd = 'COUNT'
        elif re.match(r'\[(TOP_10|TOP_100)\]', line):
            current_cmd = None
        m = re.match(r'  (pizza-hybrid-multi-core vs \S+):', line)
        if m and current_cmd == 'COUNT':
            pair = m.group(1)
            count_issues[pair] = count_issues.get(pair, 0) + 1
for pair, c in sorted(count_issues.items(), key=lambda x: -x[1]):
    print(f"  {pair}: {c}")
