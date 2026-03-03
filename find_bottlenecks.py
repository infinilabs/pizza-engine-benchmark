"""Find bottleneck queries where Pizza is slowest relative to LuceneBP."""
import json, os

RESULTS_DIR = 'results'

def load(engine, cmd):
    path = os.path.join(RESULTS_DIR, '%s#%s_results.json' % (engine, cmd))
    with open(path) as f:
        return json.load(f)

def categorize(q):
    q = q.strip()
    if q.startswith('+'):
        if '"' in q:
            return 'intersection+phrase'
        return 'intersection'
    if '"' in q:
        return 'phrase'
    if ' ' in q:
        return 'union'
    return 'single_term'

for cmd in ['TOP_10', 'TOP_100', 'COUNT']:
    pizza = load('pizza-engine-0.1', cmd)
    bp = load('lucene-9.9.2-bp', cmd)
    luc = load('lucene-9.9.2', cmd)

    bp_dict = {d['query']: min(d['duration']) for d in bp}
    luc_dict = {d['query']: min(d['duration']) for d in luc}

    rows = []
    for d in pizza:
        q = d['query']
        pt = min(d['duration'])
        bt = bp_dict.get(q, 999999)
        lt = luc_dict.get(q, 999999)
        cat = categorize(q)
        ratio = pt / bt if bt > 0 else 999
        rows.append((q, pt, bt, lt, cat, ratio))

    # Sort by absolute time descending (biggest bottlenecks)
    rows.sort(key=lambda x: -x[1])

    print('\n=== %s: Top 15 slowest Pizza queries ===' % cmd)
    print('%10s %10s %10s %6s %-15s  %s' % ('Pizza', 'BP', 'Lucene', 'P/BP', 'Category', 'Query'))
    for q, pt, bt, lt, cat, ratio in rows[:15]:
        print('%10d %10d %10d %6.2f %-15s  %s' % (pt, bt, lt, ratio, cat, q))

    # Sort by P/BP ratio (where Pizza is worst relative to BP)
    rows_slow = [r for r in rows if r[1] > 100]  # skip trivial
    rows_slow.sort(key=lambda x: -x[5])

    print('\n=== %s: Top 15 worst P/BP ratio ===' % cmd)
    print('%10s %10s %10s %6s %-15s  %s' % ('Pizza', 'BP', 'Lucene', 'P/BP', 'Category', 'Query'))
    for q, pt, bt, lt, cat, ratio in rows_slow[:15]:
        print('%10d %10d %10d %6.2f %-15s  %s' % (pt, bt, lt, ratio, cat, q))
