
# Welcome to Search Benchmark, the Game!

This repository is standardized benchmark for comparing the speed of various
aspects of search engine technologies. forked from [here](https://github.com/quickwit-oss/search-benchmark-game).

This benchmark is both
- **for users** to make it easy for users to compare different libraries
- **for library** developers to identify optimization opportunities by comparing
their implementation to other implementations.

Currently, the benchmark only includes Lucene, Tantivy and Pizza-Engine(FIRE).
It is reasonably simple to add another engine.

You are free to communicate about the results of this benchmark **in
a reasonable manner**.
For instance, twisting this benchmark in marketing material to claim that your search engine is 31x faster than Lucene,
because your product was 31x on one of the test is not tolerated. If this happens, the benchmark will publicly
host a wall of shame.
Bullshit claims about performance are a plague in the database world.

Please note that this benchmark is highly biased and may not accurately reflect fair or objective performance.

## The benchmark

Different search engine implementation are benched over different real-life tests.
The corpus used is the English wikipedia. Stemming is disabled. Queries have been derived
 from the [AOL query dataset](https://en.wikipedia.org/wiki/AOL_search_data_leak)
 (but do not contain any personal information).

Out of a random sample of query, we filtered queries that had at least two terms and yield at least 1 hit when searches as
a phrase query.

For each of these query, we then run them as :
- `intersection`
- `unions`
- `phrase queries`

with the following collection options :
- `COUNT` only count documents, no need to score them
- `TOP 10` : Identify the 10 documents with the best BM25 score.
- `TOP 10 + COUNT`: Identify the 10  documents with the best BM25 score, and count the matching documents.

We also reintroduced artificially a couple of term queries with different term frequencies.

All tests are run once in order to make sure that
- all of the data is loaded and in page cache
- Java's JIT already kicked in.

Test are run in a single thread.
Out of 10 runs, we only retain the best score, so Garbage Collection likely does not matter.

### Benchmark environment

The results file that is included in this repository was generated using the following benchmark
environment:

```
Software:

    System Software Overview:

      System Version: macOS 14.4.1 (23E224)
      Kernel Version: Darwin 23.4.0
      Boot Volume: Macintosh HD
      Boot Mode: Normal
      Computer Name: INFINI
      User Name: Medcl (medcl)
      Secure Virtual Memory: Enabled
      System Integrity Protection: Enabled
      Time since boot: 5 days, 14 hours, 59 minutes

Hardware:

    Hardware Overview:

      Model Name: MacBook Air
      Model Identifier: Mac14,2
      Model Number: Z1610002HCH/A
      Chip: Apple M2
      Total Number of Cores: 8 (4 performance and 4 efficiency)
      Memory: 24 GB
      System Firmware Version: 10151.101.3
      OS Loader Version: 10151.101.3
      Serial Number (system): CK2Y75LF2W
      Hardware UUID: 2EFC98B8-5AAA-5F5A-964B-2F19DD8A2EB2
      Provisioning UDID: 00008112-001E45D63621401E
      Activation Lock Status: Enabled

JAVA:
    openjdk 17.0.5 2022-10-18 LTS
    OpenJDK Runtime Environment Zulu17.38+21-CA (build 17.0.5+8-LTS)
    OpenJDK 64-Bit Server VM Zulu17.38+21-CA (build 17.0.5+8-LTS, mixed mode, sharing)

Rust:
    rustc 1.80.0-nightly (72fdf913c 2024-06-05)
```


## Engine specific detail

### Lucene

- Query cache is disabled.
- GC should not influence the results as we pick the best out of 5 runs.
- The `-bp` variant implements document reordering via the bipartite graph partitioning algorithm, also called recursive graph bisection.

### Tantivy

- Tantivy returns slightly more results because its tokenizer handles apostrophes differently.
- Tantivy and Lucene both use BM25 and should return almost identical scores.


# Reproducing

These instructions will get you a copy of the project up and running on your local machine.

### Prerequisites

The lucene benchmarks requires Java, the most recent version is recommended.
The tantivy benchmarks and benchmark driver code requires Cargo. This can be installed using [rustup](https://www.rustup.rs/).

### Installing

Clone this repo.

```
git clone git@github.com:infinilabs/search-benchmark-game.git
```

## Running

Checkout the [Makefile](Makefile) for all available commands. You can adjust the `ENGINES` parameter for a different set of engines.

Run `make corpus` to download and unzip the corpus used in the benchmark.
```
make corpus
```

Run `make index` to create the indices for the engines.

```
make index
```

Run `make bench` to build the different project and run the benches.
This command may take more than 30mn.

```
make bench
```

Or you can run the benchmark for a specific engine:

```
ENGINES=pizza-engine-0.1 make quick-bench
```

Or you can run the benchmark for a specific test:

```
COMMANDS=TOP_10 ENGINES="lucene-9.9.2-bp tantivy-0.22" make quick-bench
```

The results are outputted in a `results.json` file.

You can then check your results out by running:

```
make serve
```

And open the following in your browser: [http://localhost:8000/](http://localhost:8000/)


# Adding another search engine

See `CONTRIBUTE.md`.
