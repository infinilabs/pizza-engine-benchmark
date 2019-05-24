import json

reference = "tantivy-0.8"

all = json.load(open("results.json"))

def query_count(query_bench):
    c = {}
    for q in query_bench:
        c[q["query"]] = q["count"] 
    return c


def compare(ref_count, engine_count):
    diffs = []
    assert len(ref_count) == len(engine_count)
    for q in ref_count:
        if ref_count[q] != engine_count[q]:
            diffs.append((q, ref_count[q], engine_count[q]))
    return diffs
    
for (metric, engine_bench) in all.items():
    ref_count = query_count(engine_bench[reference])
    # print ref_count
    for (engine, query_bench) in engine_bench.items():
        engine_count = query_count(query_bench)
        diff = compare(ref_count, engine_count)
        if diff:
            print "Engine", engine
            print diff
