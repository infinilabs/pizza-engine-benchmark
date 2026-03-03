#!/usr/bin/env python3
import re

report = open('cross_check_report.txt').read()

# Parse per-query blocks
blocks = re.split(r'\n(?=\[TOP_)', report)

# Count results by query type for pizza vs lucene
for cmd in ['TOP_10', 'TOP_100']:
    for qtype in ['phrase', 'intersection', 'union']:
        perfect = 0
        sameset = 0
        diff = 0
        total = 0
        for block in blocks:
            if not block.startswith(f'[{cmd}]'):
                continue
            if f'phrase,phrase' not in block and qtype == 'phrase':
                continue
            if f'intersection:' in block and qtype == 'intersection':
                pass
            elif f'phrase,phrase' in block and qtype == 'phrase':
                pass
            elif qtype == 'union' and 'union:' in block:
                pass
            else:
                continue
            
            for line in block.split('\n'):
                if 'lucene' in line and 'pizza' in line:
                    total += 1
                    if 'same doc order but' in line:
                        perfect += 1
                    elif 'same doc set but different order' in line:
                        sameset += 1
                    elif 'common' in line:
                        diff += 1
        
        if total > 0:
            print(f'{cmd} {qtype}: Perfect={perfect}, SameSet={sameset}, Diff={diff}, Total={total}')

# Also count pizza vs tantivy for phrases
print("\n--- Pizza vs Tantivy (phrase queries) ---")
for cmd in ['TOP_10', 'TOP_100']:
    perfect = 0
    sameset = 0  
    diff = 0
    total = 0
    for block in blocks:
        if not block.startswith(f'[{cmd}]'):
            continue
        if 'phrase,phrase' not in block:
            continue
        for line in block.split('\n'):
            if 'tantivy' in line and 'pizza' in line:
                total += 1
                if 'same doc order but' in line:
                    perfect += 1
                elif 'same doc set but different order' in line:
                    sameset += 1
                elif 'common' in line:
                    diff += 1
    if total > 0:
        print(f'{cmd} phrase: Perfect={perfect}, SameSet={sameset}, Diff={diff}, Total={total}')

# Lucene vs Tantivy for reference
print("\n--- Lucene vs Tantivy (phrase queries) ---")
for cmd in ['TOP_10', 'TOP_100']:
    perfect = 0
    sameset = 0
    diff = 0
    total = 0
    for block in blocks:
        if not block.startswith(f'[{cmd}]'):
            continue
        if 'phrase,phrase' not in block:
            continue
        for line in block.split('\n'):
            if 'lucene' in line and 'tantivy' in line and 'pizza' not in line:
                total += 1
                if 'same doc order but' in line:
                    perfect += 1
                elif 'same doc set but different order' in line:
                    sameset += 1
                elif 'common' in line:
                    diff += 1
    if total > 0:
        print(f'{cmd} phrase: Perfect={perfect}, SameSet={sameset}, Diff={diff}, Total={total}')
