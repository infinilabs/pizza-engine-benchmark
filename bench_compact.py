#!/usr/bin/env python3
"""Quick timing benchmark for the compacted pizza-memory engine."""
import subprocess, time, sys

proc = subprocess.Popen(
    ['engines/pizza-memory/target/release/do_query', 'engines/pizza-memory/idx'],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr
)

queries = [
    ('COUNT', 'the'),
    ('COUNT', 'obama'),
    ('TOP_10', 'obama'),
    ('TOP_10', 'hurricane wilma'),
    ('TOP_10', '+mercedes +benz'),
    ('TOP_10', '"personal loan"'),
    ('TOP_10', 'canadian real estate'),
    ('COUNT', '+hello +world'),
    ('TOP_10', 'the'),
    ('TOP_10', '+the +news +journal'),
    ('COUNT', '"ugly people"'),
]

# Warmup (3 rounds) - first query blocks until engine is ready
for rnd in range(3):
    for cmd, q in queries:
        proc.stdin.write('{}\t{}\n'.format(cmd, q).encode())
        proc.stdin.flush()
        proc.stdout.readline()

print("Warmup done, measuring...", file=sys.stderr)

# Measure (5 rounds, report average)
timings = {}
results = {}
for i in range(len(queries)):
    timings[i] = []

for rnd in range(5):
    for i in range(len(queries)):
        cmd, q = queries[i]
        start = time.monotonic()
        proc.stdin.write('{}\t{}\n'.format(cmd, q).encode())
        proc.stdin.flush()
        result = proc.stdout.readline().strip().decode()
        end = time.monotonic()
        timings[i].append((end - start) * 1e6)
        results[i] = result

print("")
print("=== Compacted Index Query Latency ===")
for i in range(len(queries)):
    cmd, q = queries[i]
    avg = sum(timings[i]) / len(timings[i])
    mn = min(timings[i])
    print('{:>10} {:<35} => {:>10}  avg={:>10.0f} us  min={:>10.0f} us'.format(
        cmd, q, results[i], avg, mn))

proc.stdin.close()
proc.wait()
