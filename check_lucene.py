#!/usr/bin/env python3
"""Check specific queries vs Lucene to see who is more correct."""
import re

with open('cross_check_report.txt') as f:
    lines = f.readlines()

# For the worst-overlap queries between pizza-engine-0.1 and pizza-memory,
# check what happens with lucene-10.4

# First, collect all issues per (cmd, query_num)
issues = {}
i = 0
while i < len(lines):
    hdr = re.match(r'\[(TOP_10|TOP_100|COUNT)\] Query #(\d+): (.*?) \[(.+)\]', lines[i])
    if hdr:
        cmd = hdr.group(1)
        qnum = int(hdr.group(2))
        query = hdr.group(3)
        qtags = hdr.group(4)
        key = (cmd, qnum)
        if key not in issues:
            issues[key] = {'query': query, 'qtags': qtags, 'pairs': {}}
        j = i + 1
        while j < len(lines) and not lines[j].startswith('['):
            m = re.match(r'  (\S+ vs \S+): (.+)', lines[j])
            if m:
                pair = m.group(1)
                detail = m.group(2)
                issues[key]['pairs'][pair] = detail
            j += 1
    i += 1

# Find queries where pizza-engine-0.1 vs pizza-memory has low overlap
print("=== Worst queries: pizza-engine-0.1 vs pizza-memory (0/10 overlap) ===")
print("Checking if lucene also disagrees with pizza-memory or pizza-engine-0.1\n")

for key in sorted(issues.keys()):
    cmd, qnum = key
    if cmd != 'TOP_10':
        continue
    pairs = issues[key]['pairs']
    pm_vs = pairs.get('pizza-engine-0.1 vs pizza-memory', '')
    if 'low doc overlap 0/10' not in pm_vs and 'low doc overlap 1/10' not in pm_vs:
        continue
    
    query = issues[key]['query']
    qtags = issues[key]['qtags']
    print(f"Query #{qnum}: {query} [{qtags}]")
    print(f"  pizza-engine-0.1 vs pizza-memory: {pm_vs}")
    
    # Check lucene vs each pizza
    for p in ['lucene-10.4 vs pizza-engine-0.1', 'lucene-10.4 vs pizza-memory',
              'pizza-memory-multi-core vs pizza-memory', 'pizza-memory-multi-core vs pizza-engine-0.1']:
        if p in pairs:
            print(f"  {p}: {pairs[p]}")
    print()

# Now check: how many of pizza-engine-0.1 vs pizza-memory queries also appear
# in pizza-memory-multi-core vs pizza-memory?
print("\n=== Overlap of problematic queries ===")
pe_vs_pm = set()
pmc_vs_pm = set()
for key in issues:
    cmd, qnum = key
    if cmd != 'TOP_10':
        continue
    pairs = issues[key]['pairs']
    if 'pizza-engine-0.1 vs pizza-memory' in pairs:
        pe_vs_pm.add(qnum)
    if 'pizza-memory-multi-core vs pizza-memory' in pairs:
        pmc_vs_pm.add(qnum)

both = pe_vs_pm & pmc_vs_pm
only_pe = pe_vs_pm - pmc_vs_pm
only_pmc = pmc_vs_pm - pe_vs_pm
print(f"  pizza-engine-0.1 vs pizza-memory: {len(pe_vs_pm)} queries with issues")
print(f"  pizza-memory-multi-core vs pizza-memory: {len(pmc_vs_pm)} queries with issues")
print(f"  Both: {len(both)} queries")
print(f"  Only in pizza-engine-0.1 comparison: {len(only_pe)} queries")
print(f"  Only in pizza-memory-multi-core comparison: {len(only_pmc)} queries")

# For queries that are in BOTH, are they the same kinds of issues?
print(f"\n=== Queries where pizza-engine-0.1 disagrees with pizza-memory but pizza-memory-multi-core does NOT ===")
count = 0
for qnum in sorted(only_pe):
    key = ('TOP_10', qnum)
    if key in issues:
        query = issues[key]['query']
        qtags = issues[key]['qtags']
        pairs = issues[key]['pairs']
        pm_vs = pairs.get('pizza-engine-0.1 vs pizza-memory', '')
        pmc_pe = pairs.get('pizza-memory-multi-core vs pizza-engine-0.1', '')
        count += 1
        if count <= 10:
            print(f"  Query #{qnum}: {query} [{qtags}]")
            print(f"    pizza-engine-0.1 vs pizza-memory: {pm_vs}")
            if pmc_pe:
                print(f"    pizza-memory-multi-core vs pizza-engine-0.1: {pmc_pe}")
print(f"  ... total: {len(only_pe)} queries")
