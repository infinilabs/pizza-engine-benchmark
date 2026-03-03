import json

engines = ['lucene-9.9.2', 'tantivy-0.22', 'pizza-engine-0.1']
commands = ['TOP_10', 'TOP_100', 'COUNT']

# Check COUNT values consistency
print("=== COUNT value consistency check ===")
print(f"{'Query':<55} {'Lucene':>8} {'Tantivy':>8} {'Pizza':>8}  {'Match':>6}")
print("-" * 100)

data = {}
for eng in engines:
    f = f'results/{eng}#COUNT_results.json'
    with open(f) as fh:
        raw = json.load(fh)
    data[eng] = {item['query']: item['count'] for item in raw}

queries = [item['query'] for item in json.load(open(f'results/{engines[0]}#COUNT_results.json'))]
mismatch_count = 0

for q in queries:
    counts = []
    row = f'{q:<55}'
    for eng in engines:
        c = data[eng].get(q, -1)
        counts.append(c)
        row += f' {c:>8}'
    match = "OK" if len(set(counts)) == 1 else "DIFF!"
    if match != "OK":
        mismatch_count += 1
    row += f'  {match:>6}'
    print(row)

print("-" * 100)
print(f"Total queries: {len(queries)}, Mismatches: {mismatch_count}")

# Check that all engines have the same queries
print("\n=== Query set consistency check ===")
for cmd in commands:
    query_sets = {}
    for eng in engines:
        f = f'results/{eng}#{cmd}_results.json'
        with open(f) as fh:
            raw = json.load(fh)
        query_sets[eng] = [item['query'] for item in raw]
    
    all_same = all(query_sets[eng] == query_sets[engines[0]] for eng in engines)
    print(f"{cmd}: {len(query_sets[engines[0]])} queries, all engines same set: {all_same}")
    if not all_same:
        for eng in engines:
            print(f"  {eng}: {len(query_sets[eng])} queries")

# Check TOP_10 count values
print("\n=== TOP_10 count consistency check ===")
print(f"{'Query':<55} {'Lucene':>8} {'Tantivy':>8} {'Pizza':>8}  {'Match':>6}")
print("-" * 100)
data10 = {}
for eng in engines:
    f = f'results/{eng}#TOP_10_results.json'
    with open(f) as fh:
        raw = json.load(fh)
    data10[eng] = {item['query']: item['count'] for item in raw}

mismatch10 = 0
for q in queries:
    counts = []
    row = f'{q:<55}'
    for eng in engines:
        c = data10[eng].get(q, -1)
        counts.append(c)
        row += f' {c:>8}'
    match = "OK" if len(set(counts)) == 1 else "DIFF!"
    if match != "OK":
        mismatch10 += 1
    row += f'  {match:>6}'
    if match != "OK":
        print(row)

print(f"Total queries: {len(queries)}, Mismatches: {mismatch10}")
