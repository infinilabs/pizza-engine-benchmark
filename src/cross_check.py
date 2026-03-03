#!/usr/bin/env python3
"""
Cross-check engine results for correctness.

Sends CHECK_COUNT, CHECK_TOP_10, CHECK_TOP_100 queries to each engine and
compares:
  - COUNT must match across all engines
  - TOP_K doc ids and scores: compared across engines, with tolerance for
    floating-point differences and score-tie reordering

All engines store the corpus line number (1-based) as the `id` field,
so everyone outputs the same numeric doc IDs directly.

Usage:
  COMMANDS="TOP_10 TOP_100 COUNT" ENGINES="tantivy-0.22 pizza-engine-0.1 lucene-9.9.2-bp lucene-9.9.2" \
    make cross-check

Environment:
  ENGINES    space-separated list of engine directories under engines/
  COMMANDS   space-separated list of commands: COUNT, TOP_10, TOP_100, TOP_1000
"""

import subprocess
import os
import sys
import json
from os import path
from collections import defaultdict

COMMANDS = os.environ.get('COMMANDS', 'COUNT TOP_10 TOP_100').split()
SCORE_TOLERANCE = 0.02  # relative tolerance for score comparison
SCORE_ABS_TOLERANCE = 0.001  # absolute tolerance for very small scores


