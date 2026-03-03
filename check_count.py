import json

pf = open('results/pizza-engine-0.1#COUNT_results.json')
pizza = json.load(pf)
pf.close()

lf = open('results/lucene-9.9.2#COUNT_results.json')
lucene = json.load(lf)
lf.close()

luc_dict = {}
for d in lucene:
    luc_dict[d['query']] = d['count']

mismatches = 0
for d in pizza:
    q = d['query']
    pc = d['count']
    lc = luc_dict.get(q, 'MISSING')
    if pc != lc:
        mismatches += 1
        if mismatches <= 10:
            print('MISMATCH: %r pizza=%s lucene=%s' % (q, pc, lc))

print('Total: %d/%d queries, %d mismatches' % (len(pizza), len(lucene), mismatches))
