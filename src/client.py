import subprocess
import os
from os import path
import time
import json
import random
import glob
import sys
from collections import defaultdict

COMMANDS = os.environ.get('COMMANDS', '').split(' ')

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

    def query(self, query, command):
        query_line = f"{command}\t{query}\n"
        self.process.stdin.write(query_line.encode("utf-8"))
        self.process.stdin.flush()
        recv = self.process.stdout.readline().strip()
        if recv == b"UNSUPPORTED":
            return None
        cnt = int(recv)
        return cnt

    def close(self):
        self.process.stdin.close()
        self.process.stdout.close()

def drive(queries, client, command):
    for query in queries:
        start = time.monotonic()
        count = client.query(query.query, command)
        stop = time.monotonic()
        duration = int((stop - start) * 1e6)
        yield (query, count, duration)

class Query:
    def __init__(self, query, tags):
        self.query = query
        self.tags = tags

def read_queries(query_path):
    with open(query_path) as f:
        for q in f:
            c = json.loads(q)
            yield Query(c["query"], c["tags"])

def printProgressBar(progress, prefix='', suffix='', decimals=1, length=100, fill='█', printEnd="\r"):
    percent = ("{0:." + str(decimals) + "f}").format(100 * progress)
    filledLength = int(length * progress)
    bar = fill * filledLength + '-' * (length - filledLength)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end=printEnd)
    if progress >= 1:
        print()

NUM_ITER = 10

def save_engine_results(engine, command, engine_results):
    results_dir = 'results'
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    filename = path.join(results_dir, f"{engine}#{command}_results.json")
    with open(filename, 'w') as f:
        json.dump(engine_results, f)

def load_engine_results():
    all_results = defaultdict(lambda: defaultdict(list))
    results_dir = 'results'
    for result_file in glob.glob(path.join(results_dir, "*_results.json")):
        try:
            engine_command, _ = path.basename(result_file).rsplit('_', 1)
            engine, command = engine_command.split('#', 1)
            with open(result_file, 'r') as f:
                engine_results = json.load(f)
                all_results[command][engine] = engine_results
        except ValueError as e:
            print(f"Skipping file {result_file}: {e}")
    return all_results

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python script.py <query_path> <warmup_time_seconds> <engine1> [<engine2> ...]")
        sys.exit(1)

    random.seed(2)
    query_path = sys.argv[1]
    WARMUP_TIME = int(sys.argv[2])
    engines = sys.argv[3:]
    queries = list(read_queries(query_path))
    results = load_engine_results()

    for command in COMMANDS:
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

            print("======================")
            print(f"BENCHMARKING {engine} {command}")
            search_client = SearchClient(engine)
            queries_shuffled = list(queries[:])
            random.seed(2)
            random.shuffle(queries_shuffled)
            warmup_start = time.monotonic()
            printProgressBar(0, prefix='Warmup:', suffix='Complete', length=50)
            while True:
                for _ in drive(queries_shuffled, search_client, command):
                    pass
                progress = min(1, (time.monotonic() - warmup_start) / WARMUP_TIME)
                printProgressBar(progress, prefix='Warmup:', suffix='Complete', length=50)
                if progress == 1:
                    break
            printProgressBar(0, prefix='Run:   ', suffix='Complete', length=50)
            for i in range(NUM_ITER):
                for query, count, duration in drive(queries_shuffled, search_client, command):
                    if count is None:
                        query_idx[query.query] = {"count": -1, "duration": []}
                    else:
                        query_idx[query.query]["count"] = count
                        query_idx[query.query]["duration"].append(duration)
                printProgressBar(float(i + 1) / NUM_ITER, prefix='Run:   ', suffix='Complete', length=50)
            for query in engine_results:
                query["duration"].sort()

            save_engine_results(engine, command, engine_results)
            search_client.close()
            results[command][engine] = engine_results

    with open("results.json", "w") as f:
        json.dump(results, f, indent=2)
