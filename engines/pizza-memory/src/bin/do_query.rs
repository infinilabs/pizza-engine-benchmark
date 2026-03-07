//! Query a pizza-engine MemoryStore for the search benchmark game.
//!
//! Usage: do_query <idx_dir>
//!
//! Reads the corpus JSON directly and bulk-creates docs into a raw
//! MemoryStore (bypassing Engine/Writer to avoid epoch management
//! overhead), then serves query commands from stdin.
//!
//! This tests pure in-memory mutable index search performance — all 5M
//! docs live in a single MemoryStore with InMemoryInvertIndex.

use pizza_engine::context::Context;
use pizza_engine::document::{DocID, DraftDoc, FieldValue, Property, Schema};
use pizza_engine::search::iterator::CombinationStrategy;
use pizza_engine::search::query::{Operator, TrackTotalHits};
use pizza_engine::search::{OriginalQuery, QueryContext, Searcher};
use pizza_engine::store::MemoryStore;
use pizza_engine::traits::{StoreReader, StoreWriter};

use serde::Deserialize;
use std::env;
use std::io::{self, BufRead, BufReader, Write};
use std::path::Path;
use std::sync::Arc;
use std::time::Instant;

use spin::RwLock;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn write_line(s: &str) {
    let stdout = io::stdout();
    let mut out = stdout.lock();
    if writeln!(out, "{}", s).is_err() {
        std::process::exit(0);
    }
}

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

/// Load docs from corpus JSON directly into a raw MemoryStore
/// (bypasses Engine/Writer to avoid epoch freeze overhead).
fn load_corpus(idx_dir: &Path) -> (MemoryStore, Arc<Context>) {
    let snapshot_dir = idx_dir.join("snapshot");
    let meta_path = snapshot_dir.join("meta.dat");

    // ── Fast path: load from snapshot directory ───────────────────
    if meta_path.exists() {
        return load_from_snapshot(&snapshot_dir);
    }

    // ── Legacy fast path: single-blob dump ────────────────────────
    let legacy_dump = idx_dir.join("epoch_dump.bin");
    if legacy_dump.exists() {
        return load_from_dump(&legacy_dump);
    }

    // ── Slow path: index from corpus JSON ─────────────────────────
    let (store, ctx) = build_from_corpus(idx_dir);

    // Dump per-epoch snapshot for next time
    dump_to_dir(&store, &snapshot_dir);

    (store, ctx)
}

