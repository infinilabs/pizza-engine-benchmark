#!/usr/bin/env python3
"""Identify the slowest queries in Pizza V8+PFOR benchmark."""
import json

results = json.load(open('results.json'))
for mode in ['TOP_10', 'TOP_100', 'COUNT']:
    if mode not in results:
        continue
    pizza = results[mode].get('pizza-engine-0.1', [])
    lucene = results[mode].get('lucene-9.9.2-bp', [])
    lucene_map = {q['query']: q for q in lucene}

    ranked = sorted(pizza, key=lambda q: q['duration'][0] if q['duration'] else 0, reverse=True)
    print(f'\n=== {mode} -- TOP 25 SLOWEST QUERIES (Pizza V8+PFOR) ===')
    print(f'{"Query":<55} {"Pizza(us)":>10} {"Lucene":>10} {"Ratio":>8} {"Type":>12}')
    print('-' * 100)
    for q in ranked[:25]:
        dur = q['duration'][0] if q['duration'] else 0
        lq = lucene_map.get(q['query'], {})
        ldur = lq.get('duration', [0])[0] if lq.get('duration') else 0
        ratio = f'{dur/ldur:.1f}x' if ldur > 0 else 'N/A'
        if q['query'].startswith('"'):
            qtype = 'phrase'
        elif q['query'].startswith('+'):
            qtype = 'intersection'
        elif ' ' in q['query']:
            qtype = 'union'
        else:
            qtype = 'term'
        print(f'{q["query"][:54]:<55} {dur:>10} {ldur:>10} {ratio:>8} {qtype:>12}')

# Summary: where Pizza LOSES to Lucene
print('\n\n=== QUERIES WHERE PIZZA IS SLOWER THAN LUCENE ===')
for mode in ['TOP_10', 'TOP_100']:
    if mode not in results:
        continue
    pizza = results[mode].get('pizza-engine-0.1', [])
    lucene = results[mode].get('lucene-9.9.2-bp', [])
    lucene_map = {q['query']: q for q in lucene}
    
    losses = []
    for q in pizza:
        dur = q['duration'][0] if q['duration'] else 0
        lq = lucene_map.get(q['query'], {})
        ldur = lq.get('duration', [0])[0] if lq.get('duration') else 0
        if ldur > 0 and dur > ldur:
            ratio = dur / ldur
            if q['query'].startswith('"'):
                qtype = 'phrase'
            elif q['query'].startswith('+'):
                qtype = 'intersection'
            elif ' ' in q['query']:
                qtype = 'union'
            else:
                qtype = 'term'
            losses.append((q['query'], dur, ldur, ratio, qtype))
    
    losses.sort(key=lambda x: x[3], reverse=True)
    print(f'\n--- {mode}: {len(losses)} queries slower than Lucene ---')
    print(f'{"Query":<55} {"Pizza(us)":>10} {"Lucene":>10} {"Ratio":>8} {"Type":>12}')
    print('-' * 100)
    for query, dur, ldur, ratio, qtype in losses[:30]:
        print(f'{query[:54]:<55} {dur:>10} {ldur:>10} {ratio:>5.1f}x {qtype:>12}')

# Overall stats
print('\n\n=== OVERALL STATISTICS ===')
for mode in ['TOP_10', 'TOP_100']:
    if mode not in results:
        continue
    pizza = results[mode].get('pizza-engine-0.1', [])
    lucene = results[mode].get('lucene-9.9.2-bp', [])
    lucene_map = {q['query']: q for q in lucene}
    
    wins = 0
    losses = 0
    total = 0
    pizza_total = 0
    lucene_total = 0
    for q in pizza:
        dur = q['duration'][0] if q['duration'] else 0
        lq = lucene_map.get(q['query'], {})
        ldur = lq.get('duration', [0])[0] if lq.get('duration') else 0
        if ldur > 0:
            total += 1
            pizza_total += dur
            lucene_total += ldur
            if dur < ldur:
                wins += 1
            else:
                losses += 1
    
    print(f'{mode}: Pizza wins {wins}/{total} ({100*wins/total:.1f}%), '
          f'total Pizza={pizza_total/1000:.0f}ms, Lucene={lucene_total/1000:.0f}ms, '
          f'ratio={pizza_total/lucene_total:.2f}x')
