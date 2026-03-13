#!/usr/bin/env python3
import json

def load(path):
    with open(path) as f:
        data = json.load(f)
    d = {}
    for entry in data:
        d[entry['query']] = min(entry['duration'])
    return d

def compare(a, b):
    w = l = t = 0
    for q in a:
        if q in b:
            av, bv = a[q], b[q]
            if av < bv: w += 1
            elif av > bv: l += 1
            else: t += 1
    return w, l, t

for cmd in ['TOP_10', 'TOP_100', 'COUNT']:
    try:
        store_opt = load(f'results/pizza-opt-latency#{cmd}_results.json')
        lucene = load(f'results/lucene-10.4-bp#{cmd}_results.json')
        engine01 = load(f'results/pizza-engine-0.1#{cmd}_results.json')
    except FileNotFoundError as e:
        print(f'{cmd}: missing file: {e}')
        continue

    w, l, t = compare(store_opt, lucene)
    total = w + l + t
    print(f'{cmd:8s} vs lucene  : V9 {w}/{total} ({100*w/total:.1f}%) | lucene {l}/{total} ({100*l/total:.1f}%) | ties {t}')

    w2, l2, t2 = compare(store_opt, engine01)
    total2 = w2 + l2 + t2
    print(f'{cmd:8s} vs V8-flat : V9 {w2}/{total2} ({100*w2/total2:.1f}%) | V8 {l2}/{total2} ({100*l2/total2:.1f}%) | ties {t2}')
    print()
