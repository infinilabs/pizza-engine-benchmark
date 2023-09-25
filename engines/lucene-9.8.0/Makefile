clean:
	@echo "--- Cleaning Lucene 9.8.0 ---"
	@rm -fr idx idx-reordered
	@rm -fr build

serve:
	@java -XX:+UseParallelGC -cp "build/libs/search-index-benchmark-game-lucene-1.0-SNAPSHOT.jar:build/dependencies/*" DoQuery idx-reordered

index: idx-reordered

compile:
	@echo "--- Building Lucene 9.8.0"
	@./gradlew clean build copyDependencies

idx: compile
	@echo "--- Indexing Lucene 9.8.0 ---"
	@java -server -cp "build/libs/search-index-benchmark-game-lucene-1.0-SNAPSHOT.jar:build/dependencies/*" BuildIndex idx < $(CORPUS)

idx-reordered: compile idx
	@echo "--- Reordering index Lucene 9.8.0 ---"
	@java -server -cp "build/libs/search-index-benchmark-game-lucene-1.0-SNAPSHOT.jar:build/dependencies/*" ReorderIndex idx idx-reordered
