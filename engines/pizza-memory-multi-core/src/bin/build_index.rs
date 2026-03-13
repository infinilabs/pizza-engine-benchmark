//! Index builder for pizza-memory: builds the full in-memory index from
//! corpus JSON and persists it as a snapshot directory for fast loading.
//!
//! Usage: build_index <idx_dir> < corpus.json
//!        CORPUS=/path/to/corpus.json build_index <idx_dir> < /dev/null
//!
//! The snapshot directory (`idx/snapshot/`) contains per-epoch binary files
//! that `do_query` can load in seconds without re-indexing.

use pizza_engine::context::Context;
use pizza_engine::document::{Property, Schema};
use pizza_engine::store::MemoryStore;
use pizza_engine::traits::StoreWriter;

use serde::Deserialize;
use std::env;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Instant;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn create_schema() -> Schema {
    let mut schema = Schema::new();
    schema
        .add_property("text", Property::as_text(Some("standard")))
        .unwrap();
    schema.freeze();
    schema
}

#[derive(Deserialize)]
struct InputDocument {
    #[serde(default)]
    text: Option<String>,
}

/// Dump per-epoch snapshot: meta.dat + term_dict.bin + epoch_N.bin files.
fn dump_to_dir(store: &MemoryStore, snapshot_dir: &Path) {
    let start = Instant::now();
    if let Some((meta_json, files)) = store.dump_epoch_snapshot_files("text") {
        std::fs::create_dir_all(snapshot_dir).expect("create snapshot dir");

        let mut total_bytes: usize = 0;
        for (name, data) in &files {
            let p = snapshot_dir.join(name);
            std::fs::write(&p, data).expect("write snapshot file");
            total_bytes += data.len();
        }

        let meta_path = snapshot_dir.join("meta.dat");
        std::fs::write(&meta_path, &meta_json).expect("write meta.dat");
        total_bytes += meta_json.len();

        eprintln!(
            "Dumped snapshot to {} ({} files, {:.1} MB total, {:.2}s)",
            snapshot_dir.display(),
            files.len(),
            total_bytes as f64 / (1024.0 * 1024.0),
            start.elapsed().as_secs_f64(),
        );
    } else {
        eprintln!("Warning: could not dump snapshot (field 'text' not found or not epoch)");
    }
}

// ---------------------------------------------------------------------------
// Build from corpus
// ---------------------------------------------------------------------------

