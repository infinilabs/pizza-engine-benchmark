import json, os, sys
from collections import defaultdict
os.chdir('/Users/medcl/rust/search-benchmark-game')

with open('results.json') as f:
    data = json.load(f)

print("=" * 80)
print("COMPREHENSIVE BENCHMARK ANALYSIS")
print("=" * 80)

# ── 1. Per-engine median and ranking ──
for cmd in ['COUNT', 'TOP_10', 'TOP_100']:
    print(f"\n{'='*60}")
    print(f"  {cmd} — Median latency ranking")
    print(f"{'='*60}")
    engine_medians = []
    for engine, queries in data[cmd].items():
        durations = [q['duration'][0] for q in queries if q['duration'] and q['duration'][0] < 999999]
        if durations:
            durations.sort()
            med = durations[len(durations)//2]
            engine_medians.append((med, engine))
    engine_medians.sort()
    for rank, (med, engine) in enumerate(engine_medians, 1):
        marker = " ◀ BEST" if rank == 1 else ""
        print(f"  #{rank}  {med:8d}µs  {engine}{marker}")

# ── 2. Per-engine win rate against all others ──
for cmd in ['COUNT', 'TOP_10', 'TOP_100']:
    print(f"\n{'='*60}")
    print(f"  {cmd} — Per-query fastest engine distribution")
    print(f"{'='*60}")
    engines = list(data[cmd].keys())
    # Build query→engine→time map
    q_times = defaultdict(dict)
    for engine in engines:
        for q in data[cmd][engine]:
            t = q['duration'][0] if q['duration'] else 999999
            q_times[q['query']][engine] = t

    fastest_count = defaultdict(int)
    for query, times in q_times.items():
        best_engine = min(times, key=times.get)
        fastest_count[best_engine] += 1

    total_q = len(q_times)
    for engine, count in sorted(fastest_count.items(), key=lambda x: -x[1]):
        pct = 100 * count / total_q
        bar = "█" * int(pct / 2)
        print(f"  {engine:25s} {count:4d}/{total_q} ({pct:5.1f}%) {bar}")

# ── 3. pizza-engine-0.1 vs best-non-pizza: losses by tag ──
print(f"\n{'='*60}")
print(f"  COUNT — pizza-engine-0.1 losses by query tag")
print(f"{'='*60}")
cmd = 'COUNT'
pizza_data = {q['query']: q for q in data[cmd]['pizza-engine-0.1']}
best_other = {}
for engine, queries in data[cmd].items():
    if 'pizza' in engine:
        continue
    for q in queries:
        t = q['duration'][0] if q['duration'] else 999999
        if q['query'] not in best_other or t < best_other[q['query']][0]:
            best_other[q['query']] = (t, engine)

tag_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'ratios': []})
for query, pq in pizza_data.items():
    if query not in best_other:
        continue
    pt = pq['duration'][0] if pq['duration'] else 999999
    bt, be = best_other[query]
    ratio = pt / bt if bt > 0 else 999
    tags = pq.get('tags', [])
    for tag in tags:
        tag_stats[tag]['ratios'].append(ratio)
        if pt <= bt:
            tag_stats[tag]['wins'] += 1
        else:
            tag_stats[tag]['losses'] += 1

print(f"  {'Tag':45s} {'Win%':>6s} {'Wins':>5s} {'Loss':>5s} {'MedRatio':>9s} {'AvgRatio':>9s}")
for tag, s in sorted(tag_stats.items(), key=lambda x: sum(x[1]['ratios'])/len(x[1]['ratios'])):
    total = s['wins'] + s['losses']
    if total < 5:
        continue
    win_pct = 100 * s['wins'] / total
    ratios = sorted(s['ratios'])
    med_r = ratios[len(ratios)//2]
    avg_r = sum(ratios)/len(ratios)
    print(f"  {tag:45s} {win_pct:5.1f}% {s['wins']:5d} {s['losses']:5d} {med_r:9.3f} {avg_r:9.3f}")

# ── 4. pizza-hybrid vs pizza-engine-0.1 ──
for cmd in ['COUNT', 'TOP_10', 'TOP_100']:
    print(f"\n{'='*60}")
    print(f"  {cmd} — pizza-hybrid vs pizza-engine-0.1")
    print(f"{'='*60}")
    pe = {q['query']: q['duration'][0] if q['duration'] else 999999
          for q in data[cmd]['pizza-engine-0.1']}
    ph = {q['query']: q['duration'][0] if q['duration'] else 999999
          for q in data[cmd]['pizza-hybrid']}
    pm = {q['query']: q['duration'][0] if q['duration'] else 999999
          for q in data[cmd]['pizza-memory']}

    hybrid_slower = []
    hybrid_faster = []
    ratios = []
    for query in pe:
        if query not in ph:
            continue
        pet = pe[query]
        pht = ph[query]
        if pet > 0:
            r = pht / pet
            ratios.append(r)
            if r > 1.5:
                hybrid_slower.append((r, query, pet, pht, pm.get(query, 0)))
            elif r < 0.67:
                hybrid_faster.append((r, query, pet, pht))

    ratios.sort()
    med_r = ratios[len(ratios)//2] if ratios else 0
    avg_r = sum(ratios)/len(ratios) if ratios else 0
    n_slower = sum(1 for r in ratios if r > 1.0)
    n_faster = sum(1 for r in ratios if r < 1.0)
    print(f"  hybrid/engine ratio: median={med_r:.3f}x, avg={avg_r:.3f}x")
    print(f"  hybrid faster: {n_faster}, hybrid slower: {n_slower}")

    hybrid_slower.sort(reverse=True)
    if hybrid_slower:
        print(f"\n  Queries where hybrid is much slower (>1.5x):")
        for r, q, pet, pht, pmt in hybrid_slower[:10]:
            tags = pizza_data.get(q, {}).get('tags', []) if cmd == 'COUNT' else []
            tag_str = ','.join(t for t in tags if ':' not in t)[:20]
            print(f"    {r:.2f}x  engine={pet:7d}µs hybrid={pht:7d}µs memory={pmt:7d}µs  [{tag_str:20s}]  \"{q}\"")

# ── 5. All remaining >1.5x losses across all 3 modes ──
for cmd in ['COUNT', 'TOP_10', 'TOP_100']:
    print(f"\n{'='*60}")
    print(f"  {cmd} — ALL remaining losses >1.5x vs best non-pizza")
    print(f"{'='*60}")
    pizza_q = {q['query']: q for q in data[cmd]['pizza-engine-0.1']}
    best_np = {}
    for engine, queries in data[cmd].items():
        if 'pizza' in engine:
            continue
        for q in queries:
            t = q['duration'][0] if q['duration'] else 999999
            if q['query'] not in best_np or t < best_np[q['query']][0]:
                best_np[q['query']] = (t, engine)

    losses = []
    for query, pq in pizza_q.items():
        if query not in best_np:
            continue
        pt = pq['duration'][0] if pq['duration'] else 999999
        bt, be = best_np[query]
        if bt > 0 and pt / bt > 1.5:
            losses.append((pt/bt, pt, bt, be, query, pq.get('tags', [])))
    losses.sort(reverse=True)
    print(f"  Total queries >1.5x slower: {len(losses)}/{len(pizza_q)}")
    for ratio, pt, bt, be, q, tags in losses[:20]:
        tag_str = ','.join(t for t in tags if ':' not in t)[:25]
        print(f"    {ratio:.2f}x  {pt:8d}µs vs {bt:8d}µs ({be:20s})  [{tag_str:25s}]  \"{q}\"")
