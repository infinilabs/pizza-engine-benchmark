import subprocess
import os
from os import path
import time
import json
import random
from collections import defaultdict

random.seed(2)


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

NUM_ITER = 15

class Result:
    pass


if __name__ == "__main__":
    import sys
    (command, query_path, engines) = sys.argv[1:]
    assert command in ("COUNT", "NO_SCORE", "TOP_10")
    engines = engines.split(",")
    queries = list(read_queries(query_path))[:10]
    random.shuffle(queries)
    for engine in engines:
        engine_results = defaultdict(list)
        print("\n\n\n======================")
        print("BENCHMARKING %s" % engine)
        search_client = SearchClient("lucene")
        print("- Warming up ...")
        for _ in drive(queries, search_client, command=command):
            pass
        for i in range(NUM_ITER):
            print("- Run #%s of %s" % (i + 1, NUM_ITER))
            for (query, count, duration) in drive(queries, search_client):
                if query.query not in engine_results:
                    engine_results[query.query] = {
                        "tags": query.tags,
                        "count": count,
                        "duration": []
                    }
                engine_results[query.query]["duration"].append(duration)
        with open("results/%s_%s.json" % (engine, command), "w") as f:
            json.dump(engine_results, f, default=lambda obj: obj.__dict__)
