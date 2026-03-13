#!/usr/bin/env python3
import json, os

engines = ['pizza-memory', 'pizza-memory-multi-core', 'pizza-engine-0.1']
commands = ['TOP_10', 'TOP_100', 'COUNT']

def load_results(eng, cmd):
    f = f'results/{eng}#{cmd}_results.json'
    if not os.path.exists(f):
        return {}
    with open(f) as fh:
        items = json.load(fh)
    out = {}
    for item in items:
        q = item['query']
        durations = sorted(item['duration'])
        out[q] = durations[len(durations) // 2]
    return out

for cmd in commands:
    data = {}
    for eng in engines:
        r = load_results(eng, cmd)
        if r:
            data[eng] = r
    if 'pizza-memory' not in data or 'pizza-memory-multi-core' not in data:
        continue
    print(f'\n===== {cmd} =====')
    queries = list(data['pizza-memory'].keys())
    t1_total = 0
    t2_total = 0
    w1 = 0
    w2 = 0
    n = 0
    ratios = []
    for q in queries:
        if q not in data['pizza-memory-multi-core']:
            continue
        a = data['pizza-memory'][q]
        b = data['pizza-memory-multi-core'][q]
        n += 1
        t1_total += a
        t2_total += b
        if a < b:
            w1 += 1
        elif b < a:
            w2 += 1
        if b > 0:
            ratios.append((a / b, q, a, b))
    print(f'  Queries: {n}')
    print(f'  pizza-memory:            total={t1_total}us  wins={w1}')
    print(f'  pizza-memory-multi-core: total={t2_total}us  wins={w2}')
    sp = t1_total / t2_total if t2_total > 0 else 0
    print(f'  => multi-core speedup: {sp:.2f}x')
    ratios.sort(key=lambda x: x[0], reverse=True)
    print(f'  Best 10 (multi-core helped):')
    for r, q, a, b in ratios[:10]:
        print(f'    {r:.2f}x  {q[:50]:50s}  {a}us -> {b}us')
    ratios.sort(key=lambda x: x[0])
    print(f'  Worst 10 (multi-core hurt):')
    for r, q, a, b in ratios[:10]:
        print(f'    {r:.2f}x  {q[:50]:50s}  {a}us -> {b}us')

print('\n===== vs pizza-engine-0.1 =====')
for cmd in commands:
    mc = load_results('pizza-memory-multi-core', cmd)
    pe = load_results('pizza-engine-0.1', cmd)
    if not mc or not pe:
        continue
    t_mc = 0
    t_pe = 0
    w_mc = 0
    w_pe = 0
    n = 0
    for q in pe:
        if q not in mc:
            continue
        n += 1
        t_mc += mc[q]
        t_pe += pe[q]
        if mc[q] < pe[q]:
            w_mc += 1
        elif pe[q] < mc[q]:
            w_pe += 1
    ratio = t_pe / t_mc if t_mc > 0 else 0
    print(f'  {cmd}: {n}q  mc={t_mc}us({w_mc}w)  eng={t_pe}us({w_pe}w)  ratio={ratio:.2f}x')
