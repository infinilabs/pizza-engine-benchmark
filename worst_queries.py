#!/usr/bin/env python3
"""Show the worst pizza queries vs tantivy for TOP_10 and TOP_100."""
import json

with open("results.json") as f:
    data = json.load(f)

for cmd in ["TOP_10", "TOP_100"]:
    print(f"\n{'='*80}")
    print(f"  {cmd}: Pizza vs Tantivy — worst absolute time and worst ratio")
    print(f"{'='*80}")
    
    pizza_qs = {q["query"]: q for q in data.get(cmd, {}).get("pizza-engine-0.1", [])}
    tantivy_qs = {q["query"]: q for q in data.get(cmd, {}).get("tantivy-0.22", [])}
    
    rows = []
    for query, pq in pizza_qs.items():
        tq = tantivy_qs.get(query)
        if not tq:
            continue
        pd = pq["duration"][-1] if pq["duration"] else 0
        td = tq["duration"][-1] if tq["duration"] else 0
        ratio = pd / td if td > 0 else 999
        excess = pd - td
        tags = ",".join(pq.get("tags", []))
        rows.append((pd, td, ratio, excess, tags, query))
    
    # Top 20 by absolute pizza time
    print(f"\n  --- Top 20 by absolute pizza time ---")
    print(f"  {'Pizza':>10s} {'Tantivy':>10s} {'Ratio':>7s} {'Excess':>10s}  Query")
    for pd, td, ratio, excess, tags, query in sorted(rows, key=lambda x: -x[0])[:20]:
        marker = " <<<" if ratio > 1.0 else ""
        print(f"  {pd:>9d}us {td:>9d}us {ratio:>6.2f}x {excess:>9d}us  [{tags}] {query}{marker}")
    
    # Top 20 by worst ratio (where pizza > tantivy)
    print(f"\n  --- Top 20 by worst ratio (pizza slower) ---")
    print(f"  {'Pizza':>10s} {'Tantivy':>10s} {'Ratio':>7s} {'Excess':>10s}  Query")
    for pd, td, ratio, excess, tags, query in sorted(rows, key=lambda x: -x[2])[:20]:
        if ratio <= 1.0:
            break
        print(f"  {pd:>9d}us {td:>9d}us {ratio:>6.2f}x {excess:>9d}us  [{tags}] {query}")
    
    # Summary: how many queries is pizza slower?
    slower = [r for r in rows if r[2] > 1.0]
    much_slower = [r for r in rows if r[2] > 2.0]
    total_excess = sum(r[3] for r in rows if r[3] > 0)
    print(f"\n  Pizza slower: {len(slower)}/{len(rows)} queries, >2x slower: {len(much_slower)}")
    print(f"  Total excess time (pizza - tantivy, where pizza slower): {total_excess:,d}us")
