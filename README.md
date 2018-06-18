# Search Index Benchmark Game

A set of standardized benchmarks for comparing the speed of various aspects of search engine technologies.

This is useful both for comparing different libraries and as tooling for more easily and comprehensively
 comparing versions of the same technology.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine.

### Prerequisites

The lucene benchmarks requires Gradle. This can be installed from [the Gradle website](https://gradle.org/).

The tantivy benchmarks and benchmark driver code requires Cargo. This can be installed using [rustup](https://www.rustup.rs/).

### Installing

Clone this repo.

```
git clone git@github.com:jason-wolfe/search-index-benchmark-game.git
```

## Running

Run `make bench` to build the different project and run the benches.

```
./run_all.sh ./common/datasets/minimal.json ./common/queries
```

The results are available in the `results` directory.


## Adding another engine

Currently only tantivy and lucene are supported, but you can add another search
engine by creating a directory in the engines directory and add a `Makefile`
implementing the following commands

- clean
- index
- serve
