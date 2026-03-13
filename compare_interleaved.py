#!/usr/bin/env python3
import json

old = json.load(open('results_before_interleaved.json'))
new = json.load(open('results.json'))

for mode in ['TOP_10', 'TOP_100', 'COUNT']:
    old_d = {r['query']: r['duration'][0] for r in old[mode]['pizza-engine-0.1']}
    new_d = {r['query']: r['duration'][0] for r in new[mode]['pizza-engine-0.1']}
    common = set(old_d) & set(new_d)
    faster = sum(1 for q in common if new_d[q] < old_d[q])
    slower = sum(1 for q in common if new_d[q] > old_d[q])
    same = sum(1 for q in common if new_d[q] == old_d[q])
    total_old = sum(old_d[q] for q in common)
    total_new = sum(new_d[q] for q in common)
    pct = (total_old - total_new) / total_old * 100 if total_old else 0
    print(f'{mode}: {len(common)} queries, {faster} faster, {slower} slower, {same} same')
    print(f'  Total: {total_old/1000:.0f}ms -> {total_new/1000:.0f}ms ({pct:+.1f}%)')

    # Show biggest improvements and regressions
    diffs = [(q, old_d[q], new_d[q], new_d[q] - old_d[q]) for q in common if old_d[q] > 0]
    diffs.sort(key=lambda x: x[3])
    print(f'  Top 5 improvements:')
    for q, o, n, d in diffs[:5]:
        print(f'    {q}: {o} -> {n} ({d:+d}us)')
    print(f'  Top 5 regressions:')
    for q, o, n, d in diffs[-5:]:
        print(f'    {q}: {o} -> {n} ({d:+d}us)')
    print()

# Also compare vs lucene-bp
print("=" * 60)
print("Win rates vs lucene-10.4-bp:")
for mode in ['TOP_10', 'TOP_100', 'COUNT']:
    lucene_data = new[mode].get('lucene-10.4-bp', [])
    pizza_data = new[mode].get('pizza-engine-0.1', [])
    if not lucene_data or not pizza_data:
        print(f"  {mode}: no data for both engines")
        continue
    lucene_d = {r['query']: r['duration'][0] for r in lucene_data}
    pizza_d = {r['query']: r['duration'][0] for r in pizza_data}
    common = set(lucene_d) & set(pizza_d)
    wins = sum(1 for q in common if pizza_d[q] < lucene_d[q])
    losses = sum(1 for q in common if pizza_d[q] > lucene_d[q])
    ties = sum(1 for q in common if pizza_d[q] == lucene_d[q])
    print(f"  {mode}: {wins}W/{losses}L/{ties}T out of {len(common)} ({wins/len(common)*100:.1f}% win rate)")
