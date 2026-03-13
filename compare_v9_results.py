#!/usr/bin/env python3
import json, os

engines = ['pizza-engine-0.1', 'pizza-opt-latency']
commands = ['TOP_10', 'TOP_100', 'COUNT']

print('=== V9 vs V8 baseline ===')
for cmd in commands:
    print(f'--- {cmd} ---')
    for engine in engines:
        path = f'results/{engine}#{cmd}_results.json'
        if not os.path.exists(path):
            print(f'  {engine:25s} (no results)')
            continue
        with open(path) as f:
            data = json.load(f)
        times = [d['duration'][0] for d in data]
        total = len(times)
        avg = sum(times) / total
        st = sorted(times)
        p50 = st[int(total * 0.5)]
        p99 = st[int(total * 0.99)]
        print(f'  {engine:25s} avg={avg:7.0f}us  p50={p50:6d}us  p99={p99:6d}us')
    print()
