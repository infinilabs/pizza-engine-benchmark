clean:
	@rm -fr idx

serve:
	@java -XX:+UseParallelGC -cp "${shell pwd}/../lucene-9.8.0/build/libs/search-index-benchmark-game-lucene-1.0-SNAPSHOT.jar:${shell pwd}/../lucene-9.8.0/build/dependencies/*" DoQuery idx

index: idx

compile:
	cd ${shell pwd}/../lucene-9.8.0 && make compile

idx: compile
	cd ${shell pwd}/../lucene-9.8.0 && make index
	@echo "--- Reordering index with Lucene 9.8.0 ---"
	@java -server -cp "${shell pwd}/../lucene-9.8.0/build/libs/search-index-benchmark-game-lucene-1.0-SNAPSHOT.jar:${shell pwd}/../lucene-9.8.0/build/dependencies/*" ReorderIndex ${shell pwd}/../lucene-9.8.0/idx idx
