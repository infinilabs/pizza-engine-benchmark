clean:
	rm -fr idx
	rm -fr target

compile: target/release/build_index target/release/do_query

index: idx

serve: target/release/do_query
	@target/release/do_query idx

target/release/%:
	@echo "\n\n\n--- Building rucene's binary ---"
	@cargo build --release --bin $(notdir $@)

idx: target/release/build_index
	@echo "\n\n\n---- Indexing rucene ----"
	@mkdir -p idx
	export RUST_LOG=info && export RUST_BACKTRACE=1 && target/release/build_index "$@" < ${CORPUS}
