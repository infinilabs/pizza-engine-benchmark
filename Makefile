CORPUS = /home/paul/git/search-index-benchmark-game/corpus.json
export

COMMANDS = COUNT NO_SCORE TOP_10
ENGINES = lucene tantivy

all: index

clean:
	rm -fr results
	for engine in $(ENGINES); do cd ${shell pwd}/engines/$$engine && make clean ; done

# Target to build the indexes of
# all of the search engine
index: $(INDEX_DIRECTORIES)
	for engine in $(ENGINES); do cd ${shell pwd}/engines/$$engine && make index ; done

# Target to run the query benchmark for
# all of the search engines
bench: index compile
	@rm -fr results
	@mkdir results
	python3 src/client.py queries.txt $(ENGINES)

compile:
	for engine in $(ENGINES); do cd ${shell pwd}/engines/$$engine && make compile ; done
