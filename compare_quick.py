#!/usr/bin/env python3
import json, os
from collections import defaultdict

engines = {'pizza': 'pizza-engine-0.1', 'lucene': 'lucene-9.9.2-bp'}
modes = ['COUNT', 'TOP_10', 'TOP_100']

for mode in modes:
    results = {}
    for name, eng in engines.items():
        path = f'results/{eng}#{mode}_results.json'
        if not os.path.exists(path):
            continue
        with open(path) as f:
            data = json.load(f)
        by_type = defaultdict(list)
        for q in data:
            tags = q['tags']
            qt = tags[0] if tags else 'unknown'
            med = sorted(q['duration'])[len(q['duration'])//2]
            by_type[qt].append(med)
        results[name] = {qt: sorted(vals)[len(vals)//2] for qt, vals in by_type.items()}

    if len(results) < 2:
        continue
    print(f'\n=== {mode} ===')
    all_types = sorted(set().union(*(r.keys() for r in results.values())))
    for qt in all_types:
        p = results.get('pizza', {}).get(qt, 0)
        l = results.get('lucene', {}).get(qt, 0)
        ratio = p/l if l else 0
        mark = 'WIN' if ratio <= 1.0 else 'LOSE'
        print(f'  {qt:15s}  pizza={p:7.0f}  lucene={l:7.0f}  ratio={ratio:.2f}x  {mark}')
