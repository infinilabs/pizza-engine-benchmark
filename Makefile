CORPUS = /home/paul/git/search-index-benchmark-game/corpus10000.json
export

ENGINE = lucene tantivy

QUERY_RESULTS = $(addprefix results/, $(ENGINE))

all: index

clean:
	rm -fr results
	for engine in $(ENGINE); do cd ${shell pwd}/engines/$$engine && make clean ; done

# Target to build the indexes of
# all of the search engine
index: $(INDEX_DIRECTORIES)
	for engine in $(ENGINE); do cd ${shell pwd}/engines/$$engine && make index ; done

# Target to run the query benchmark for
# all of the search engines
bench: index compile
	@rm -fr results
	@mkdir results
	for engine in $(ENGINE); do python3 src/client.py COUNT queries.txt $$engine; done

compile:
	for engine in $(ENGINE); do cd ${shell pwd}/engines/$$engine && make compile ; done
