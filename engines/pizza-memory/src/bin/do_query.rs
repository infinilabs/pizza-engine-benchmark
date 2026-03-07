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
