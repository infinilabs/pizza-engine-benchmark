#!/usr/bin/env python3
import json

with open('results.json') as f:
    data = json.load(f)

for mode in ['COUNT', 'TOP_10', 'TOP_100']:
    pe = {q['query']: q for q in data[mode]['pizza-engine-0.1']}
    all_engines = list(data[mode].keys())
    
    query_map = {}
    for eng in all_engines:
        for q in data[mode].get(eng, []):
            name = q['query']
            dur = q['duration'][0] if q['duration'] else 999999
            if name not in query_map:
                query_map[name] = {}
            query_map[name][eng] = dur
    
    wins = 0
    total = 0
    ratios = []
    for qname, engines in query_map.items():
        if 'pizza-engine-0.1' not in engines:
            continue
        total += 1
        pizza_t = engines['pizza-engine-0.1']
        fastest = min(engines.values())
        if pizza_t <= fastest * 1.01:
            wins += 1
        if fastest > 0:
            ratios.append(pizza_t / fastest)
    ratios.sort()
    median = ratios[len(ratios)//2]
    p90 = ratios[int(len(ratios)*0.9)]
    p95 = ratios[int(len(ratios)*0.95)]
    p99 = ratios[int(len(ratios)*0.99)]
    print(f'{mode}: wins={wins}/{total} ({100*wins/total:.1f}%), median_ratio={median:.2f}x, p90={p90:.2f}x, p95={p95:.2f}x, p99={p99:.2f}x')

print()
print("=" * 60)
print("TOP_10 breakdown by query category vs lucene-10.4-bp:")
print("=" * 60)

mode = 'TOP_10'
pe = {q['query']: q for q in data[mode]['pizza-engine-0.1']}
lbp = {q['query']: q for q in data[mode].get('lucene-10.4-bp', [])}

union_queries = [(q, pe[q], lbp.get(q)) for q in pe if any('union' in t for t in pe[q].get('tags',[]))]
inter_queries = [(q, pe[q], lbp.get(q)) for q in pe if any('intersection' in t for t in pe[q].get('tags',[]))]
phrase_queries = [(q, pe[q], lbp.get(q)) for q in pe if any('phrase' in t for t in pe[q].get('tags',[]))]

for tag, qs in [('union', union_queries), ('intersection', inter_queries), ('phrase', phrase_queries)]:
    total_q = len(qs)
    wins_q = sum(1 for q, pq, lq in qs if lq and pq['duration'] and lq['duration'] and pq['duration'][0] <= lq['duration'][0])
    losses_15 = sum(1 for q, pq, lq in qs if lq and pq['duration'] and lq['duration'] and lq['duration'][0] > 0 and pq['duration'][0] / lq['duration'][0] > 1.5)
    losses_2 = sum(1 for q, pq, lq in qs if lq and pq['duration'] and lq['duration'] and lq['duration'][0] > 0 and pq['duration'][0] / lq['duration'][0] > 2.0)
    
    ratios_cat = []
    for q, pq, lq in qs:
        if lq and pq['duration'] and lq['duration'] and lq['duration'][0] > 0:
            ratios_cat.append(pq['duration'][0] / lq['duration'][0])
    ratios_cat.sort()
    med = ratios_cat[len(ratios_cat)//2] if ratios_cat else 0
    print(f'  {tag}: total={total_q}, wins={wins_q}, >1.5x={losses_15}, >2x={losses_2}, median_ratio={med:.2f}x')

# Pizza vs tantivy on union queries
print()
print("Union queries: pizza vs tantivy-0.25:")
t025 = {q['query']: q for q in data[mode].get('tantivy-0.25', [])}
union_vs_tantivy = []
for q, pq, lq in union_queries:
    tq = t025.get(q)
    if tq and pq['duration'] and tq['duration'] and tq['duration'][0] > 0:
        union_vs_tantivy.append(pq['duration'][0] / tq['duration'][0])
union_vs_tantivy.sort()
med_t = union_vs_tantivy[len(union_vs_tantivy)//2] if union_vs_tantivy else 0
wins_t = sum(1 for r in union_vs_tantivy if r <= 1.0)
print(f'  median_ratio={med_t:.2f}x, wins={wins_t}/{len(union_vs_tantivy)}')

# Analyze: what makes the slow queries slow?
# Look at high-freq terms
print()
print("=" * 60)
print("Slow union TOP_10 queries - term frequency analysis:")
print("=" * 60)

losses = []
for q, pq, lq in union_queries:
    if lq and pq['duration'] and lq['duration'] and lq['duration'][0] > 0:
        ratio = pq['duration'][0] / lq['duration'][0]
        if ratio > 1.5:
            losses.append((ratio, q, pq['duration'][0], lq['duration'][0]))
losses.sort(reverse=True)

# Common stop words in queries
stop_words = {'the', 'of', 'to', 'in', 'a', 'as', 'on', 'or', 'not', 'be', 'for', 'and', 'is'}
has_stop = sum(1 for r, q, pt, lt in losses if any(w in stop_words for w in q.lower().split()))
no_stop = sum(1 for r, q, pt, lt in losses if not any(w in stop_words for w in q.lower().split()))
print(f"  With stop words: {has_stop}/{len(losses)}")
print(f"  No stop words: {no_stop}/{len(losses)}")

print()
for r, q, pt, lt in losses[:15]:
    words = q.lower().split()
    has_s = [w for w in words if w in stop_words]
    print(f'  {r:.2f}x  {pt:6d}us vs {lt:6d}us  stops={has_s}  "{q}"')

# Pizza-memory performance on these exact queries (interesting comparison)
print()
print("=" * 60)
print("Pizza-memory vs pizza-engine on same slow queries:")
print("=" * 60)
pm = {q['query']: q for q in data[mode].get('pizza-memory', [])}
for r, q, pt, lt in losses[:15]:
    pm_t = pm.get(q, {}).get('duration', [0])[0] if q in pm else 0
    print(f'  engine={pt:6d}us  memory={pm_t:6d}us  lucene-bp={lt:6d}us  mem/eng={pm_t/pt:.2f}x  "{q}"')
