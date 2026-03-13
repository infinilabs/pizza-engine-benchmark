import json
import sys

with open('docs/results.json') as f:
    data = json.load(f)

# Clean empty key
if "" in data:
    del data[""]

pizza_engines = ["pizza-engine-0.1", "pizza-memory", "pizza-hybrid"]
other_engines = ["tantivy-0.22", "tantivy-0.25", "lucene-10.4", "lucene-10.4-bp", "lucene-9.9.2", "lucene-9.9.2-bp"]

for mode in ["COUNT", "TOP_10", "TOP_100"]:
    if mode not in data:
        continue
    mode_data = data[mode]
    
    # Collect per-engine data
    engines = sorted(mode_data.keys())
    
    # Build query -> engine -> time
    query_map = {}
    for eng in engines:
        for q in mode_data[eng]:
            qname = q['query']
            dur = q['duration']
            tags = q['tags']
            if dur and len(dur) > 0:
                if qname not in query_map:
                    query_map[qname] = {'tags': tags}
                query_map[qname][eng] = dur[0]
    
    print(f"\n{'='*120}")
    print(f"MODE: {mode}")
    print(f"{'='*120}")
    
    # Per-tag average comparison
    tag_stats = {}
    for qname, qdata in query_map.items():
        tags = [t for t in qdata.get('tags', []) if ':' not in t]
        for tag in tags:
            if tag not in tag_stats:
                tag_stats[tag] = {e: [] for e in engines}
            for eng in engines:
                if eng in qdata:
                    tag_stats[tag][eng].append(qdata[eng])
    
    print(f"\n--- Per-Tag Average (us) ---")
    print(f"{'Tag':<20}", end="")
    for eng in engines:
        print(f"{eng:>20}", end="")
    print()
    
    for tag in sorted(tag_stats.keys()):
        print(f"{tag:<20}", end="")
        for eng in engines:
            vals = tag_stats[tag][eng]
            avg = sum(vals) / len(vals) if vals else 0
            print(f"{avg:>20.0f}", end="")
        print()
    
    # Find queries where pizza is MUCH slower than best non-pizza
    print(f"\n--- Queries where Pizza is slowest (pizza vs best-other ratio) ---")
    pizza_slow = []
    for qname, qdata in query_map.items():
        tags = [t for t in qdata.get('tags', []) if ':' not in t]
        
        # Best pizza time
        best_pizza = min((qdata.get(pe, float('inf')) for pe in pizza_engines), default=float('inf'))
        # Best other time
        best_other = min((qdata.get(oe, float('inf')) for oe in other_engines if oe in qdata), default=float('inf'))
        
        if best_pizza < float('inf') and best_other < float('inf') and best_other > 0:
            ratio = best_pizza / best_other
            if ratio > 1.5:
                pizza_slow.append({
                    'query': qname,
                    'tags': tags,
                    'pizza_best': best_pizza,
                    'other_best': best_other,
                    'ratio': ratio,
                    'all': {e: qdata.get(e) for e in engines}
                })
    
    pizza_slow.sort(key=lambda x: -x['ratio'])
    
    print(f"Total queries where pizza > 1.5x slower: {len(pizza_slow)}")
    print(f"{'#':<4} {'Ratio':>8} {'Pizza':>10} {'Other':>10} {'Tags':<25} {'Query':<60}")
    for i, item in enumerate(pizza_slow[:50]):
        tags_str = ','.join(item['tags'][:3])
        print(f"{i+1:<4} {item['ratio']:>8.2f}x {item['pizza_best']:>10.0f} {item['other_best']:>10.0f} {tags_str:<25} {item['query'][:60]}")
    
    # Also show queries where pizza WINS
    pizza_wins = []
    for qname, qdata in query_map.items():
        tags = [t for t in qdata.get('tags', []) if ':' not in t]
        best_pizza = min((qdata.get(pe, float('inf')) for pe in pizza_engines), default=float('inf'))
        best_other = min((qdata.get(oe, float('inf')) for oe in other_engines if oe in qdata), default=float('inf'))
        
        if best_pizza < float('inf') and best_other < float('inf') and best_pizza > 0:
            ratio = best_other / best_pizza
            if ratio > 1.1:
                pizza_wins.append({
                    'query': qname,
                    'tags': tags,
                    'pizza_best': best_pizza,
                    'other_best': best_other,
                    'ratio': ratio,
                })
    
    pizza_wins.sort(key=lambda x: -x['ratio'])
    print(f"\nQueries where pizza WINS (by > 1.1x): {len(pizza_wins)}")
    for i, item in enumerate(pizza_wins[:20]):
        tags_str = ','.join(item['tags'][:3])
        print(f"{i+1:<4} {item['ratio']:>8.2f}x faster  pizza={item['pizza_best']:>8.0f}  other={item['other_best']:>8.0f}  {tags_str:<25} {item['query'][:60]}")

    # Summarize by tag: how many queries pizza wins vs loses
    print(f"\n--- Win/Loss by Tag ---")
    tag_wl = {}
    for qname, qdata in query_map.items():
        tags = [t for t in qdata.get('tags', []) if ':' not in t]
        best_pizza = min((qdata.get(pe, float('inf')) for pe in pizza_engines), default=float('inf'))
        best_other = min((qdata.get(oe, float('inf')) for oe in other_engines if oe in qdata), default=float('inf'))
        if best_pizza >= float('inf') or best_other >= float('inf'):
            continue
        for tag in tags:
            if tag not in tag_wl:
                tag_wl[tag] = {'wins': 0, 'losses': 0, 'ties': 0, 'total_pizza': 0, 'total_other': 0, 'count': 0}
            if best_pizza < best_other * 0.95:
                tag_wl[tag]['wins'] += 1
            elif best_pizza > best_other * 1.05:
                tag_wl[tag]['losses'] += 1
            else:
                tag_wl[tag]['ties'] += 1
            tag_wl[tag]['total_pizza'] += best_pizza
            tag_wl[tag]['total_other'] += best_other
            tag_wl[tag]['count'] += 1
    
    print(f"{'Tag':<20} {'Wins':>6} {'Ties':>6} {'Losses':>8} {'Avg Pizza':>12} {'Avg Other':>12} {'Pizza/Other':>12}")
    for tag in sorted(tag_wl.keys()):
        wl = tag_wl[tag]
        avg_p = wl['total_pizza'] / wl['count'] if wl['count'] > 0 else 0
        avg_o = wl['total_other'] / wl['count'] if wl['count'] > 0 else 0
        ratio = avg_p / avg_o if avg_o > 0 else 0
        print(f"{tag:<20} {wl['wins']:>6} {wl['ties']:>6} {wl['losses']:>8} {avg_p:>12.0f} {avg_o:>12.0f} {ratio:>12.2f}x")

    # Detailed per-query dump for the worst pizza performers
    print(f"\n--- Detailed: Top 10 worst pizza queries (all engine times) ---")
    for i, item in enumerate(pizza_slow[:10]):
        print(f"\n  [{i+1}] {item['query']}  tags={','.join(item['tags'][:3])}  ratio={item['ratio']:.2f}x")
        for eng in engines:
            val = item['all'].get(eng)
            if val is not None:
                marker = " <-- PIZZA" if eng in pizza_engines else ""
                print(f"      {eng:>30}: {val:>10} us{marker}")
