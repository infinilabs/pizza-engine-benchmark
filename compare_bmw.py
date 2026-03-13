#!/usr/bin/env python3
"""Compare new pizza results with old baseline."""
import json, os

os.chdir('/Users/medcl/rust/search-benchmark-game')

# Load old baseline
with open('results_before_bmw.json') as f:
    old = json.load(f)

# Load new results from individual files
new = {}
for mode in ['COUNT', 'TOP_10', 'TOP_100']:
    fname = f'results/pizza-engine-0.1#{mode}_results.json'
    with open(fname) as f:
        raw = json.load(f)
    new[mode] = raw

for mode in ['TOP_10', 'TOP_100', 'COUNT']:
    old_pe = {q['query']: q for q in old[mode].get('pizza-engine-0.1', [])}
    new_pe = {q['query']: q for q in new[mode]}
    
    improvements = []
    regressions = []
    for qname in old_pe:
        if qname not in new_pe:
            continue
        old_t = old_pe[qname]['duration'][0] if old_pe[qname]['duration'] else 0
        new_t = new_pe[qname]['duration'][0] if new_pe[qname]['duration'] else 0
        if old_t > 0 and new_t > 0:
            ratio = new_t / old_t
            if ratio < 0.9:
                improvements.append((ratio, qname, old_t, new_t))
            elif ratio > 1.1:
                regressions.append((ratio, qname, old_t, new_t))
    
    improvements.sort()
    regressions.sort(reverse=True)
    
    # Compute overall stats
    all_ratios = []
    for qname in old_pe:
        if qname not in new_pe:
            continue
        old_t = old_pe[qname]['duration'][0] if old_pe[qname]['duration'] else 0
        new_t = new_pe[qname]['duration'][0] if new_pe[qname]['duration'] else 0
        if old_t > 0 and new_t > 0:
            all_ratios.append(new_t / old_t)
    all_ratios.sort()
    
    avg_sum_old = sum(old_pe[q]['duration'][0] for q in old_pe if old_pe[q]['duration'] and q in new_pe)
    avg_sum_new = sum(new_pe[q]['duration'][0] for q in new_pe if new_pe[q]['duration'] and q in old_pe)
    
    median = all_ratios[len(all_ratios)//2] if all_ratios else 0
    p10 = all_ratios[int(len(all_ratios)*0.1)] if all_ratios else 0
    p90 = all_ratios[int(len(all_ratios)*0.9)] if all_ratios else 0
    
    print(f"\n{'='*60}")
    print(f"  {mode}: median new/old = {median:.3f}x, sum_old={avg_sum_old}µs, sum_new={avg_sum_new}µs ({avg_sum_new/avg_sum_old:.2f}x)")
    print(f"  p10={p10:.3f}x  p90={p90:.3f}x")
    print(f"  Improvements (>10% faster): {len(improvements)}")
    print(f"  Regressions (>10% slower): {len(regressions)}")
    
    if improvements:
        print(f"\n  Top improvements:")
        for ratio, q, old_t, new_t in improvements[:15]:
            print(f"    {ratio:.3f}x  old={old_t:7d}µs  new={new_t:7d}µs  \"{q}\"")
    
    if regressions:
        print(f"\n  Top regressions:")
        for ratio, q, old_t, new_t in regressions[:15]:
            print(f"    {ratio:.3f}x  old={old_t:7d}µs  new={new_t:7d}µs  \"{q}\"")

    # Compare against lucene-10.4-bp
    lbp = {q['query']: q for q in old[mode].get('lucene-10.4-bp', [])}
    old_losses = sum(1 for q in old_pe if q in lbp and old_pe[q]['duration'] and lbp[q]['duration']
                     and lbp[q]['duration'][0] > 0 and old_pe[q]['duration'][0] / lbp[q]['duration'][0] > 1.5)
    new_losses = sum(1 for q in new_pe if q in lbp and new_pe[q]['duration'] and lbp[q]['duration']
                     and lbp[q]['duration'][0] > 0 and new_pe[q]['duration'][0] / lbp[q]['duration'][0] > 1.5)
    print(f"\n  vs lucene-10.4-bp: old_losses>1.5x={old_losses}, new_losses>1.5x={new_losses}")
