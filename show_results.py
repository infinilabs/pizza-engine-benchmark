import json, os, statistics

results = {}
for f in os.listdir('results'):
    if not f.endswith('.json'):
        continue
    engine_cmd = f.replace('_results.json', '')
    parts = engine_cmd.split('#')
    engine, cmd = parts[0], parts[1]
    data = json.load(open(os.path.join('results', f)))
    # data is a list of {query, tags, count, duration:[...]}
    all_medians = []
    for item in data:
        med = statistics.median(item['duration'])
        all_medians.append(med)
    all_medians.sort()
    median = all_medians[len(all_medians) // 2]
    p90 = all_medians[int(len(all_medians) * 0.9)]
    avg = sum(all_medians) / len(all_medians)
    results.setdefault(cmd, {})[engine] = (median, avg, p90)

for cmd in sorted(results):
    print()
    print(f'=== {cmd} ===')
    print(f"{'Engine':>25} {'Median(us)':>12} {'Avg(us)':>12} {'P90(us)':>12}")
    entries = sorted(results[cmd].items(), key=lambda x: x[1][0])
    for engine, (med, avg, p90) in entries:
        print(f'{engine:>25} {med:>12.0f} {avg:>12.0f} {p90:>12.0f}')
    if len(entries) >= 2:
        fast_name, fast_vals = entries[0]
        slow_name, slow_vals = entries[-1]
        ratio = slow_vals[0] / fast_vals[0]
        print(f'  -> {fast_name} is {ratio:.2f}x faster (median)')
