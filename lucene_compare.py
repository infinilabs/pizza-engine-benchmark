#!/usr/bin/env python3
"""Check which pizza engine matches Lucene better on the problematic queries."""
import re

with open('cross_check_report.txt') as f:
    lines = f.readlines()

# Collect ALL pairwise issues per (cmd, query_num) 
# Handle duplicate pair entries (low_overlap + detail) by collecting all
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
                if pair not in issues[key]['pairs']:
                    issues[key]['pairs'][pair] = []
                issues[key]['pairs'][pair].append(detail)
            j += 1
    i += 1

# For queries where pizza-memory differs from pizza-engine-0.1 TOP_10,
# check if lucene also differs from pizza-memory or pizza-engine-0.1
print("=== Who matches Lucene better? ===\n")

pizza_mem_better = 0  # pizza-memory matches lucene but pizza-engine-0.1 doesn't
pizza_eng_better = 0  # pizza-engine-0.1 matches lucene but pizza-memory doesn't
both_differ = 0       # both differ from lucene
neither_differ = 0    # lucene has no issue with either

for key in sorted(issues.keys()):
    cmd, qnum = key
    if cmd != 'TOP_10':
        continue
    pairs = issues[key]['pairs']
    
    # Check if pizza-engine-0.1 vs pizza-memory has an issue
    pe_pm = pairs.get('pizza-engine-0.1 vs pizza-memory', [])
    if not pe_pm:
        continue
    
    # Check lucene vs each
    luc_pe = pairs.get('lucene-10.4 vs pizza-engine-0.1', [])
    luc_pm = pairs.get('lucene-10.4 vs pizza-memory', [])
    
    luc_pe_has_issue = len(luc_pe) > 0
    luc_pm_has_issue = len(luc_pm) > 0
    
    if luc_pe_has_issue and not luc_pm_has_issue:
        pizza_mem_better += 1
    elif not luc_pe_has_issue and luc_pm_has_issue:
        pizza_eng_better += 1
    elif luc_pe_has_issue and luc_pm_has_issue:
        both_differ += 1
    else:
        neither_differ += 1

print(f"pizza-memory matches Lucene (engine-0.1 does not): {pizza_mem_better}")
print(f"pizza-engine-0.1 matches Lucene (memory does not): {pizza_eng_better}")
print(f"Both differ from Lucene: {both_differ}")
print(f"Neither differs from Lucene (issue is only between pizza variants): {neither_differ}")

# Now look at the hybrid issue
print("\n\n=== Hybrid-multi-core analysis ===")
# Check if hybrid matches lucene on any queries
hybrid_luc_issues = set()
hybrid_pizza_issues = set()
for key in issues:
    cmd, qnum = key
    if cmd != 'TOP_10':
        continue
    pairs = issues[key]['pairs']
    if 'pizza-hybrid-multi-core vs lucene-10.4' in pairs:
        hybrid_luc_issues.add(qnum)
    elif 'lucene-10.4 vs pizza-hybrid-multi-core' in pairs:
        hybrid_luc_issues.add(qnum)
    # Check hybrid vs any pizza
    for p in pairs:
        if 'pizza-hybrid-multi-core' in p and ('pizza-engine-0.1' in p or 'pizza-memory' in p):
            hybrid_pizza_issues.add(qnum)

print(f"Hybrid vs Lucene TOP_10 issues: {len(hybrid_luc_issues)} queries")
print(f"Hybrid vs other pizza TOP_10 issues: {len(hybrid_pizza_issues)} queries")

# For hybrid, show query type breakdown
print("\n=== Hybrid query type breakdown for TOP_10 ===")
hybrid_qt = {}
for key in issues:
    cmd, qnum = key
    if cmd != 'TOP_10':
        continue
    pairs = issues[key]['pairs']
    if 'pizza-hybrid-multi-core vs pizza-engine-0.1' in pairs:
        qt = issues[key]['qtags']
        hybrid_qt[qt] = hybrid_qt.get(qt, 0) + 1
for k, v in sorted(hybrid_qt.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

# Check: do queries that are problems for hybrid also show issues between
# non-hybrid engines and lucene?
print("\n=== Hybrid-only queries (no issues between other engines) ===")
hybrid_only = 0
hybrid_plus_others = 0
for key in issues:
    cmd, qnum = key
    if cmd != 'TOP_10':
        continue
    pairs = issues[key]['pairs']
    has_hybrid = any('pizza-hybrid-multi-core' in p for p in pairs)
    has_non_hybrid = any('pizza-hybrid-multi-core' not in p for p in pairs)
    if has_hybrid and not has_non_hybrid:
        hybrid_only += 1
    elif has_hybrid:
        hybrid_plus_others += 1
print(f"Queries with ONLY hybrid issues: {hybrid_only}")
print(f"Queries with hybrid + other issues: {hybrid_plus_others}")
