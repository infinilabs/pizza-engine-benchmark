#!/usr/bin/env python3
"""Benchmark per-epoch BMW (frozen cache) vs CompactedIndex."""
import subprocess, time, sys, os

queries = [
    "COUNT\tthe",
    "COUNT\tobama",
    "TOP_10\tobama",
    "TOP_10\thurricane wilma",
    "TOP_10\t+mercedes +benz",
    'TOP_10\t"personal loan"',
    'TOP_10\t"canadian real estate"',
    "TOP_10\tthe",
    "TOP_10\t+the +news +journal",
    'COUNT\t"ugly people"',
]

def run_bench(label, env_extra=None):
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    base = os.path.dirname(os.path.abspath(__file__))
    bin_path = os.path.join(base, "engines/pizza-memory/target/release/do_query")
    idx_path = os.path.join(base, "engines/pizza-memory/idx")
    proc = subprocess.Popen(
        [bin_path, idx_path],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env,
        cwd=base,
    )
    # Wait for ready
    while True:
        line = proc.stderr.readline().decode()
        if "Ready" in line:
            print(f"  {line.strip()}", file=sys.stderr)
            break
        if line:
            print(f"  {line.strip()}", file=sys.stderr)

    results = []
    for q in queries:
        # Warm up
        proc.stdin.write((q + "\n").encode())
        proc.stdin.flush()
        proc.stdout.readline()

    for q in queries:
        times = []
        for _ in range(3):
            start = time.perf_counter_ns()
            proc.stdin.write((q + "\n").encode())
            proc.stdin.flush()
            result = proc.stdout.readline().decode().strip()
            elapsed_us = (time.perf_counter_ns() - start) / 1000
            times.append(elapsed_us)
        best = min(times)
        results.append((q, result, best))

    proc.stdin.close()
    proc.wait()
    return results


print("=" * 80)
print(f"{'Per-Epoch BMW (frozen cache, NO_COMPACT=1)':^80}")
print("=" * 80)
frozen = run_bench("frozen", {"NO_COMPACT": "1"})
print(f"\n{'Query':<45} {'Result':>10} {'Time (μs)':>12}")
print("-" * 70)
for q, r, t in frozen:
    print(f"{q:<45} {r:>10} {t:>12.0f}")

print("\n" + "=" * 80)
print(f"{'CompactedIndex (full compaction)':^80}")
print("=" * 80)
compact = run_bench("compact", {})
print(f"\n{'Query':<45} {'Result':>10} {'Time (μs)':>12}")
print("-" * 70)
for q, r, t in compact:
    print(f"{q:<45} {r:>10} {t:>12.0f}")

print("\n" + "=" * 80)
print(f"{'Comparison':^80}")
print("=" * 80)
print(f"\n{'Query':<40} {'Frozen':>10} {'Compact':>10} {'Ratio':>8}")
print("-" * 72)
for (q1, r1, t1), (q2, r2, t2) in zip(frozen, compact):
    ratio = t1 / t2 if t2 > 0 else float('inf')
    print(f"{q1:<40} {t1:>10.0f} {t2:>10.0f} {ratio:>7.1f}x")
