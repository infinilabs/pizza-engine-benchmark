import json, os
os.chdir('/Users/medcl/rust/search-benchmark-game')

# Merge new pizza results with Lucene/Tantivy from old results
with open('docs/results.json') as f:
    old = json.load(f)
with open('results.json') as f:
    new = json.load(f)

merged = {}
for cmd in ['COUNT', 'TOP_10', 'TOP_100']:
    merged[cmd] = {}
    for engine, d in old.get(cmd, {}).items():
        if 'pizza' not in engine:
            merged[cmd][engine] = d
    for engine, d in new.get(cmd, {}).items():
        merged[cmd][engine] = d

with open('results.json', 'w') as f:
    json.dump(merged, f, indent=2)

for cmd in ['COUNT', 'TOP_10', 'TOP_100']:
    pizza = {q['query']: q['duration'][0] if q['duration'] else 999999
             for q in merged[cmd]['pizza-engine-0.1']}

    best_other = {}
    for engine, queries in merged[cmd].items():
        if 'pizza' in engine:
            continue
        for q in queries:
            t = q['duration'][0] if q['duration'] else 999999
            if q['query'] not in best_other or t < best_other[q['query']][0]:
                best_other[q['query']] = (t, engine)

    wins, losses = 0, 0
    ratios = []
    loss_details = []
    for query in pizza:
        if query in best_other:
            pt = pizza[query]
            bt, be = best_other[query]
            ratio = pt / bt if bt > 0 else 999
            ratios.append(ratio)
            if pt <= bt:
                wins += 1
            else:
                losses += 1
                if ratio > 1.5:
                    loss_details.append((ratio, pt, bt, be, query))

    total = wins + losses
    ratios.sort()
    p50 = ratios[len(ratios)//2]
    avg = sum(ratios)/len(ratios)
    print(f'\n=== {cmd}: pizza-engine-0.1 wins {wins}/{total} ({100*wins/total:.1f}%) ===')
    print(f'Ratio (pizza/best_other): median={p50:.3f}x, avg={avg:.3f}x')

    loss_details.sort(reverse=True)
    n_show = 15 if cmd == 'COUNT' else 5
    if loss_details:
        print(f'Biggest losses (>1.5x, top {n_show}):')
        for ratio, pt, bt, be, q in loss_details[:n_show]:
            print(f'  {ratio:.2f}x  {pt:8d}us vs {bt:8d}us ({be:20s})  "{q}"')

    durations = sorted(pizza.values())
    med = durations[len(durations)//2]
    print(f'Median query time: {med}us')
