"""Cross-check correctness: compare Pizza results against Lucene for all commands."""
import json, sys, os

RESULTS_DIR = 'results'
COMMANDS = ['TOP_10', 'TOP_100', 'COUNT']
REFERENCE = 'lucene-9.9.2'
ENGINES = ['pizza-engine-0.1', 'tantivy-0.22', 'lucene-9.9.2-bp']

def load(engine, cmd):
    path = os.path.join(RESULTS_DIR, '%s#%s_results.json' % (engine, cmd))
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)

for cmd in COMMANDS:
    ref_data = load(REFERENCE, cmd)
    if not ref_data:
        print('SKIP %s: no reference data' % cmd)
        continue

    ref_dict = {}
    for d in ref_data:
        ref_dict[d['query']] = d

    for engine in ENGINES:
        eng_data = load(engine, cmd)
        if not eng_data:
            print('SKIP %s %s: no data' % (cmd, engine))
            continue

        mismatches = 0
        missing = 0
        details = []
        for d in eng_data:
            q = d['query']
            if q not in ref_dict:
                missing += 1
                continue
            rd = ref_dict[q]

            if cmd == 'COUNT':
                # Compare count values
                if d['count'] != rd['count']:
                    mismatches += 1
                    details.append('  COUNT mismatch: %r  %s=%d  ref=%d' % (q, engine, d['count'], rd['count']))
            else:
                # Compare top-K doc IDs (ignoring order for robustness)
                eng_docs = set(d.get('docs', []))
                ref_docs = set(rd.get('docs', []))
                if eng_docs != ref_docs:
                    mismatches += 1
                    only_eng = eng_docs - ref_docs
                    only_ref = ref_docs - eng_docs
                    detail = '  %s mismatch: %r' % (cmd, q)
                    if only_eng:
                        detail += '  only_%s=%s' % (engine, sorted(only_eng)[:5])
                    if only_ref:
                        detail += '  only_ref=%s' % sorted(only_ref)[:5]
                    detail += '  eng_n=%d ref_n=%d' % (len(eng_docs), len(ref_docs))
                    details.append(detail)

        status = 'OK' if mismatches == 0 else 'FAIL'
        print('%s %s vs %s: %d/%d queries, %d mismatches, %d missing' % (
            status, cmd, engine, len(eng_data), len(ref_data), mismatches, missing))
        for line in details[:10]:
            print(line)
