#!/usr/bin/env python3
import json

with open('results_before_wand.json') as f:
    before = json.load(f)
with open('results.json') as f:
    after = json.load(f)

for cmd in ['TOP_10', 'TOP_100', 'COUNT']:
    old = before.get(cmd, {}).get('pizza-engine-0.1', [])
    new = after.get(cmd, {}).get('pizza-engine-0.1', [])
    if not old or not new:
        print(f'{cmd}: missing data')
        continue

    old_by_q = {r['query']: r for r in old}
    new_by_q = {r['query']: r for r in new}

    common = set(old_by_q.keys()) & set(new_by_q.keys())

    old_times = []
    new_times = []
    improvements = []

    for q in sorted(common):
        o = old_by_q[q]
        n = new_by_q[q]
        od = o['duration']
        nd = n['duration']
        if od and nd:
            omedian = od[len(od)//2]
            nmedian = nd[len(nd)//2]
            old_times.append(omedian)
            new_times.append(nmedian)
            if omedian > 100:
                improvements.append((q, omedian, nmedian, omedian/nmedian if nmedian > 0 else float('inf')))

    total_old = sum(old_times)
    total_new = sum(new_times)

    print(f'=== {cmd} ===')
    print(f'  Queries: {len(common)}')
    print(f'  Total latency (before): {total_old:>12,} us')
    print(f'  Total latency (after):  {total_new:>12,} us')
    if total_new > 0:
        print(f'  Overall speedup:        {total_old/total_new:.2f}x')

    improvements.sort(key=lambda x: -x[3])
    print(f'  Top 10 most improved:')
    for q, old_us, new_us, ratio in improvements[:10]:
        print(f'    {ratio:6.1f}x  {old_us:>8}us -> {new_us:>8}us  {q[:60]}')

    regressions = [x for x in improvements if x[3] < 0.9]
    if regressions:
        regressions.sort(key=lambda x: x[3])
        print(f'  Regressions (>10% slower):')
        for q, old_us, new_us, ratio in regressions[:5]:
            print(f'    {ratio:6.2f}x  {old_us:>8}us -> {new_us:>8}us  {q[:60]}')
    print()

# Also compare with Lucene BP if available
for cmd in ['TOP_10', 'TOP_100']:
    lucene = before.get(cmd, {}).get('lucene-9.9.2-bp', [])
    pizza_new = after.get(cmd, {}).get('pizza-engine-0.1', [])
    if not lucene or not pizza_new:
        continue

    lucene_by_q = {r['query']: r for r in lucene}
    pizza_by_q = {r['query']: r for r in pizza_new}
    common = set(lucene_by_q.keys()) & set(pizza_by_q.keys())

    lucene_total = 0
    pizza_total = 0
    for q in common:
        ld = lucene_by_q[q]['duration']
        pd = pizza_by_q[q]['duration']
        if ld and pd:
            lucene_total += ld[len(ld)//2]
            pizza_total += pd[len(pd)//2]

    print(f'=== {cmd}: Pizza vs Lucene-BP ===')
    print(f'  Lucene-BP total: {lucene_total:>12,} us')
    print(f'  Pizza total:     {pizza_total:>12,} us')
    if lucene_total > 0:
        print(f'  Pizza / Lucene:  {pizza_total/lucene_total:.2f}x')
    print()