class SearchClient:
    """Manages a subprocess engine that reads queries from stdin."""

    def __init__(self, engine):
        self.engine = engine
        dirname = path.dirname(path.dirname(path.abspath(__file__)))
        cwd = path.join(dirname, "engines", engine)
        self.cwd = cwd
        self.process = subprocess.Popen(
            ["make", "--no-print-directory", "serve"],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def query(self, query_str, command):
        """Send a CHECK_* query and return the raw response line."""
        check_cmd = f"CHECK_{command}"
        line = f"{check_cmd}\t{query_str}\n"
        self.process.stdin.write(line.encode("utf-8"))
        self.process.stdin.flush()
        recv = self.process.stdout.readline().strip().decode("utf-8")
        if recv == "UNSUPPORTED":
            return None
        return recv

    def close(self):
        try:
            self.process.stdin.close()
        except:
            pass
        try:
            self.process.stdout.close()
        except:
            pass
        try:
            self.process.terminate()
            self.process.wait(timeout=5)
        except:
            pass


def parse_topk_response(response):
    """
    Parse a CHECK_TOP_K response: 'id1:score1,id2:score2,...'
    Returns list of (doc_id_int, score_float) in rank order.
    All engines now store corpus line numbers (1-based int) as the id field.
    """
    if not response or response == "UNSUPPORTED":
        return []
    pairs = []
    for part in response.split(","):
        part = part.strip()
        if not part:
            continue
        # Split on the last colon: "doc_id:score"
        idx = part.rfind(":")
        if idx < 0:
            continue
        raw_id = part[:idx]
        try:
            score = float(part[idx + 1:])
        except ValueError:
            continue
        try:
            doc_id = int(raw_id)
        except ValueError:
            doc_id = raw_id  # fallback
        pairs.append((doc_id, score))
    return pairs


def scores_close(a, b):
    """Check if two scores are close enough (relative + absolute tolerance)."""
    if abs(a - b) <= SCORE_ABS_TOLERANCE:
        return True
    denom = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / denom <= SCORE_TOLERANCE


def compare_count(results, query_str, engines):
    """Compare COUNT results across engines. Returns list of issues."""
    issues = []
    counts = {}
    for eng in engines:
        resp = results.get(eng)
        if resp is None:
            issues.append(f"  {eng}: UNSUPPORTED")
            continue
        try:
            counts[eng] = int(resp)
        except ValueError:
            issues.append(f"  {eng}: invalid response '{resp}'")

    if len(counts) < 2:
        return issues

    values = list(counts.values())
    if len(set(values)) > 1:
        details = ", ".join(f"{eng}={c}" for eng, c in counts.items())
        issues.append(f"  COUNT MISMATCH: {details}")

    return issues


def compare_topk(results, query_str, engines, command):
    """Compare TOP_K results across engines. Returns list of issues."""
    issues = []
    parsed = {}
    for eng in engines:
        resp = results.get(eng)
        if resp is None:
            continue
        parsed[eng] = parse_topk_response(resp)

    if len(parsed) < 2:
        return issues

    # Check result counts
    counts = {eng: len(docs) for eng, docs in parsed.items()}
    unique_counts = set(counts.values())
    if len(unique_counts) > 1:
        details = ", ".join(f"{eng}={c}" for eng, c in counts.items())
        issues.append(f"  {command} result count mismatch: {details}")

    # Check score ordering within each engine
    for eng, docs in parsed.items():
        for i in range(1, len(docs)):
            if docs[i][1] > docs[i - 1][1] + SCORE_ABS_TOLERANCE:
                issues.append(
                    f"  {eng}: scores not in descending order at rank {i}: "
                    f"{docs[i-1][1]:.6f} < {docs[i][1]:.6f}"
                )
                break

    # Cross-engine comparison: compare doc ID sets and score values
    eng_list = list(parsed.keys())
    for i in range(len(eng_list)):
        for j in range(i + 1, len(eng_list)):
            eng_a, eng_b = eng_list[i], eng_list[j]
            docs_a, docs_b = parsed[eng_a], parsed[eng_b]

            ids_a = [d[0] for d in docs_a]
            ids_b = [d[0] for d in docs_b]
            set_a = set(ids_a)
            set_b = set(ids_b)

            # Check document overlap
            if set_a and set_b:
                overlap = len(set_a & set_b)
                max_len = max(len(set_a), len(set_b))
                overlap_pct = overlap / max_len * 100 if max_len > 0 else 100

                if overlap_pct < 50:
                    issues.append(
                        f"  {eng_a} vs {eng_b}: low doc overlap "
                        f"{overlap}/{max_len} ({overlap_pct:.0f}%)"
                    )

            # Check ranking order match (only for exact doc overlap)
            if ids_a == ids_b:
                # Perfect match - also check scores
                score_mismatches = 0
                for k in range(len(docs_a)):
                    if not scores_close(docs_a[k][1], docs_b[k][1]):
                        score_mismatches += 1
                if score_mismatches > 0:
                    issues.append(
                        f"  {eng_a} vs {eng_b}: same doc order but "
                        f"{score_mismatches} score mismatches"
                    )
            elif set_a == set_b and len(set_a) > 0:
                # Same documents but different order
                # Check if reordering is due to score ties
                score_map_a = {d[0]: d[1] for d in docs_a}
                score_map_b = {d[0]: d[1] for d in docs_b}

                reorder_issues = 0
                for k in range(min(len(ids_a), len(ids_b))):
                    if ids_a[k] != ids_b[k]:
                        # Different doc at this rank - check if scores are tied
                        sa = score_map_a.get(ids_a[k], 0)
                        sb = score_map_b.get(ids_b[k], 0)
                        if not scores_close(sa, sb):
                            reorder_issues += 1
                if reorder_issues > 0:
                    issues.append(
                        f"  {eng_a} vs {eng_b}: same doc set but different order, "
                        f"{reorder_issues} non-tie reorderings"
                    )
            else:
                # Different document sets
                only_a = set_a - set_b
                only_b = set_b - set_a
                common = set_a & set_b
                # Show first few unique-to-each-side doc IDs
                sample_a = sorted(only_a)[:5]
                sample_b = sorted(only_b)[:5]
                issues.append(
                    f"  {eng_a} vs {eng_b}: {len(common)} common, "
                    f"{len(only_a)} only in {eng_a} {sample_a}, "
                    f"{len(only_b)} only in {eng_b} {sample_b}"
                )

    return issues


def read_queries(query_path):
    """Read queries from the queries file."""
    queries = []
    with open(query_path) as f:
        for line in f:
            c = json.loads(line)
            queries.append((c["query"], c.get("tags", [])))
    return queries


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 src/cross_check.py <queries.txt>")
        print("  Environment: ENGINES='eng1 eng2 ...' COMMANDS='COUNT TOP_10 ...'")
        sys.exit(1)

    query_path = sys.argv[1]
    engines = os.environ.get('ENGINES', '').split()
    if not engines:
        print("ERROR: ENGINES environment variable not set")
        sys.exit(1)

    queries = read_queries(query_path)
    print(f"Cross-checking {len(engines)} engines with {len(queries)} queries")
    print(f"Engines: {', '.join(engines)}")
    print(f"Commands: {', '.join(COMMANDS)}")
    print()

    # Start all engine processes
    clients = {}
    for eng in engines:
        print(f"Starting {eng}...")
        try:
            clients[eng] = SearchClient(eng)
        except Exception as e:
            print(f"  FAILED to start {eng}: {e}")

    if len(clients) < 2:
        print("ERROR: Need at least 2 engines for cross-checking")
        sys.exit(1)

    active_engines = list(clients.keys())
    total_issues = 0
    total_checks = 0
    issues_by_type = defaultdict(int)
    issue_details = []

    # Per-pair statistics: (eng_a, eng_b, command) -> {perfect, overlap_sum, count, ...}
    pair_stats = defaultdict(lambda: {
        "perfect": 0,      # exact same doc set and order
        "same_set": 0,     # same doc set, different order
        "overlap_sum": 0,  # sum of overlap percentages
        "overlap_count": 0,  # number of queries compared
        "count_match": 0,  # COUNT matches
        "count_total": 0,  # COUNT queries compared
    })

    for command in COMMANDS:
        print(f"\n{'='*70}")
        print(f"  Checking {command}")
        print(f"{'='*70}")

        cmd_issues = 0
        cmd_checks = 0

        for qi, (query_str, tags) in enumerate(queries):
            # Collect results from all engines
            results = {}
            for eng in active_engines:
                try:
                    results[eng] = clients[eng].query(query_str, command)
                except Exception as e:
                    results[eng] = None

            cmd_checks += 1
            total_checks += 1

            # Track per-pair overlap for TOP_K
            if command != "COUNT":
                parsed = {}
                for eng in active_engines:
                    resp = results.get(eng)
                    if resp:
                        parsed[eng] = parse_topk_response(resp)

                eng_list = list(parsed.keys())
                for i in range(len(eng_list)):
                    for j in range(i + 1, len(eng_list)):
                        ea, eb = eng_list[i], eng_list[j]
                        key = (ea, eb, command)
                        da, db = parsed[ea], parsed[eb]
                        ids_a = [d[0] for d in da]
                        ids_b = [d[0] for d in db]
                        set_a, set_b = set(ids_a), set(ids_b)
                        s = pair_stats[key]
                        s["overlap_count"] += 1
                        if set_a and set_b:
                            overlap = len(set_a & set_b)
                            max_len = max(len(set_a), len(set_b))
                            s["overlap_sum"] += overlap / max_len * 100 if max_len else 100
                        if ids_a == ids_b:
                            s["perfect"] += 1
                        elif set_a == set_b:
                            s["same_set"] += 1
            else:
                # Track COUNT pair stats
                counts = {}
                for eng in active_engines:
                    resp = results.get(eng)
                    if resp:
                        try:
                            counts[eng] = int(resp)
                        except ValueError:
                            pass
                eng_list = list(counts.keys())
                for i in range(len(eng_list)):
                    for j in range(i + 1, len(eng_list)):
                        ea, eb = eng_list[i], eng_list[j]
                        key = (ea, eb, command)
                        s = pair_stats[key]
                        s["count_total"] += 1
                        if counts[ea] == counts[eb]:
                            s["count_match"] += 1

            # Compare (for issue tracking)
            if command == "COUNT":
                issues = compare_count(results, query_str, active_engines)
            else:
                issues = compare_topk(results, query_str, active_engines, command)

            if issues:
                cmd_issues += len(issues)
                total_issues += len(issues)
                tag_str = ",".join(tags) if tags else "unknown"
                detail = f"\n[{command}] Query #{qi}: \"{query_str}\" [{tag_str}]"
                for iss in issues:
                    detail += f"\n{iss}"
                    if "MISMATCH" in iss:
                        issues_by_type["count_mismatch"] += 1
                    elif "result count" in iss:
                        issues_by_type["topk_count_mismatch"] += 1
                    elif "not in descending" in iss:
                        issues_by_type["score_ordering"] += 1
                    elif "low doc overlap" in iss:
                        issues_by_type["low_overlap"] += 1
                    elif "different order" in iss:
                        issues_by_type["reordering"] += 1
                    elif "score mismatches" in iss:
                        issues_by_type["score_value"] += 1
                    else:
                        issues_by_type["other"] += 1
                issue_details.append(detail)

            if (qi + 1) % 100 == 0:
                print(f"  ... {qi+1}/{len(queries)} queries checked, {cmd_issues} issues so far")

        status = "PASS" if cmd_issues == 0 else "FAIL"
        print(f"\n  {command}: {cmd_checks} queries checked, {cmd_issues} issues [{status}]")

    # Close all engines
    for client in clients.values():
        client.close()

    # ===== SUMMARY =====
    print(f"\n{'='*70}")
    print(f"  CROSS-CHECK SUMMARY")
    print(f"{'='*70}")
    print(f"  Engines:  {', '.join(active_engines)}")
    print(f"  Queries:  {len(queries)}")
    print(f"  Commands: {', '.join(COMMANDS)}")
    print(f"  Checks:   {total_checks}")
    print(f"  Issues:   {total_issues}")

    # ===== PER-PAIR STATISTICS TABLE =====
    print(f"\n  {'='*70}")
    print(f"  PER-PAIR STATISTICS")
    print(f"  {'='*70}")

    for command in COMMANDS:
        eng_list = active_engines
        header_printed = False
        for i in range(len(eng_list)):
            for j in range(i + 1, len(eng_list)):
                ea, eb = eng_list[i], eng_list[j]
                key = (ea, eb, command)
                s = pair_stats.get(key)
                if not s:
                    continue
                if not header_printed:
                    print(f"\n  --- {command} ---")
                    if command == "COUNT":
                        print(f"  {'Pair':<50} {'Match':>7} {'Total':>7} {'Rate':>7}")
                    else:
                        print(f"  {'Pair':<50} {'Perfect':>8} {'SameSet':>8} {'AvgOvlp':>8} {'Queries':>8}")
                    header_printed = True

                pair_label = f"{ea} vs {eb}"
                if command == "COUNT":
                    ct, cm = s["count_total"], s["count_match"]
                    rate = f"{cm/ct*100:.1f}%" if ct > 0 else "N/A"
                    print(f"  {pair_label:<50} {cm:>7} {ct:>7} {rate:>7}")
                else:
                    oc = s["overlap_count"]
                    avg_overlap = s["overlap_sum"] / oc if oc > 0 else 0
                    print(f"  {pair_label:<50} {s['perfect']:>8} {s['same_set']:>8} {avg_overlap:>7.1f}% {oc:>8}")

    if issues_by_type:
        print(f"\n  Issue breakdown:")
        for cat, cnt in sorted(issues_by_type.items(), key=lambda x: -x[1]):
            print(f"    {cat}: {cnt}")

    if issue_details:
        # Show condensed issue list
        show_n = min(30, len(issue_details))
        print(f"\n  First {show_n} issues (of {len(issue_details)} queries with issues):")
        for detail in issue_details[:show_n]:
            print(detail)

    if total_issues == 0:
        print(f"\n  *** ALL CHECKS PASSED ***")
    else:
        report_path = "cross_check_report.txt"
        with open(report_path, "w") as f:
            f.write(f"Cross-Check Report\n")
            f.write(f"Engines: {', '.join(active_engines)}\n")
            f.write(f"Commands: {', '.join(COMMANDS)}\n")
            f.write(f"Total issues: {total_issues}\n\n")
            for detail in issue_details:
                f.write(detail + "\n")
        print(f"\n  Full report written to {report_path}")

    sys.exit(0 if total_issues == 0 else 1)


if __name__ == "__main__":
    main()
