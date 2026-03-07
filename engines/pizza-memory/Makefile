clean:
	rm -fr idx
	rm -fr target

compile: target/release/build_index target/release/do_query

index: idx

serve: target/release/do_query
	@RUST_BACKTRACE=1 target/release/do_query idx

target/release/%:
	@echo "\n\n\n--- Building pizza-memory binary ---"
	@RUSTFLAGS='-C target-cpu=native' cargo build --release --bin $(notdir $@)

idx: target/release/build_index
	@echo "\n\n\n---- Indexing pizza-memory ----"
	@mkdir -p idx
	CORPUS=${CORPUS} target/release/build_index idx < ${CORPUS}
