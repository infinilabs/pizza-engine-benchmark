CORPUS = /home/paul/git/search-index-benchmark-game/corpus10000.json
export

ENGINE = lucene tantivy

QUERY_RESULTS = $(addsuffix /query, $(ENGINE))

all: index

clean:
	for engine in $(ENGINE); do cd ${shell pwd}/engines/$$engine && make clean ; done

# Target to build the indexes of
# all of the search engine
index: $(INDEX_DIRECTORIES)
	for engine in $(ENGINE); do cd ${shell pwd}/engines/$$engine && make index ; done

# Target to run the query benchmark for
# all of the search engines
query: $(QUERY_RESULTS)

%/query:
	bash ./run_bench.sh $(dir $@) $@
