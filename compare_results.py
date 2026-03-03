#!/usr/bin/env python3
import json
import sys
import os

def load_results(path):
    with open(path) as f:
        data = json.load(f)
    durations = {}
    for entry in data:
        q = entry['query']
        dur = entry['duration']
        if dur:
            avg = sum(dur) / len(dur)
            durations[q] = avg
    return durations

results_dir = "results"
engines = {}
for fname in sorted(os.listdir(results_dir)):
    if fname.endswith("_results.json") and "TOP_10" in fname:
        engine_name = fname.replace("#TOP_10_results.json", "")
        engines[engine_name] = load_results(os.path.join(results_dir, fname))

print(f"Engines found: {list(engines.keys())}")
print()

# Find common queries across all engines
all_query_sets = [set(d.keys()) for d in engines.values()]
if not all_query_sets:
    print("No results found")
    sys.exit(1)
common = all_query_sets[0]
for qs in all_query_sets[1:]:
    common = common & qs
print(f"Common queries: {len(common)}")
print()

# Summary table
print(f"{'Engine':<30} {'Avg (us)':>10} {'Median (us)':>12} {'P99 (us)':>10}")
print("-" * 65)
for name, data in sorted(engines.items()):
    vals = sorted([data[q] for q in common])
    avg = sum(vals) / len(vals)
    median = vals[len(vals) // 2]
    p99 = vals[int(len(vals) * 0.99)]
    print(f"{name:<30} {avg:>10.1f} {median:>12.1f} {p99:>10.1f}")

# Pairwise comparison
names = sorted(engines.keys())
if len(names) >= 2:
    print()
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a_name, b_name = names[i], names[j]
            a_data, b_data = engines[a_name], engines[b_name]
            a_total = sum(a_data[q] for q in common)
            b_total = sum(b_data[q] for q in common)
            ratio = a_total / b_total if b_total > 0 else float('inf')
            print(f"{a_name} vs {b_name}: ratio = {ratio:.2f}x")
            if ratio > 1:
                print(f"  -> {b_name} is {ratio:.2f}x faster overall")
            else:
                print(f"  -> {a_name} is {1/ratio:.2f}x faster overall")

            # Per-query ratios
            ratios = [(q, a_data[q], b_data[q], a_data[q] / b_data[q])
                      for q in common if b_data[q] > 0]
            ratios.sort(key=lambda x: x[3])

            n_a_faster = sum(1 for _, _, _, r in ratios if r < 1.0)
            n_b_faster = sum(1 for _, _, _, r in ratios if r > 1.0)
            print(f"  {a_name} faster on {n_a_faster} queries, {b_name} faster on {n_b_faster} queries")
            print()
