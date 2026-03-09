JAVA21=/opt/homebrew/opt/openjdk@21/bin/java

clean:
	@rm -fr idx

serve:
	@$(JAVA21) -XX:+UseParallelGC -cp "../lucene-10.4/build/libs/search-index-benchmark-game-lucene-1.0-SNAPSHOT.jar:../lucene-10.4/build/dependencies/*" DoQuery idx

index: idx

compile:
	cd ${shell pwd}/../lucene-10.4 && make compile

idx: compile
	cd ${shell pwd}/../lucene-10.4 && make index
	@echo "--- Reordering index with Lucene 10.4 ---"
	@$(JAVA21) -server -cp "${shell pwd}/../lucene-10.4/build/libs/search-index-benchmark-game-lucene-1.0-SNAPSHOT.jar:${shell pwd}/../lucene-10.4/build/dependencies/*" ReorderIndex ${shell pwd}/../lucene-10.4/idx idx
