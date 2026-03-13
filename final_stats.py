import json
data = json.load(open('results.json'))

for mode in ['TOP_10','TOP_100','COUNT']:
    engines = list(data[mode].keys())
    pizza = {r['query']: r['duration'][0] for r in data[mode].get('pizza-engine-0.1',[])}
    
    total = len(pizza)
    wins_all = 0
    for q, pizza_t in pizza.items():
        all_faster = True
        for e in engines:
            if e == 'pizza-engine-0.1':
                continue
            e_data = {r['query']: r['duration'][0] for r in data[mode].get(e,[])}
            if q in e_data and e_data[q] < pizza_t:
                all_faster = False
                break
        if all_faster:
            wins_all += 1
    
    lucene_bp = {r['query']: r['duration'][0] for r in data[mode].get('lucene-10.4-bp',[])}
    wins_bp = sum(1 for q in pizza if q in lucene_bp and pizza[q] <= lucene_bp[q])
    losses_bp_15 = sum(1 for q in pizza if q in lucene_bp and pizza[q] > lucene_bp[q] * 1.5)
    
    print(f"{mode}: fastest={wins_all}/{total} ({100*wins_all/total:.1f}%), vs_bp_wins={wins_bp}/{total} ({100*wins_bp/total:.1f}%), losses>1.5x_vs_bp={losses_bp_15}")
