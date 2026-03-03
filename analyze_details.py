#!/usr/bin/env python3
"""Deep analysis of benchmark weaknesses for optimization planning."""
import json

with open('results.json') as f:
    data = json.load(f)
with open('docs/results.json') as f:
    lucene_data = json.load(f)

stopwords = {'the', 'of', 'in', 'a', 'to', 'and', 'is', 'on', 'for', 'at', 'by', 'an', 'or', 'as', 'it'}

for mode in ['TOP_10', 'COUNT']:
    pizza_list = data[mode].get('pizza-engine-0.1', [])
    lucene_list = lucene_data[mode].get('lucene-9.9.2-bp', [])
    lmap = {q['query']: min(q['duration']) for q in lucene_list if q['duration']}

    print(f'\n=== {mode} ===')
    for qtype in ['union', 'intersection', 'phrase']:
        sw_ratios = []
        nosw_ratios = []
        all_ratios = []
        for q in pizza_list:
            qn = q['query']
            if qtype == 'union' and (qn.startswith('+') or qn.startswith('"')):
                continue
            if qtype == 'intersection' and (not qn.startswith('+') or '"' in qn):
                continue
            if qtype == 'phrase' and not qn.startswith('"'):
                continue
            if qn not in lmap:
                continue
            pt = min(q['duration'])
            lt = lmap[qn]
            if lt == 0:
                continue
            ratio = pt / lt

            if qtype == 'intersection':
                terms = [t.strip('+') for t in qn.split()]
            elif qtype == 'phrase':
                terms = qn.strip('"').split()
            else:
                terms = qn.split()

            has_sw = any(t.lower() in stopwords for t in terms)
            all_ratios.append(ratio)
            if has_sw:
                sw_ratios.append((ratio, pt, lt, qn))
            else:
                nosw_ratios.append((ratio, pt, lt, qn))

        all_ratios.sort()
        n = len(all_ratios)
        if n == 0:
            continue
        avg = sum(all_ratios) / n
        wins = sum(1 for r in all_ratios if r < 1.0)
        print(f'\n  {qtype} ({n} queries): avg {avg:.3f}x, {wins}/{n} wins')
        print(f'    p50={all_ratios[n//2]:.3f}x  p90={all_ratios[int(n*0.9)]:.3f}x  p95={all_ratios[int(n*0.95)]:.3f}x  p99={all_ratios[int(n*0.99)]:.3f}x  max={all_ratios[-1]:.3f}x')

        sw_avg = sum(r for r,_,_,_ in sw_ratios) / len(sw_ratios) if sw_ratios else 0
        nosw_avg = sum(r for r,_,_,_ in nosw_ratios) / len(nosw_ratios) if nosw_ratios else 0
        sw_wins = sum(1 for r,_,_,_ in sw_ratios if r < 1.0)
        nosw_wins = sum(1 for r,_,_,_ in nosw_ratios if r < 1.0)
        print(f'    With stopwords: {len(sw_ratios)} queries, avg {sw_avg:.3f}x, {sw_wins}/{len(sw_ratios)} wins')
        print(f'    No stopwords:   {len(nosw_ratios)} queries, avg {nosw_avg:.3f}x, {nosw_wins}/{len(nosw_ratios)} wins')

        two_term = [r for r,_,_,q in sw_ratios + nosw_ratios if len(q.split()) == 2]
        multi_term = [r for r,_,_,q in sw_ratios + nosw_ratios if len(q.split()) > 2]
        if two_term:
            print(f'    2-term: {len(two_term)} queries, avg {sum(two_term)/len(two_term):.3f}x')
        if multi_term:
            print(f'    3+ term: {len(multi_term)} queries, avg {sum(multi_term)/len(multi_term):.3f}x')

print('\n\n=== TIME BUDGET ANALYSIS ===')
for mode in ['TOP_10', 'COUNT']:
    pizza_list = data[mode].get('pizza-engine-0.1', [])
    lucene_list = lucene_data[mode].get('lucene-9.9.2-bp', [])
    lmap = {q['query']: min(q['duration']) for q in lucene_list if q['duration']}

    total_pizza = 0
    total_lucene = 0
    loss_pizza = 0
    loss_lucene = 0
    for q in pizza_list:
        qn = q['query']
        if qn not in lmap:
            continue
        pt = min(q['duration'])
        lt = lmap[qn]
        total_pizza += pt
        total_lucene += lt
        if pt > lt:
            loss_pizza += pt
            loss_lucene += lt

    print(f'\n  {mode}: total pizza={total_pizza}us, lucene={total_lucene}us')
    savings = loss_pizza - loss_lucene
    print(f'  Time spent on losses: pizza={loss_pizza}us, lucene={loss_lucene}us, gap={savings}us')
    print(f'  If we matched Lucene on ALL losses, ratio would be: {(total_pizza - savings)/total_lucene:.3f}x')

print('\n\n=== PER-TYPE TIME BUDGET ===')
for mode in ['TOP_10', 'COUNT']:
    pizza_list = data[mode].get('pizza-engine-0.1', [])
    lucene_list = lucene_data[mode].get('lucene-9.9.2-bp', [])
    lmap = {q['query']: min(q['duration']) for q in lucene_list if q['duration']}

    print(f'\n  {mode}:')
    for qtype in ['union', 'intersection', 'phrase']:
        total_p = 0
        total_l = 0
        gap = 0
        for q in pizza_list:
            qn = q['query']
            if qtype == 'union' and (qn.startswith('+') or qn.startswith('"')):
                continue
            if qtype == 'intersection' and (not qn.startswith('+') or '"' in qn):
                continue
            if qtype == 'phrase' and not qn.startswith('"'):
                continue
            if qn not in lmap:
                continue
            pt = min(q['duration'])
            lt = lmap[qn]
            total_p += pt
            total_l += lt
            if pt > lt:
                gap += pt - lt
        if total_l > 0:
            print(f'    {qtype:15s}: pizza={total_p:>8}us  lucene={total_l:>8}us  ratio={total_p/total_l:.3f}x  loss_gap={gap:>6}us')
