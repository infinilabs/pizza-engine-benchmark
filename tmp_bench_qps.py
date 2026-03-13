import subprocess
import time
import statistics
import json
from pathlib import Path

root = Path('/Users/medcl/rust/search-benchmark-game')
queries_path = root / 'queries.txt'
input_lines = []
for line in queries_path.read_text().splitlines():
    if not line.strip():
        continue
    obj = json.loads(line)
    q = obj.get("query", "")
    if q:
        input_lines.append(f"CHECK_TOP_10\t{q}")
input_data = ("\n".join(input_lines) + "\n").encode("utf-8")

engines = {
    'pizza-engine-0.1': (root / 'engines/pizza-engine-0.1/target/release/do_query', root / 'engines/pizza-engine-0.1/idx'),
    'pizza-hybrid': (root / 'engines/pizza-hybrid/target/release/do_query', root / 'engines/pizza-hybrid/idx'),
    'pizza-hybrid-multi-core': (root / 'engines/pizza-hybrid-multi-core/target/release/do_query', root / 'engines/pizza-hybrid-multi-core/idx'),
}

runs = 3
qcount = len(input_lines)
print(f"queries={qcount}")

for name, (binary, index_dir) in engines.items():
    warmup = subprocess.run([str(binary), str(index_dir)], input=input_data, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if warmup.returncode != 0:
        print(f"{name}: warmup failed rc={warmup.returncode}")
        continue

    times = []
    for _ in range(runs):
        start = time.perf_counter()
        p = subprocess.run([str(binary), str(index_dir)], input=input_data, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elapsed = time.perf_counter() - start
        if p.returncode != 0:
            print(f"{name}: run failed rc={p.returncode}")
            times = []
            break
        times.append(elapsed)

    if not times:
        continue

    avg = statistics.mean(times)
    qps = qcount / avg
    ms_per_q = (avg / qcount) * 1000.0
    print(f"{name}: runs={[round(x, 3) for x in times]} avg={avg:.3f}s qps={qps:.1f} ms/query={ms_per_q:.3f}")
