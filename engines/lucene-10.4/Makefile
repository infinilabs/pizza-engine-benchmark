JAVA21=/opt/homebrew/opt/openjdk@21/bin/java

clean:
	@echo "--- Cleaning Lucene 10.4 ---"
	@rm -fr idx
	@rm -fr build

serve:
	@$(JAVA21) -XX:+UseParallelGC -cp "build/libs/search-index-benchmark-game-lucene-1.0-SNAPSHOT.jar:build/dependencies/*" DoQuery idx

index: idx

compile:
	@echo "--- Building Lucene 10.4"
	@JAVA_HOME=/opt/homebrew/opt/openjdk@21 ./gradlew clean build copyDependencies

idx: compile
	@echo "--- Indexing Lucene 10.4 ---"
	@$(JAVA21) -server -cp "build/libs/search-index-benchmark-game-lucene-1.0-SNAPSHOT.jar:build/dependencies/*" BuildIndex idx < $(CORPUS)
