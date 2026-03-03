import json, statistics, os

engines = ['lucene-9.9.2', 'lucene-9.9.2-bp', 'tantivy-0.22', 'pizza-engine-0.1']

for cmd in ['TOP_10', 'TOP_100', 'COUNT']:
    data = {}
    available = []
    for eng in engines:
        fpath = f'results/{eng}#{cmd}_results.json'
        if not os.path.exists(fpath):
            continue
        raw = json.load(open(fpath))
        data[eng] = {item['query']: statistics.median(item['duration']) for item in raw}
        available.append(eng)

    if not available:
        continue

    queries = list(data[available[0]].keys())

    # Categorize
    cats = {'intersection (+)': [], 'phrase': [], 'union (bare)': [], 'single term': []}
    for q in queries:
        if q.startswith('"'):
            cats['phrase'].append(q)
        elif '+' in q:
            cats['intersection (+)'].append(q)
        elif ' ' in q:
            cats['union (bare)'].append(q)
        else:
            cats['single term'].append(q)

    # Build header
    col_names = {'lucene-9.9.2': 'Lucene', 'lucene-9.9.2-bp': 'LuceneBP', 'tantivy-0.22': 'Tantivy', 'pizza-engine-0.1': 'Pizza'}
    header = f'{"Category":<20} {"N":>4}'
    for eng in available:
        header += f' {col_names.get(eng, eng):>10}'
    header += f' {"P/L":>8}'
    if 'lucene-9.9.2-bp' in available:
        header += f' {"P/BP":>8}'

    print(f'=== {cmd} (median us) ===')
    print(header)
    print('-' * len(header))
    for cat, qs in cats.items():
        if not qs:
            continue
        avgs = {}
        for eng in available:
            vals = [data[eng][q] for q in qs if q in data[eng]]
            avgs[eng] = statistics.mean(vals) if vals else 0
        pizza = avgs.get('pizza-engine-0.1', 0)
        lucene = avgs.get('lucene-9.9.2', 1)
        lucene_bp = avgs.get('lucene-9.9.2-bp', 0)
        ratio_l = pizza / lucene if lucene > 0 else 0
        line = f'{cat:<20} {len(qs):>4}'
        for eng in available:
            line += f' {avgs[eng]:>10.0f}'
        line += f' {ratio_l:>7.2f}x'
        if 'lucene-9.9.2-bp' in available and lucene_bp > 0:
            line += f' {pizza / lucene_bp:>7.2f}x'
        print(line)

    all_avg = {eng: statistics.mean(data[eng].values()) for eng in available}
    pizza_all = all_avg.get('pizza-engine-0.1', 0)
    lucene_all = all_avg.get('lucene-9.9.2', 1)
    lucene_bp_all = all_avg.get('lucene-9.9.2-bp', 0)
    ratio = pizza_all / lucene_all if lucene_all > 0 else 0
    line = f'{"OVERALL":<20} {len(queries):>4}'
    for eng in available:
        line += f' {all_avg[eng]:>10.0f}'
    line += f' {ratio:>7.2f}x'
    if 'lucene-9.9.2-bp' in available and lucene_bp_all > 0:
        line += f' {pizza_all / lucene_bp_all:>7.2f}x'
    print(line)
    print()
