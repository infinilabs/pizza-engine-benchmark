import json
import sys

engines = ['pizza-engine-0.1', 'pizza-hybrid']
commands = ['COUNT', 'TOP_10', 'TOP_100']

results = {}
for engine in engines:
    results[engine] = {}
    for cmd in commands:
        fname = "results/{}#{}_results.json".format(engine, cmd)
        try:
            with open(fname) as f:
                data = json.load(f)
        except FileNotFoundError:
            continue
        durations = []
        for q in data:
            if q['duration']:
                durations.extend(q['duration'])
        durations.sort()
        n = len(durations)
        if n > 0:
            avg = sum(durations) / n
            p50 = durations[n // 2]
            p90 = durations[int(n * 0.9)]
            p99 = durations[int(n * 0.99)]
            results[engine][cmd] = dict(avg=avg, p50=p50, p90=p90, p99=p99, n=n)

header = "{:<20} {:<10} {:>9} {:>9} {:>9} {:>9} {:>6}".format(
    "Engine", "Command", "Avg(us)", "P50(us)", "P90(us)", "P99(us)", "N")
print(header)
print("-" * len(header))
for engine in engines:
    for cmd in commands:
        r = results[engine].get(cmd)
        if r:
            print("{:<20} {:<10} {:>9.0f} {:>9} {:>9} {:>9} {:>6}".format(
                engine, cmd, r['avg'], r['p50'], r['p90'], r['p99'], r['n']))
