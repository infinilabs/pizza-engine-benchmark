clean:
	rm -fr idx
	rm -fr build

compile: build

serve:
		@java -cp build/libs/search-index-benchmark-game-lucene-1.0-SNAPSHOT-all.jar DoQuery idx

# ------------------------
index: idx

build:
	gradle clean shadowJar

idx: build
	@echo "---- Indexing Lucene ----"
	java -server -cp build/libs/search-index-benchmark-game-lucene-1.0-SNAPSHOT-all.jar BuildIndex idx < $(CORPUS)
