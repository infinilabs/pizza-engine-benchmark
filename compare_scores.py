#!/usr/bin/env python3
"""Compare actual BM25 scores between pizza-memory and pizza-engine-0.1."""
import subprocess, os, sys, time, json
from os import path

class SearchClient:
    def __init__(self, engine):
        self.engine = engine
        dirname = path.dirname(path.abspath(__file__))
        cwd = path.join(dirname, 'engines', engine)
        self.process = subprocess.Popen(
            ['make', '--no-print-directory', 'serve'],
            cwd=cwd, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    def query(self, q, cmd):
        line = f'CHECK_{cmd}\t{q}\n'
        self.process.stdin.write(line.encode())
        self.process.stdin.flush()
        return self.process.stdout.readline().strip().decode()

engines = ['pizza-memory', 'pizza-engine-0.1']
clients = {}
for e in engines:
    print(f"Starting {e}...", file=sys.stderr)
    clients[e] = SearchClient(e)
    time.sleep(15)
    print(f"  {e} ready", file=sys.stderr)

queries_file = 'queries.txt'
with open(queries_file) as f:
    raw_queries = [l.strip() for l in f if l.strip()]

# Parse JSON to extract query string
queries = []
for raw in raw_queries:
    obj = json.loads(raw)
    queries.append((obj['query'], obj.get('tags', [])))

# Check specific queries - mix of phrase, intersection, and union
for qi in [50, 113, 2, 5, 8, 46, 3, 6, 0]:
    if qi >= len(queries):
        continue
    q, tags = queries[qi]
    print(f'\nQuery #{qi}: {q}  tags={tags}')
    results = {}
    for e in engines:
        resp = clients[e].query(q, 'TOP_10')
        if resp:
            entries = resp.split(',')
            results[e] = {}
            for entry in entries:
                doc_id, score = entry.split(':')
                results[e][int(doc_id)] = float(score)
            print(f'  {e}:')
            for entry in entries[:5]:
                print(f'    {entry}')

    # Find common docs and compare scores
    if len(results) == 2:
        e1, e2 = engines
        common = set(results[e1].keys()) & set(results[e2].keys())
        if common:
            print(f'  Common docs ({len(common)}):')
            for doc_id in sorted(common):
                s1 = results[e1][doc_id]
                s2 = results[e2][doc_id]
                diff = abs(s1 - s2)
                rel = diff / max(abs(s1), abs(s2), 1e-10) * 100
                marker = ' ***' if rel > 1.0 else ''
                print(f'    doc {doc_id}: {e1}={s1:.6f} {e2}={s2:.6f} diff={diff:.6f} ({rel:.2f}%){marker}')

for c in clients.values():
    c.process.terminate()
