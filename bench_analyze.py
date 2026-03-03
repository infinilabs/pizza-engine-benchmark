import json, os, sys
from collections import defaultdict

os.chdir(os.path.dirname(os.path.abspath(__file__)))

data = {}
for f in os.listdir('results'):
    if not f.endswith('_results.json'):
        continue
    parts = f.replace('_results.json', '').split('#')
    engine, cmd = parts[0], parts[1]
    with open(f'results/{f}') as fh:
        data[(engine, cmd)] = json.load(fh)

for cmd in ['TOP_10', 'TOP_100', 'COUNT']:
    pizza = data.get(('pizza-engine-0.1', cmd))
    lucene = data.get(('lucene-9.9.2-bp', cmd))
    tantivy = data.get(('tantivy-0.22', cmd))
    if not pizza or not lucene:
        continue

    tag_times = defaultdict(lambda: {'pizza': [], 'lucene': [], 'tantivy': []})
    pq = {r['query']: r for r in pizza}
    lq = {r['query']: r for r in lucene}
    tq = {r['query']: r for r in tantivy} if tantivy else {}

    for q in pq:
        if q not in lq:
            continue
        tags = pq[q].get('tags', ['all'])
        pt = sum(pq[q]['duration']) / len(pq[q]['duration'])
        lt = sum(lq[q]['duration']) / len(lq[q]['duration'])
        tt = sum(tq[q]['duration']) / len(tq[q]['duration']) if q in tq else None
        for tag in tags:
            tag_times[tag]['pizza'].append(pt)
            tag_times[tag]['lucene'].append(lt)
            if tt is not None:
                tag_times[tag]['tantivy'].append(tt)
        tag_times['ALL']['pizza'].append(pt)
        tag_times['ALL']['lucene'].append(lt)
        if tt is not None:
            tag_times['ALL']['tantivy'].append(tt)

    print(f'\n=== {cmd} ===')
    hdr = f"{'Tag':<20} {'#Q':>5} {'Pizza(ms)':>10} {'Lucene(ms)':>11} {'Tantivy(ms)':>12} {'P/L':>7} {'P/T':>7}"
    print(hdr)
    print('-' * len(hdr))
    for tag in sorted(tag_times.keys()):
        t = tag_times[tag]
        n = len(t['pizza'])
        pavg = sum(t['pizza']) / n / 1000
        lavg = sum(t['lucene']) / n / 1000
        tavg = sum(t['tantivy']) / n / 1000 if t['tantivy'] else 0
        ratio_l = pavg / lavg if lavg else 0
        ratio_t = pavg / tavg if tavg else 0
        tstr = f'{tavg:12.2f}' if tavg else '         N/A'
        rtstr = f'{ratio_t:6.2f}x' if tavg else '    N/A'
        print(f'{tag:<20} {n:>5} {pavg:10.2f} {lavg:11.2f} {tstr} {ratio_l:6.2f}x {rtstr}')

# Slowest queries for TOP_10
print('\n=== TOP_10: Slowest 20 queries (pizza) ===')
pizza = data.get(('pizza-engine-0.1', 'TOP_10'))
lucene = data.get(('lucene-9.9.2-bp', 'TOP_10'))
if pizza and lucene:
    pq = {r['query']: r for r in pizza}
    lq = {r['query']: r for r in lucene}
    rows = []
    for q in pq:
        if q not in lq:
            continue
        pt = sum(pq[q]['duration']) / len(pq[q]['duration'])
        lt = sum(lq[q]['duration']) / len(lq[q]['duration'])
        tags = pq[q].get('tags', [])
        rows.append((pt, lt, tags, q))
    rows.sort(reverse=True)
    print(f"{'Pizza(ms)':>10} {'Lucene(ms)':>11} {'Ratio':>7} {'Tags':<25} Query")
    print('-' * 110)
    for pt, lt, tags, q in rows[:20]:
        ratio = pt / lt if lt else 0
        tstr = ",".join(tags)
        print(f'{pt/1000:10.2f} {lt/1000:11.2f} {ratio:6.2f}x {tstr:<25} {q[:60]}')