fn build_from_corpus(corpus_path: &str, idx_dir: &Path) {
    let schema = create_schema();
    let ctx = Arc::new(Context::new(schema.clone()));

    // Extract field_id and field_schema once up front
    let field_schema = schema.get_property("text").expect("text field in schema").clone();
    let field_id = field_schema.field_id().expect("schema not frozen");

    let mut store = MemoryStore::new_epoch();
    store.open(&schema).unwrap();

    // Enable bulk mode for faster DatTermDict insertions
    store.enable_bulk_mode(0, 0);

    eprintln!("Reading corpus from: {}", corpus_path);
    let file = std::fs::File::open(corpus_path).expect("open corpus file");
    let reader = BufReader::with_capacity(4 << 20, file);

    let start = Instant::now();
    let batch_size = 100_000;

    // Text buffer arena: accumulate all batch texts in a single contiguous
    // String.  Avoids per-doc String alloc/free + enables batch lowercase.
    let mut text_buf = String::with_capacity(batch_size * 1500);
    // (doc_id, start_offset, end_offset) into text_buf
    let mut offsets: Vec<(u32, u32, u32)> = Vec::with_capacity(batch_size);

    let mut doc_id: u32 = 1;
    let mut total = 0u32;
    let mut json_parse_ns: u128 = 0;
    let mut index_ns: u128 = 0;

    for line in reader.lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => continue,
        };
        if line.trim().is_empty() {
            continue;
        }

        let t0 = Instant::now();
        let input_doc: InputDocument = match serde_json::from_str(&line) {
            Ok(d) => d,
            Err(_) => continue,
        };
        let text = input_doc.text.unwrap_or_default();
        json_parse_ns += t0.elapsed().as_nanos();

        let s = text_buf.len() as u32;
        text_buf.push_str(&text);
        let e = text_buf.len() as u32;
        offsets.push((doc_id, s, e));
        doc_id += 1;

        if offsets.len() >= batch_size {
            let t1 = Instant::now();
            // Batch-normalize: lowercase the entire buffer in one shot.
            // SAFETY: make_ascii_lowercase only changes A-Z → a-z bytes,
            // which preserves valid UTF-8.
            unsafe { text_buf.as_bytes_mut().make_ascii_lowercase(); }

            let refs: Vec<(u32, &str)> = offsets
                .iter()
                .map(|&(id, s, e)| (id, &text_buf[s as usize..e as usize]))
                .collect();
            store.bulk_index_raw_text_prenormalized(
                &ctx, "text", field_id, &field_schema, &refs,
            );
            index_ns += t1.elapsed().as_nanos();

            text_buf.clear();
            offsets.clear();
            total += batch_size as u32;
            if total % 500_000 == 0 {
                eprintln!(
                    "  loaded {} docs  (json_parse: {:.2}s, index: {:.2}s, wall: {:.2}s)",
                    total,
                    json_parse_ns as f64 / 1e9,
                    index_ns as f64 / 1e9,
                    start.elapsed().as_secs_f64(),
                );
            }
        }
    }

    // Flush remaining
    if !offsets.is_empty() {
        total += offsets.len() as u32;
        let t1 = Instant::now();
        unsafe { text_buf.as_bytes_mut().make_ascii_lowercase(); }
        let refs: Vec<(u32, &str)> = offsets
            .iter()
            .map(|&(id, s, e)| (id, &text_buf[s as usize..e as usize]))
            .collect();
        store.bulk_index_raw_text_prenormalized(
            &ctx, "text", field_id, &field_schema, &refs,
        );
        index_ns += t1.elapsed().as_nanos();
    }

    // Finalise bulk mode: flush HashMap write cache into Cedar trie
    let t_flush = Instant::now();
    store.finish_bulk_mode();
    let flush_ms = t_flush.elapsed().as_millis();

    // Dump snapshot (must happen BEFORE compact — compact drops epoch data).
    let snapshot_dir = idx_dir.join("snapshot");
    dump_to_dir(&store, &snapshot_dir);

    // Also save the corpus path for reference
    let path_file = idx_dir.join("corpus_path.txt");
    std::fs::write(&path_file, corpus_path).expect("write corpus_path.txt");

    store.flush().unwrap();

    eprintln!(
        "Built index: {} docs in {:.2}s  (json_parse: {:.2}s, index: {:.2}s, cedar_flush: {}ms)",
        total,
        start.elapsed().as_secs_f64(),
        json_parse_ns as f64 / 1e9,
        index_ns as f64 / 1e9,
        flush_ms,
    );
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("Usage: build_index <idx_dir> < corpus.json");
        eprintln!("   or: CORPUS=/path/to/corpus.json build_index <idx_dir> < /dev/null");
        std::process::exit(1);
    }
    let idx_dir = PathBuf::from(&args[1]);
    std::fs::create_dir_all(&idx_dir).expect("create idx dir");

    // Determine corpus path: CORPUS env var, or drain stdin into idx/corpus.json
    let corpus_path = if let Ok(p) = std::env::var("CORPUS") {
        // Drain stdin so pipe doesn't block
        let stdin = std::io::stdin();
        let reader = BufReader::new(stdin.lock());
        let mut count = 0u32;
        for line in reader.lines() {
            if line.is_ok() {
                count += 1;
            }
        }
        if count > 0 {
            eprintln!("Drained {} lines from stdin", count);
        }
        p
    } else {
        // Read from stdin and save to idx/corpus.json
        eprintln!("CORPUS env var not set; saving stdin to idx/corpus.json");
        let stdin = std::io::stdin();
        let reader = BufReader::with_capacity(4 << 20, stdin.lock());
        let out_path = idx_dir.join("corpus.json");
        let mut out = std::io::BufWriter::new(
            std::fs::File::create(&out_path).expect("create corpus.json"),
        );
        let mut count = 0u32;
        for line in reader.lines() {
            if let Ok(l) = line {
                use std::io::Write;
                out.write_all(l.as_bytes()).unwrap();
                out.write_all(b"\n").unwrap();
                count += 1;
            }
        }
        eprintln!("Saved {} lines to idx/corpus.json", count);
        out_path.to_string_lossy().to_string()
    };

    // Build the full index and persist snapshot
    build_from_corpus(&corpus_path, &idx_dir);
}
