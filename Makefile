CORPUS = `pwd`/wiki-articles.json
export

COMMANDS = COUNT NO_SCORE TOP_10
ENGINES = `ls engines`

all: index

corpus.json:
    echo "Download corpus.json from https://www.dropbox.com/s/wwnfnu441w1ec9p/wiki-articles.json.bz2?dl=0"

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

serve:
	cp results.json web/output/results.json 
	cd web/output && python -m SimpleHTTPServer 8000
