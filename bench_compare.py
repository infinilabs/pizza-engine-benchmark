import json, os
os.chdir('/Users/medcl/rust/search-benchmark-game')

with open('results.json') as f:
    data = json.load(f)
with open('docs/results.json') as f:
    old = json.load(f)

cmd = 'COUNT'
new_pizza = {q['query']: q for q in data[cmd]['pizza-engine-0.1']}
old_pizza = {q['query']: q for q in old[cmd]['pizza-engine-0.1']}
lucene_bp = {q['query']: q for q in data[cmd].get('lucene-10.4-bp', [])}

# Compare union queries before/after
print("=== UNION (OR) queries: before vs after ===")
union_improved = []
for query, nq in new_pizza.items():
    tags = nq.get('tags', [])
    if 'union' not in str(tags):
        continue
    nt = nq['duration'][0] if nq['duration'] else 999999
    ot_data = old_pizza.get(query)
    if ot_data:
        ot = ot_data['duration'][0] if ot_data['duration'] else 999999
        if ot > 0 and nt > 0:
            union_improved.append((ot/nt, query, ot, nt))

union_improved.sort(reverse=True)
print(f"Total union queries: {len(union_improved)}")
for s, q, ot, nt in union_improved[:15]:
    lb_data = lucene_bp.get(q, {})
    lb_t = lb_data.get('duration', [999999])[0] if lb_data else 999999
    print(f'  {s:.2f}x faster: {ot:8d}us -> {nt:8d}us (lucene-bp: {lb_t:8d}us)  "{q}"')

# Compare intersection queries
print("\n=== INTERSECTION (AND) queries: pizza vs lucene-bp ===")
int_losses = []
for query, nq in new_pizza.items():
    tags = nq.get('tags', [])
    if 'intersection' not in str(tags):
        continue
    nt = nq['duration'][0] if nq['duration'] else 999999
    lb_data = lucene_bp.get(query, {})
    lb_t = lb_data.get('duration', [999999])[0] if lb_data else 999999
    if lb_t > 0:
        ratio = nt / lb_t
        if ratio > 1.5:
            int_losses.append((ratio, query, nt, lb_t))

int_losses.sort(reverse=True)
print(f"Intersection losses (>1.5x vs lucene-bp): {len(int_losses)}")
for ratio, q, pt, lt in int_losses[:20]:
    ot_data = old_pizza.get(q)
    ot = ot_data['duration'][0] if ot_data and ot_data['duration'] else 0
    print(f'  {ratio:.2f}x slower: pizza={pt:8d}us, lucene-bp={lt:8d}us, old_pizza={ot:8d}us  "{q}"')

# Overall comparison before/after
print("\n=== Overall COUNT before vs after ===")
before_wins = 0
after_wins = 0
total = 0
for query in new_pizza:
    if query not in old_pizza:
        continue
    nt = new_pizza[query]['duration'][0] if new_pizza[query]['duration'] else 999999
    ot = old_pizza[query]['duration'][0] if old_pizza[query]['duration'] else 999999
    total += 1
    if nt < ot:
        after_wins += 1
    elif ot < nt:
        before_wins += 1

print(f"New better: {after_wins}, Old better: {before_wins}, Same: {total - after_wins - before_wins}")
