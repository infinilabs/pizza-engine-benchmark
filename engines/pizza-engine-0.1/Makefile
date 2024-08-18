clean:
	rm -fr idx
	rm -fr target

compile: target/release/build_index target/release/do_query

index: idx

serve: target/release/do_query
	@RUST_BACKTRACE=1 target/release/do_query idx

target/release/%:
	@echo "\n\n\n--- Building pizza's binary ---"
	@RUSTFLAGS='-C target-cpu=native' cargo build --release --bin $(notdir $@)

idx: target/release/build_index
	@echo "\n\n\n---- Indexing pizza ----"
	@mkdir -p idx
	export RUST_LOG=info && target/release/build_index "$@" < ${CORPUS}
	#target/release/build_index "$@" < ${CORPUS}
