#!/usr/bin/env python3
"""Check baseline results and corpus assumptions."""
import json

with open('docs/results.json') as f:
    data = json.load(f)

print('Commands:', list(data.keys()))

for cmd in data.keys():
    print(f'\n=== {cmd} ===')
    for engine in data[cmd]:
        entries = data[cmd][engine]
        counts = [e['count'] for e in entries]
        print(f'  {engine}: {len(entries)} queries, count range={min(counts)}-{max(counts)}, avg_count={sum(counts)/len(counts):.0f}')
        # Show first 3
        for e in entries[:3]:
            dur = e['duration'][0] if e['duration'] else 0
            print(f'    q={e["query"]!r} count={e["count"]} dur={dur}us tags={e["tags"]}')

# Now check our BMW results
print('\n=== BMW Results ===')
try:
    with open('results/pizza-engine-0.1-bmw#TOP_10_results.json') as f:
        bmw = json.load(f)
    bmw_counts = [e['count'] for e in bmw]
    print(f'  BMW TOP_10: {len(bmw)} queries, count range={min(bmw_counts)}-{max(bmw_counts)}')
    for e in bmw[:5]:
        dur = e['duration'][0] if e['duration'] else 0
        print(f'    q={e["query"]!r} count={e["count"]} dur={dur}us')
    
    # Compare counts with Lucene BP
    lbp = data['TOP_10']['lucene-9.9.2-bp']
    lbp_by_query = {e['query']: e['count'] for e in lbp}
    bmw_by_query = {e['query']: e['count'] for e in bmw}
    
    mismatches = 0
    for q in lbp_by_query:
        if q in bmw_by_query:
            lc = lbp_by_query[q]
            bc = bmw_by_query[q]
            if lc != bc:
                mismatches += 1
                if mismatches <= 10:
                    print(f'  MISMATCH: q={q!r} lucene={lc} bmw={bc}')
    print(f'  Total mismatches: {mismatches}/{len(lbp_by_query)}')
except FileNotFoundError:
    print('  No BMW results found')

# Check tantivy counts for comparison
print('\n=== Tantivy vs Lucene BP count comparison ===')
if 'TOP_10' in data:
    lbp = data['TOP_10']['lucene-9.9.2-bp']
    tan = data['TOP_10'].get('tantivy-0.22', [])
    if tan:
        lbp_by_q = {e['query']: e['count'] for e in lbp}
        tan_by_q = {e['query']: e['count'] for e in tan}
        mm = 0
        for q in lbp_by_q:
            if q in tan_by_q and lbp_by_q[q] != tan_by_q[q]:
                mm += 1
                if mm <= 5:
                    print(f'  MISMATCH: q={q!r} lucene={lbp_by_q[q]} tantivy={tan_by_q[q]}')
        print(f'  Tantivy vs Lucene mismatches: {mm}/{len(lbp_by_q)}')
