#!/usr/bin/env python3
import json, statistics

with open('docs/results.json') as f:
    ref_data = json.load(f)
with open('results/pizza-engine-0.1-bmw#TOP_10_results.json') as f:
    bmw_data = json.load(f)

lbp = [e['duration'][0] for e in ref_data['TOP_10']['lucene-9.9.2-bp'] if e['duration']]
lbp_sorted = sorted(lbp)
lbp_avg = statistics.mean(lbp)
lbp_med = statistics.median(lbp)
lbp_p99 = lbp_sorted[int(len(lbp_sorted)*0.99)]

bmw = [e['duration'][0] for e in bmw_data if e['duration']]
bmw_sorted = sorted(bmw)
bmw_avg = statistics.mean(bmw)
bmw_med = statistics.median(bmw)
bmw_p99 = bmw_sorted[int(len(bmw_sorted)*0.99)]

print('=== Comparison: pizza-engine BMW vs Lucene BP ===')
print(f'{"":12s} {"BMW":>12s} {"Lucene BP":>12s} {"Ratio":>12s} {"Target 0.8x":>12s}')
print(f'{"Avg:":12s} {bmw_avg:>12.1f} {lbp_avg:>12.1f} {bmw_avg/lbp_avg:>12.3f}x {lbp_avg*0.8:>12.1f}')
print(f'{"Median:":12s} {bmw_med:>12.1f} {lbp_med:>12.1f} {bmw_med/lbp_med:>12.3f}x {lbp_med*0.8:>12.1f}')
print(f'{"P99:":12s} {bmw_p99:>12.1f} {lbp_p99:>12.1f} {bmw_p99/lbp_p99:>12.3f}x {lbp_p99*0.8:>12.1f}')
print()

avg_ok = bmw_avg <= lbp_avg * 0.8
med_ok = bmw_med <= lbp_med * 0.8
p99_ok = bmw_p99 <= lbp_p99 * 0.8
print(f'Target 0.8x Lucene BP:')
print(f'  Avg:    {"PASS" if avg_ok else "FAIL"} ({bmw_avg:.1f} vs {lbp_avg*0.8:.1f})')
print(f'  Median: {"PASS" if med_ok else "FAIL"} ({bmw_med:.1f} vs {lbp_med*0.8:.1f})')
print(f'  P99:    {"PASS" if p99_ok else "FAIL"} ({bmw_p99:.1f} vs {lbp_p99*0.8:.1f})')
