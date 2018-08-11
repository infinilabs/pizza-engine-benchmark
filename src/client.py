import subprocess
import os
from os import path
import time
import json
import random
from collections import defaultdict

COMMANDS = ["COUNT", "TOP_10", "TOP_10_COUNT"]
# COMMANDS = ["COUNT"]

class SearchClient:

    def __init__(self, engine):
        self.engine = engine
        dirname = os.path.split(os.path.abspath(__file__))[0]
        dirname = path.dirname(dirname)
        dirname = path.join(dirname, "engines")
        cwd = path.join(dirname, engine)
        print(cwd)
        self.process = subprocess.Popen(["make", "--no-print-directory", "serve"],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE)

    def query(self, query, command="COUNT"):
        query_line = "%s\t%s\n" % (command, query)
        self.process.stdin.write(query_line.encode("utf-8"))
        self.process.stdin.flush()
        recv = self.process.stdout.readline()
        return int(recv)

def drive(queries, client, command="COUNT"):
    for query in queries:
        start = time.monotonic()
        count = client.query(query.query, command=command)
        stop = time.monotonic()
        duration = int((stop - start) * 1e6)
        yield (query, count, duration)

class Query(object):
    def __init__(self, query, tags):
        self.query = query
        self.tags = tags

def read_queries(query_path):
    for q in open(query_path):
        c = json.loads(q)
        yield Query(c["query"], c["tags"])

WARMUP_ITER = 1
NUM_ITER = 100


if __name__ == "__main__":
    import sys
    random.seed(2)
    query_path = sys.argv[1]
    engines = sys.argv[2:]
    queries = list(read_queries(query_path))
    results = {}
    for command in COMMANDS:
        results_commands = {}
        for engine in engines:
            engine_results = []
            query_idx = {}
            for query in queries:
                query_result = {
                    "query": query.query,
                    "tags": query.tags,
                    "count": 0,
                    "duration": []
                }
                query_idx[query.query] = query_result
                engine_results.append(query_result)
            print("\n\n\n======================")
            print("BENCHMARKING %s" % engine)
            search_client = SearchClient(engine)
            print("- Warming up ...")
            queries_shuffled = list(queries[:])
            random.seed(2)
            random.shuffle(queries_shuffled)
            for i in range(WARMUP_ITER):
                for _ in drive(queries_shuffled, search_client, command=command):
                    pass
            for i in range(NUM_ITER):
                print("- Run #%s of %s" % (i + 1, NUM_ITER))
                for (query, count, duration) in drive(queries_shuffled, search_client):
                    query_idx[query.query]["count"] = count
                    query_idx[query.query]["duration"].append(duration)
            for query in engine_results:
                query["duration"].sort()
            results_commands[engine] = engine_results
        print(results_commands.keys())
        results[command] = results_commands
    with open("results.json" , "w") as f:
        json.dump(results, f, default=lambda obj: obj.__dict__)
