//! Index builder for pizza-memory: all docs in a single MemoryStore.
//!
//! Usage: build_index <idx_dir> < corpus.json
//!
//! Since MemoryStore is purely in-memory (no disk serialisation), the
//! "index" step saves a pointer to the corpus so that `do_query` can
//! read the original JSON directly without an intermediate format.
//!
//! We store the absolute path to the corpus in `idx/corpus_path.txt`
//! so do_query knows where to find it.

use std::env;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("Usage: build_index <idx_dir> < corpus.json");
        std::process::exit(1);
    }
    let idx_dir = PathBuf::from(&args[1]);
    std::fs::create_dir_all(&idx_dir).expect("Failed to create idx dir");

    // Count lines from stdin to verify corpus, and detect path from /dev/stdin
    // Since stdin is piped from the corpus, we just count docs and record the
    // corpus path from the CORPUS env var.
    let corpus_path = std::env::var("CORPUS").unwrap_or_else(|_| {
        // Fallback: read from stdin and save as corpus.json in idx_dir
        eprintln!("CORPUS env var not set; saving stdin to idx/corpus.json");
        let stdin = std::io::stdin();
        let reader = BufReader::with_capacity(4 << 20, stdin.lock());
        let out_path = idx_dir.join("corpus.json");
        let mut out = std::fs::File::create(&out_path).expect("create corpus.json");
        let mut count = 0u32;
        for line in reader.lines() {
            if let Ok(l) = line {
                out.write_all(l.as_bytes()).unwrap();
                out.write_all(b"\n").unwrap();
                count += 1;
            }
        }
        eprintln!("Saved {} lines to idx/corpus.json", count);
        out_path.to_string_lossy().to_string()
    });

    // If CORPUS is set, just consume stdin (Makefile pipes it) and record path
    if std::env::var("CORPUS").is_ok() {
        // Drain stdin so the pipe doesn't block
        let stdin = std::io::stdin();
        let reader = BufReader::with_capacity(4 << 20, stdin.lock());
        let mut count = 0u32;
        for line in reader.lines() {
            if line.is_ok() {
                count += 1;
            }
        }
        eprintln!("Verified {} lines from corpus", count);

        // Save absolute path
        let path_file = idx_dir.join("corpus_path.txt");
        std::fs::write(&path_file, &corpus_path).expect("write corpus_path.txt");
        eprintln!("Saved corpus path: {}", corpus_path);
    }
}
