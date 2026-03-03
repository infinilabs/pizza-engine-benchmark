import json

engines = ['lucene-9.9.2', 'tantivy-0.22', 'pizza-engine-0.1']

# Analyze COUNT mismatches by query type
data = {}
for eng in engines:
    f = f'results/{eng}#COUNT_results.json'
    with open(f) as fh:
        raw = json.load(fh)
    data[eng] = {item['query']: item['count'] for item in raw}

queries = [item['query'] for item in json.load(open(f'results/{engines[0]}#COUNT_results.json'))]

# Categorize queries
phrase_ok = phrase_diff = 0
intersection_ok = intersection_diff = 0
union_ok = union_diff = 0
single_ok = single_diff = 0

print("Sample mismatches by type:\n")

phrase_samples = []
inter_samples = []
union_samples = []
single_samples = []

for q in queries:
    lc = data['lucene-9.9.2'].get(q, -1)
    tc = data['tantivy-0.22'].get(q, -1)
    pc = data['pizza-engine-0.1'].get(q, -1)
    
    if q.startswith('"'):  # phrase
        if lc == tc == pc:
            phrase_ok += 1
        else:
            phrase_diff += 1
            if len(phrase_samples) < 5:
                phrase_samples.append((q, lc, tc, pc))
    elif q.startswith('+'):  # intersection
        if lc == tc == pc:
            intersection_ok += 1
        else:
            intersection_diff += 1
            if len(inter_samples) < 5:
                inter_samples.append((q, lc, tc, pc))
    elif ' ' in q:  # union (multi-word, no operator)
        if lc == tc == pc:
            union_ok += 1
        else:
            union_diff += 1
            if len(union_samples) < 5:
                union_samples.append((q, lc, tc, pc))
    else:  # single term
        if lc == tc == pc:
            single_ok += 1
        else:
            single_diff += 1
            if len(single_samples) < 5:
                single_samples.append((q, lc, tc, pc))

print(f"Query Type       OK    DIFF")
print(f"Single term     {single_ok:>4}  {single_diff:>4}")
print(f"Intersection    {intersection_ok:>4}  {intersection_diff:>4}")
print(f"Phrase          {phrase_ok:>4}  {phrase_diff:>4}")
print(f"Union           {union_ok:>4}  {union_diff:>4}")

print(f"\n--- Single term samples ---")
for q, l, t, p in single_samples:
    print(f"  {q:<40} L={l:<10} T={t:<10} P={p}")

print(f"\n--- Intersection samples ---")
for q, l, t, p in inter_samples:
    print(f"  {q:<40} L={l:<10} T={t:<10} P={p}")

print(f"\n--- Phrase samples ---")
for q, l, t, p in phrase_samples:
    print(f"  {q:<40} L={l:<10} T={t:<10} P={p}")

print(f"\n--- Union samples ---")
for q, l, t, p in union_samples:
    print(f"  {q:<40} L={l:<10} T={t:<10} P={p}")

# Also check TOP_10 
print("\n\n=== TOP_10 count check ===")
data10 = {}
for eng in engines:
    f = f'results/{eng}#TOP_10_results.json'
    with open(f) as fh:
        raw = json.load(fh)
    data10[eng] = {item['query']: item['count'] for item in raw}

# TOP_10: count should be min(total_hits, 10) for all
# But the benchmark returns total_hits, not min(total_hits, 10)
top10_ok = top10_diff = 0
top10_samples = []
for q in queries:
    lc = data10['lucene-9.9.2'].get(q, -1)
    tc = data10['tantivy-0.22'].get(q, -1)
    pc = data10['pizza-engine-0.1'].get(q, -1)
    if lc == tc == pc:
        top10_ok += 1
    else:
        top10_diff += 1
        if len(top10_samples) < 10:
            top10_samples.append((q, lc, tc, pc))

print(f"TOP_10 OK: {top10_ok}, DIFF: {top10_diff}")
for q, l, t, p in top10_samples:
    print(f"  {q:<50} L={l:<8} T={t:<8} P={p}")
