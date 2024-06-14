CORPUS := $(shell pwd)/corpus.json
export

WIKI_SRC = "https://www.dropbox.com/s/wwnfnu441w1ec9p/wiki-articles.json.bz2"

COMMANDS ?=  TOP_100 TOP_100_COUNT COUNT

# ENGINES ?= tantivy-0.13 lucene-8.4.0 pisa-0.8.2 rucene-0.1 bleve-0.8.0-scorch rucene-0.1 tantivy-0.11 tantivy-0.14 tantivy-0.15 tantivy-0.16 tantivy-0.17 tantivy-0.18 tantivy-0.19
# ENGINES ?= tantivy-0.16 lucene-8.10.1 pisa-0.8.2 bleve-0.8.0-scorch bluge-0.2.2 rucene-0.1
# ENGINES ?= tantivy-0.16 tantivy-0.17 tantivy-0.18 tantivy-0.19
ENGINES ?= lucene-9.9.2-bp tantivy-0.22 
#ENGINES ?= lucene-9.9.2-bp tantivy-0.22 pizza-0.1
#ENGINES ?= pizza-0.1
PORT ?= 8080

help:
	@grep '^[^#[:space:]].*:' Makefile

all: index

corpus:
	@echo "--- Downloading $(WIKI_SRC) ---"
	@curl -# -L "$(WIKI_SRC)" | bunzip2 -c | python3 corpus_transform.py > $(CORPUS)

clean:
	@echo "--- Cleaning directories ---"
	@rm -fr results
	@for engine in $(ENGINES); do cd ${shell pwd}/engines/$$engine && make clean ; done

index:
	@echo "--- Indexing corpus ---"
	@for engine in $(ENGINES); do cd ${shell pwd}/engines/$$engine && make index ; done

bench:
	@echo "--- Benchmarking ---"
	@rm -fr results
	@mkdir results
	@python3 src/client.py queries.txt $(ENGINES)

compile:
	@echo "--- Compiling binaries ---"
	@for engine in $(ENGINES); do cd ${shell pwd}/engines/$$engine && make compile ; done

serve:
	@echo "--- Serving results ---"
	@cp results.json web/build/results.json
	@cd web/build && python3 -m http.server $(PORT)
