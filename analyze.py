#!/usr/bin/env python3
import json, os

engines = ['pizza-engine-0.1', 'tantivy-0.22']
rdir = 'results'

by_tag = {}
for mode in ['TOP_10', 'TOP_100', 'COUNT']:
    p_data = json.load(open(os.path.join(rdir, f'{engines[0]}#{mode}_results.json')))
    t_data = json.load(open(os.path.join(rdir, f'{engines[1]}#{mode}_results.json')))
    for p, t in zip(p_data, t_data):
        pd, td = p['duration'][0], t['duration'][0]
        for tag in ['term', 'union', 'intersection', 'phrase']:
            if tag in p['tags']:
                by_tag.setdefault((mode, tag), []).append((pd, td, p['query']))

print('===== MEDIAN COMPARISON (us) =====')
print(f'{"Mode":<12} {"Type":<15} {"Pizza Med":>10} {"Tantivy Med":>12} {"Ratio":>8} {"Pizza Wins":>12}')
print('-' * 75)
for (mode, tag), pairs in sorted(by_tag.items()):
    p_times = sorted([x[0] for x in pairs])
    t_times = sorted([x[1] for x in pairs])
    pm = p_times[len(p_times)//2]
    tm = t_times[len(t_times)//2]
    wins = sum(1 for pd, td, _ in pairs if pd < td)
    total = len(pairs)
    print(f'{mode:<12} {tag:<15} {pm:>10} {tm:>12} {pm/tm:>7.2f}x {wins}/{total}')

# Identify the pattern: intersection queries where pizza is slow
print()
print('===== INTERSECTION QUERIES WHERE PIZZA > 2x SLOWER (TOP_10) =====')
p_data = json.load(open(os.path.join(rdir, f'{engines[0]}#TOP_10_results.json')))
t_data = json.load(open(os.path.join(rdir, f'{engines[1]}#TOP_10_results.json')))

slow = []
for p, t in zip(p_data, t_data):
    if 'intersection' in p['tags']:
        pd, td = p['duration'][0], t['duration'][0]
        if pd > td * 1.5:
            slow.append((pd/td, pd, td, p['query']))

slow.sort(reverse=True)
print(f'{"Query":<58} {"Pizza":>8} {"Tantivy":>8} {"Ratio":>8}')
for ratio, pd, td, q in slow:
    print(f'{q:<58} {pd:>8} {td:>8} {ratio:>7.1f}x')

# Analyze what makes these queries slow - count common high-freq terms
print()
print('===== PATTERN ANALYSIS: What do slow intersection queries have in common? =====')
# Load COUNT to see term frequencies
count_data = {}
for row in json.load(open(os.path.join(rdir, f'{engines[0]}#COUNT_results.json'))):
    if 'term' in row['tags']:
        count_data[row['query']] = row['count']

print(f'{"Query":<58} {"Ratio":>7} {"Terms & approx doc freq":>30}')
for ratio, pd, td, q in slow:
    terms = q.replace('+', '').split()
    term_info = []
    for term in terms:
        cnt = count_data.get(term, '?')
        term_info.append(f'{term}({cnt})')
    print(f'{q:<58} {ratio:>6.1f}x  {" ".join(term_info)}')

# Now check: what about union queries for same terms?
print()
print('===== SAME QUERIES: INTERSECTION vs UNION performance (TOP_10) =====')
iq = {}
uq = {}
for p, t in zip(p_data, t_data):
    pd, td = p['duration'][0], t['duration'][0]
    # normalize query for matching
    base = p['query'].replace('+', '').replace('"', '').strip()
    base = ' '.join(base.split())
    if 'intersection' in p['tags']:
        iq[base] = (pd, td)
    elif 'union' in p['tags']:
        uq[base] = (pd, td)

print(f'{"Query":<45} {"P-AND":>7} {"T-AND":>7} {"AND-R":>7} {"P-OR":>7} {"T-OR":>7} {"OR-R":>7}')
for base in sorted(iq.keys()):
    if base in uq:
        ip, it = iq[base]
        up, ut = uq[base]
        ir = ip/it if it > 0 else 0
        ur = up/ut if ut > 0 else 0
        if ir > 1.5:  # only show slow ones
            print(f'{base:<45} {ip:>7} {it:>7} {ir:>6.1f}x {up:>7} {ut:>7} {ur:>6.1f}x')

# Count how many terms in slow queries  
print()
print('===== TERM COUNT DISTRIBUTION IN SLOW QUERIES =====')
from collections import Counter
term_counts = Counter()
for ratio, pd, td, q in slow:
    n = len(q.replace('+', '').split())
    term_counts[n] += 1
for n, c in sorted(term_counts.items()):
    print(f'  {n}-term queries: {c}')
