import json, sys

with open('results/pizza-engine-0.1#COUNT_results.json') as f:
    data = json.load(f)
with open('results/lucene-9.9.2-bp#COUNT_results.json') as f:
    bp = json.load(f)
with open('results/lucene-9.9.2#COUNT_results.json') as f:
    luc = json.load(f)

bp_dict = {d['query']: d['duration'] for d in bp}
luc_dict = {d['query']: d['duration'] for d in luc}

inter = []
for d in data:
    q = d['query']
    if q.strip().startswith('+'):
        t = min(d['duration'])
        bp_t = min(bp_dict.get(q, [999999]))
        luc_t = min(luc_dict.get(q, [999999]))
        inter.append((q, t, bp_t, luc_t))

inter.sort(key=lambda x: -x[1])
total_p = sum(t for _,t,_,_ in inter)
total_bp = sum(t for _,_,t,_ in inter)
print(f'Intersection queries: {len(inter)}, Pizza total: {total_p}us, BP total: {total_bp}us, ratio: {total_p/total_bp:.2f}x')
print()
print(f'{"Pizza":>10} {"BP":>10} {"Lucene":>10} {"P/BP":>6}  Query')
for q, t, bp_t, luc_t in inter[:25]:
    ratio = f'{t/bp_t:.2f}' if bp_t > 0 else 'N/A'
    print(f'{t:>10} {bp_t:>10} {luc_t:>10} {ratio:>6}  {q}')
