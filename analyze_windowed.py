#!/usr/bin/env python3
"""Analyze benchmark results: Pizza (results.json) vs Lucene (docs/results.json)."""

import json

with open('results.json') as f:
    pizza_data = json.load(f)
with open('docs/results.json') as f:
    lucene_data = json.load(f)

for mode in ['TOP_10', 'COUNT']:
    if mode not in pizza_data or mode not in lucene_data:
        print(f'Skipping {mode}: not in both files')
        continue
    pizza_list = pizza_data[mode].get('pizza-engine-0.1', [])
    lucene_list = lucene_data[mode].get('lucene-9.9.2-bp', [])

    lucene_by_query = {}
    for q in lucene_list:
        lucene_by_query[q['query']] = q

    wins = 0
    losses = 0
    total_p = 0
    total_l = 0
    by_type = {}
    worst_union = []
    worst_phrase = []
    worst_inter = []

    for q in pizza_list:
        q_name = q['query']
        p_us = min(q['duration']) if q['duration'] else 0

        if q_name not in lucene_by_query:
            continue
        l_q = lucene_by_query[q_name]
        l_us = min(l_q['duration']) if l_q['duration'] else 0

        total_p += p_us
        total_l += l_us

        if q_name.startswith('"'):
            qtype = 'phrase'
        elif q_name.startswith('+'):
            qtype = 'intersection'
        else:
            qtype = 'union'

        if qtype not in by_type:
            by_type[qtype] = {'wins': 0, 'losses': 0, 'p_sum': 0, 'l_sum': 0, 'count': 0}
        by_type[qtype]['count'] += 1
        by_type[qtype]['p_sum'] += p_us
        by_type[qtype]['l_sum'] += l_us

        if p_us <= l_us:
            wins += 1
            by_type[qtype]['wins'] += 1
        else:
            losses += 1
            by_type[qtype]['losses'] += 1
            ratio = p_us / l_us if l_us > 0 else 999
            entry = (q_name, p_us, l_us, ratio)
            if qtype == 'union':
                worst_union.append(entry)
            elif qtype == 'phrase':
                worst_phrase.append(entry)
            else:
                worst_inter.append(entry)

    total = wins + losses
    print(f'\n=== {mode} ===')
    print(f'Overall: {wins}/{total} wins ({100*wins/total:.1f}%), ratio {total_p/total_l:.3f}x')
    for qtype, info in sorted(by_type.items()):
        ratio = info['p_sum'] / info['l_sum'] if info['l_sum'] > 0 else 0
        tot = info['wins'] + info['losses']
        print(f'  {qtype:15s}: {info["wins"]}/{tot} wins ({100*info["wins"]/tot:.1f}%), '
              f'ratio {ratio:.3f}x')

    for label, worst in [('union', worst_union), ('phrase', worst_phrase), ('intersection', worst_inter)]:
        if worst:
            worst.sort(key=lambda x: -x[3])
            print(f'\n  Worst {label} losses:')
            for q_name, p_us, l_us, ratio in worst[:8]:
                print(f'    {ratio:.2f}x  {p_us:.0f} vs {l_us:.0f}  {q_name}')
