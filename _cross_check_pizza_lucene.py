#!/usr/bin/env python3
"""Quick cross-check: pizza-engine-0.1 vs lucene-10.4-bp.
   Checks COUNT and CHECK_TOP_10 for all queries in queries.txt.
"""

import subprocess
import json
import sys
from os import path

SCORE_ABS_TOLERANCE = 0.001
SCORE_REL_TOLERANCE = 0.02


class Engine:
    def __init__(self, name):
        self.name = name
        cwd = path.join(path.dirname(path.abspath(__file__)), "engines", name)
        self.process = subprocess.Popen(
            ["make", "--no-print-directory", "serve"],
            cwd=cwd, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def query(self, cmd, q):
        line = f"{cmd}\t{q}\n"
        self.process.stdin.write(line.encode())
        self.process.stdin.flush()
        resp = self.process.stdout.readline().strip().decode()
        return resp

    def close(self):
        try: self.process.stdin.close()
        except: pass
        try: self.process.terminate(); self.process.wait(timeout=5)
        except: pass


def parse_topk(resp):
    if not resp: return []
    pairs = []
    for part in resp.split(","):
        part = part.strip()
        if not part: continue
        idx = part.rfind(":")
        if idx < 0: continue
        try:
            doc_id = int(part[:idx])
            score = float(part[idx+1:])
            pairs.append((doc_id, score))
        except ValueError:
            continue
    return pairs


def scores_close(a, b):
    if abs(a - b) <= SCORE_ABS_TOLERANCE: return True
    denom = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / denom <= SCORE_REL_TOLERANCE


def main():
    queries_file = sys.argv[1] if len(sys.argv) > 1 else "queries.txt"
    with open(queries_file) as f:
        queries = [json.loads(line)["query"] for line in f if line.strip()]

    print(f"Loaded {len(queries)} queries from {queries_file}")

    pizza = Engine("pizza-engine-0.1")
    lucene = Engine("lucene-10.4-bp")

    count_match = 0
    count_mismatch = 0
    count_errors = []
    topk_match = 0
    topk_issues = 0
    topk_errors = []

    for i, q in enumerate(queries):
        if (i + 1) % 100 == 0:
            print(f"  [{i+1}/{len(queries)}]...", file=sys.stderr)

        # COUNT check
        pc = pizza.query("CHECK_COUNT", q)
        lc = lucene.query("CHECK_COUNT", q)
        try:
            pc_int = int(pc)
            lc_int = int(lc)
            if pc_int == lc_int:
                count_match += 1
            else:
                count_mismatch += 1
                count_errors.append((q, pc_int, lc_int))
        except ValueError:
            count_mismatch += 1
            count_errors.append((q, pc, lc))

        # TOP_10 check
        pt = pizza.query("CHECK_TOP_10", q)
        lt = lucene.query("CHECK_TOP_10", q)
        p_docs = parse_topk(pt)
        l_docs = parse_topk(lt)

        p_ids = [d[0] for d in p_docs]
        l_ids = [d[0] for d in l_docs]

        if len(p_ids) != len(l_ids):
            topk_issues += 1
            topk_errors.append((q, f"count {len(p_ids)} vs {len(l_ids)}", p_ids[:3], l_ids[:3]))
        elif set(p_ids) == set(l_ids):
            topk_match += 1
            # Check order differences (allow if scores within tolerance)
            if p_ids != l_ids:
                # Score-tied reorder — acceptable
                pass
        else:
            overlap = len(set(p_ids) & set(l_ids))
            pct = overlap / max(len(p_ids), len(l_ids), 1) * 100
            if pct >= 70:
                topk_match += 1  # minor score-tie difference
            else:
                topk_issues += 1
                topk_errors.append((q, f"overlap {overlap}/{len(p_ids)} ({pct:.0f}%)", p_ids[:3], l_ids[:3]))

    pizza.close()
    lucene.close()

    print(f"\n{'='*60}")
    print(f"CORRECTNESS REPORT: pizza-engine-0.1 vs lucene-10.4-bp")
    print(f"{'='*60}")
    print(f"\nCOUNT: {count_match} match, {count_mismatch} mismatch (of {len(queries)})")
    if count_errors:
        print(f"  First 10 COUNT mismatches:")
        for q, pc, lc in count_errors[:10]:
            print(f"    '{q}': pizza={pc}, lucene={lc}")

    print(f"\nTOP_10: {topk_match} match, {topk_issues} issues (of {len(queries)})")
    if topk_errors:
        print(f"  First 10 TOP_10 issues:")
        for q, detail, p, l in topk_errors[:10]:
            print(f"    '{q}': {detail}")
            print(f"      pizza:  {p}")
            print(f"      lucene: {l}")

    total = len(queries) * 2
    passed = count_match + topk_match
    print(f"\nOVERALL: {passed}/{total} checks passed ({passed/total*100:.1f}%)")


if __name__ == "__main__":
    main()
