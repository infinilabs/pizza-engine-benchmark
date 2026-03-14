//! Query server for pizza-engine MemoryStore (search benchmark game).
//!
//! Usage: do_query <idx_dir>
//!
//! Loads a pre-built snapshot from `<idx_dir>/snapshot/` (created by
//! `build_index`), compacts it for fast queries, then serves query
//! commands from stdin.  No corpus re-indexing happens here.

use pizza_engine::context::Context;
use pizza_engine::document::{Property, Schema};
use pizza_engine::search::iterator::CombinationStrategy;
use pizza_engine::search::query::{Operator, TrackTotalHits};
use pizza_engine::search::{OriginalQuery, QueryContext, Searcher};
use pizza_engine::store::MemoryStore;
use pizza_engine::traits::{StoreReader, StoreWriter};

use std::env;
use std::io::{self, BufRead, Write};
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

// ---------------------------------------------------------------------------
// Load from snapshot
// ---------------------------------------------------------------------------

/// Load a MemoryStore from a pre-built snapshot directory, then compact.
fn load_snapshot(snapshot_dir: &Path) -> (MemoryStore, Arc<Context>) {
    let start = Instant::now();
    let schema = create_schema();
    let ctx = Arc::new(Context::new(schema.clone()));

    // Read engine metadata
    let meta_json = std::fs::read_to_string(snapshot_dir.join("meta.dat"))
        .expect("read meta.dat — did you run build_index first?");

    // Parse total_doc_count from JSON
    let total_docs: u32 = {
        let v: serde_json::Value = serde_json::from_str(&meta_json).expect("parse meta.dat");
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

    // Compact for fast queries (drops epoch data to save memory).
    let skip_compact = std::env::var("NO_COMPACT").unwrap_or_default() == "1";
    let t_compact = Instant::now();
    if !skip_compact {
        store.compact_for_queries();
    }
    let compact_ms = t_compact.elapsed().as_millis();

    if std::env::var("MEMORY_REPORT").unwrap_or_default() == "1" {
        store.print_memory_report();
    }

    store.flush().unwrap();

    eprintln!(
        "Loaded snapshot from {} ({} docs) in {:.2}s (compact: {}ms{})",
        snapshot_dir.display(),
        total_docs,
        start.elapsed().as_secs_f64(),
        compact_ms,
        if skip_compact { " SKIPPED" } else { "" },
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
    let snapshot_dir = idx_dir.join("snapshot");

    if !snapshot_dir.join("meta.dat").exists() {
        eprintln!(
            "Error: snapshot not found at {}. Run build_index first.",
            snapshot_dir.display()
        );
        std::process::exit(1);
    }

    let (mut store, ctx) = load_snapshot(&snapshot_dir);

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

        let mut parsed_query = searcher
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
                parsed_query.collect_size = if size == 10 { Some(50) } else { None };
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
                parsed_query.collect_size = if size == 10 { Some(50) } else { None };
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

    // Ensure all buffered stdout is flushed before exit.
    let _ = io::stdout().lock().flush();
}