/// Build index from corpus JSON (slow path).
fn build_from_corpus(idx_dir: &Path) -> (MemoryStore, Arc<Context>) {
    let schema = create_schema();
    let ctx = Arc::new(Context::new(schema.clone()));

    let mut store = MemoryStore::new_epoch();
    store.open(&schema).unwrap();

    // Enable bulk mode for faster DatTermDict insertions
    eprintln!("Field 'text' index exists: {}", store.field_index_store_exists("text"));
    store.enable_bulk_mode(0, 0);

    // Find corpus path
    let corpus_path_file = idx_dir.join("corpus_path.txt");
    let corpus_path = if corpus_path_file.exists() {
        std::fs::read_to_string(&corpus_path_file)
            .expect("read corpus_path.txt")
            .trim()
            .to_string()
    } else {
        // Fallback: look for corpus.json in idx_dir
        idx_dir.join("corpus.json").to_string_lossy().to_string()
    };

    eprintln!("Reading corpus from: {}", corpus_path);
    let file = std::fs::File::open(&corpus_path).expect("open corpus file");
    let reader = BufReader::with_capacity(4 << 20, file);

    let start = Instant::now();
    let batch_size = 100_000;
    let mut batch: Vec<DraftDoc> = Vec::with_capacity(batch_size);
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

        let mut fields = hashbrown::HashMap::new();
        fields.insert("text".to_string(), FieldValue::Text(text));
        batch.push(DraftDoc::new_with_id_and_fields(DocID::ID(doc_id), fields));
        doc_id += 1;

        if batch.len() >= batch_size {
            let t1 = Instant::now();
            store.bulk_create(&ctx, &schema, batch.split_off(0));
            index_ns += t1.elapsed().as_nanos();

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
    if !batch.is_empty() {
        total += batch.len() as u32;
        let t1 = Instant::now();
        store.bulk_create(&ctx, &schema, batch);
        index_ns += t1.elapsed().as_nanos();
    }

    // Finalise bulk mode: flush HashMap write cache into Cedar trie
    // so prefix/fuzzy queries work correctly.
    let t_flush = Instant::now();
    store.finish_bulk_mode();
    let flush_ms = t_flush.elapsed().as_millis();

    store.flush().unwrap();

    eprintln!(
        "Loaded {} docs into MemoryStore in {:.2}s  (json_parse: {:.2}s, index: {:.2}s, cedar_flush: {}ms)",
        total,
        start.elapsed().as_secs_f64(),
        json_parse_ns as f64 / 1e9,
        index_ns as f64 / 1e9,
        flush_ms,
    );

    (store, ctx)
}

/// Dump the epoch index for the "text" field to a binary file (legacy single-blob).
#[allow(dead_code)]
fn dump_to_file(store: &MemoryStore, path: &Path) {
    let start = Instant::now();
    if let Some(bytes) = store.dump_epoch_field("text") {
        std::fs::write(path, &bytes).expect("write epoch dump");
        eprintln!(
            "Dumped epoch index to {} ({:.1} MB, {:.2}s)",
            path.display(),
            bytes.len() as f64 / (1024.0 * 1024.0),
            start.elapsed().as_secs_f64(),
        );
    } else {
        eprintln!("Warning: could not dump epoch index (field 'text' not found or not epoch)");
    }
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

/// Fast-path: reconstruct a MemoryStore from a previously dumped binary file.
fn load_from_dump(path: &Path) -> (MemoryStore, Arc<Context>) {
    let start = Instant::now();
    let schema = create_schema();
    let ctx = Arc::new(Context::new(schema.clone()));

    let bytes = std::fs::read(path).expect("read epoch dump");
    let file_mb = bytes.len() as f64 / (1024.0 * 1024.0);

    let mut store = MemoryStore::new_epoch();
    store.open(&schema).unwrap();

    store
        .load_epoch_field("text".to_string(), &bytes)
        .expect("load epoch field");

    // Determine total_doc_count from the loaded index and fix up slot state.
    // We peek at the header: bytes[8..12] is total_doc_count (LE u32).
    let total_docs = u32::from_le_bytes([bytes[8], bytes[9], bytes[10], bytes[11]]);
    store.set_slot_state(total_docs);
    store.populate_stub_documents(total_docs);
    store.flush().unwrap();

    eprintln!(
        "Loaded epoch dump from {} ({:.1} MB, {} docs) in {:.2}s",
        path.display(),
        file_mb,
        total_docs,
        start.elapsed().as_secs_f64(),
    );

    (store, ctx)
}

/// Fast-path: reconstruct a MemoryStore from a per-epoch snapshot directory.
fn load_from_snapshot(snapshot_dir: &Path) -> (MemoryStore, Arc<Context>) {
    let start = Instant::now();
    let schema = create_schema();
    let ctx = Arc::new(Context::new(schema.clone()));

    // Read engine metadata
    let meta_json = std::fs::read_to_string(snapshot_dir.join("meta.dat"))
        .expect("read meta.dat");

    // Parse total_doc_count from JSON for slot state (quick parse)
    let total_docs: u32 = {
        let v: serde_json::Value = serde_json::from_str(&meta_json).expect("parse engine meta");
        v["total_doc_count"].as_u64().unwrap_or(0) as u32
    };

    let mut store = MemoryStore::new_epoch();
    store.open(&schema).unwrap();

    let dir = snapshot_dir.to_path_buf();
    store
        .load_epoch_snapshot_from_json(
            "text".to_string(),
            &meta_json,
            |relative_path| {
                let full_path = dir.join(relative_path);
                std::fs::read(&full_path).map_err(|e| {
                    pizza_engine::error::PizzaEngineError::DataCorrupted(Some(
                        format!("read {}: {}", full_path.display(), e),
                    ))
                })
            },
        )
        .expect("load epoch snapshot");

    store.set_slot_state(total_docs);
    store.populate_stub_documents(total_docs);
    store.flush().unwrap();

    let elapsed = start.elapsed().as_secs_f64();
    eprintln!(
        "Loaded snapshot from {} ({} docs) in {:.2}s",
        snapshot_dir.display(),
        total_docs,
        elapsed,
    );

    (store, ctx)
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("Usage: do_query <idx_dir>");
        std::process::exit(1);
    }
    let idx_dir = Path::new(&args[1]);

    let (mut store, ctx) = load_corpus(idx_dir);

    // Create snapshot and wrap for Searcher
    let snapshot = store.create_snapshot();
    let store = Arc::new(RwLock::new(store));
    let searcher: Searcher<MemoryStore> = Searcher::new(ctx.clone(), store.clone());

    eprintln!("Ready. Waiting for queries on stdin...");

    let stdin = std::io::stdin();
    for line_res in stdin.lock().lines() {
        let line = match line_res {
            Ok(l) => l,
            Err(_) => continue,
        };
        let fields: Vec<&str> = line.split('\t').collect();
        if fields.len() != 2 {
            write_line("UNSUPPORTED");
            continue;
        }
        let command = fields[0];
        let query_str = fields[1];

        let original_query = OriginalQuery::QueryString(query_str.into());
        let mut query_ctx = QueryContext {
            from: 0,
            size: 10,
            default_query_iterator_batch_size: 1024,
            support_wildcard_in_field_name: false,
            original_query: Some(original_query),
            tracing_id: String::new(),
            explains_enabled: false,
            default_field: "text".into(),
            default_operator: Operator::Or,
            default_cross_fields_strategy: CombinationStrategy::BestFields,
            track_total_hits: TrackTotalHits::default(),
        };

        let parsed_query = searcher
            .parse(&query_ctx)
            .expect("OriginalQuery must be set")
            .unwrap();

        match command {
            "COUNT" | "TOP_10_COUNT" | "TOP_100_COUNT" | "TOP_1000_COUNT" | "CHECK_COUNT" => {
                query_ctx.size = 0;
                query_ctx.track_total_hits = TrackTotalHits::Boolean(true);
                let result = searcher.query(&query_ctx, &parsed_query, &snapshot).unwrap();
                write_line(&result.total_hits.to_string());
            }
            "TOP_10" | "TOP_100" | "TOP_1000" => {
                let size = match command {
                    "TOP_10" => 10,
                    "TOP_100" => 100,
                    "TOP_1000" => 1000,
                    _ => unreachable!(),
                };
                query_ctx.size = size;
                let result = searcher.query(&query_ctx, &parsed_query, &snapshot).unwrap();
                let n = result.hits.as_ref().map(|h| h.len()).unwrap_or(0);
                write_line(&n.to_string());
            }
            "CHECK_TOP_10" | "CHECK_TOP_100" | "CHECK_TOP_1000" => {
                let size = match command {
                    "CHECK_TOP_10" => 10,
                    "CHECK_TOP_100" => 100,
                    "CHECK_TOP_1000" => 1000,
                    _ => unreachable!(),
                };
                query_ctx.size = size;
                let result = searcher.query(&query_ctx, &parsed_query, &snapshot).unwrap();
                if let Some(mut docs) = result.hits {
                    docs.sort_by(|a, b| {
                        let sa = a.score.unwrap_or(0.0);
                        let sb = b.score.unwrap_or(0.0);
                        sb.partial_cmp(&sa)
                            .unwrap_or(std::cmp::Ordering::Equal)
                            .then(a.id.cmp(&b.id))
                    });
                    let parts: Vec<String> = docs
                        .iter()
                        .map(|d| format!("{}:{:.6}", d.id, d.score.unwrap_or(0.0)))
                        .collect();
                    write_line(&parts.join(","));
                } else {
                    write_line("");
                }
            }
            _ => {
                write_line("UNSUPPORTED");
            }
        }
    }
}
