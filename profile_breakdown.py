#!/usr/bin/env python3
"""Break down pizza-engine latency by query tag and compare to tantivy."""
import json, sys
from collections import defaultdict

with open("results.json") as f:
    data = json.load(f)

for task in ["COUNT", "TOP_10", "TOP_100"]:
    engines = data.get(task, {})
    pizza_by_tag = defaultdict(list)
    tantivy_by_tag = defaultdict(list)
    
    for eng, qlist in engines.items():
        if "pizza" in eng:
            target = pizza_by_tag
        elif "tantivy" in eng:
            target = tantivy_by_tag
        else:
            continue
        for q in qlist:
            dur = q["duration"][0]
            for tag in q.get("tags", []):
                target[tag].append(dur)

    print(f"\n{'='*70}")
    print(f"  {task}")
    print(f"{'='*70}")
    print(f"  {'Tag':<35} {'Pizza p50':>10} {'Tantivy p50':>12} {'Ratio':>8} {'n':>5}")
    print(f"  {'-'*35} {'-'*10} {'-'*12} {'-'*8} {'-'*5}")
    
    for tag in sorted(set(list(pizza_by_tag.keys()) + list(tantivy_by_tag.keys()))):
        p = sorted(pizza_by_tag.get(tag, []))
        t = sorted(tantivy_by_tag.get(tag, []))
        if not p or not t:
            continue
        pp50 = p[len(p)//2]
        tp50 = t[len(t)//2]
        ratio = pp50 / tp50 if tp50 > 0 else float('inf')
        print(f"  {tag:<35} {pp50:>8}us {tp50:>10}us {ratio:>7.2f}x {len(p):>5}")

    # Overall
    all_pizza = []
    all_tantivy = []
    for qlist in engines.values():
        for q in qlist:
            dur = q["duration"][0]
            eng_name = ""
            # Need engine name from the dict key
            pass
    
    for eng, qlist in engines.items():
        for q in qlist:
            dur = q["duration"][0]
            if "pizza" in eng:
                all_pizza.append(dur)
            elif "tantivy" in eng:
                all_tantivy.append(dur)
    
    if all_pizza and all_tantivy:
        all_pizza.sort()
        all_tantivy.sort()
        pp50 = all_pizza[len(all_pizza)//2]
        tp50 = all_tantivy[len(all_tantivy)//2]
        ratio = pp50 / tp50 if tp50 > 0 else 0
        print(f"  {'OVERALL':<35} {pp50:>8}us {tp50:>10}us {ratio:>7.2f}x {len(all_pizza):>5}")

# Show slowest 20 pizza queries for TOP_10
print(f"\n{'='*70}")
print(f"  TOP 20 SLOWEST pizza-engine TOP_10 queries")
print(f"{'='*70}")
for eng, qlist in data.get("TOP_10", {}).items():
    if "pizza" not in eng:
        continue
    ranked = sorted(qlist, key=lambda q: q["duration"][0], reverse=True)
    for i, q in enumerate(ranked[:20]):
        dur = q["duration"][0]
        tags = ",".join(q.get("tags", []))
        print(f"  {i+1:>3}. {dur:>6}us  [{tags:<50}]  {q['query'][:60]}")
