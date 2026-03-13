import subprocess, time, sys, threading

proc = subprocess.Popen(['./target/release/do_query', 'idx'],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# Drain stderr in background thread to prevent blocking
stderr_lines = []
def drain_stderr():
    for line in proc.stderr:
        stderr_lines.append(line.decode().strip())
t = threading.Thread(target=drain_stderr, daemon=True)
t.start()

# Wait for process to be ready (loads snapshot ~24s)
print("Waiting for do_query to load snapshot...", flush=True)
time.sleep(30)
for line in stderr_lines:
    print("  stderr:", line)
print("Starting benchmark...", flush=True)

queries = [
    ('COUNT', 'the'),
    ('COUNT', 'obama'),
    ('COUNT', 'griffith observatory'),
    ('COUNT', '+griffith +observatory'),
    ('COUNT', '"griffith observatory"'),
    ('TOP_10', 'the'),
    ('TOP_10', 'obama'),
    ('TOP_10', 'griffith observatory'),
    ('TOP_10', '+griffith +observatory'),
    ('TOP_10', '"griffith observatory"'),
    ('TOP_100', 'the'),
    ('TOP_100', 'griffith observatory'),
]

# Warmup
for cmd, q in queries:
    proc.stdin.write('{}\t{}\n'.format(cmd, q).encode())
    proc.stdin.flush()
    proc.stdout.readline()

# Benchmark
for cmd, q in queries:
    times = []
    for _ in range(100):
        start = time.monotonic()
        proc.stdin.write('{}\t{}\n'.format(cmd, q).encode())
        proc.stdin.flush()
        result = proc.stdout.readline().strip()
        elapsed = time.monotonic() - start
        times.append(elapsed * 1e6)
    avg = sum(times) / len(times)
    p50 = sorted(times)[49]
    p99 = sorted(times)[98]
    print('{:10s} {:35s}  avg={:8.0f}us  p50={:8.0f}us  p99={:8.0f}us  result={}'.format(
        cmd, q, avg, p50, p99, result.decode()))

proc.stdin.close()
proc.wait()
