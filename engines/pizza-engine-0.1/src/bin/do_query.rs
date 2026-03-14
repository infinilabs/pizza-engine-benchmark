//! Query a pizza-engine index for the search benchmark game.
//!
//! Usage: do_query <idx_dir>
//!
//! Opens the V8 segment from `<idx_dir>/segment.v8` via mmap, wraps it
//! in a LayeredStore with a single ImmutableSegment, then reads query
//! commands from stdin in the format: COMMAND\tquery_string
//!
//! Supported commands: COUNT, TOP_10, TOP_100, TOP_1000,
//!                     TOP_10_COUNT, TOP_100_COUNT, TOP_1000_COUNT,
//!                     CHECK_COUNT, CHECK_TOP_10, CHECK_TOP_100, CHECK_TOP_1000
//!
//! Uses the real pizza-engine LayeredStore search pipeline:
//!   MmapSegment → ImmutableSegment → LayeredStore → Searcher → parse + query

use pizza_engine::context::Context;
use pizza_engine::document::{Property, Schema};
use pizza_engine::search::query::{Operator, TrackTotalHits};
use pizza_engine::search::iterator::CombinationStrategy;
use pizza_engine::search::{OriginalQuery, QueryContext, Searcher};
use pizza_engine::store::{ImmutableSegment, LayeredStore, MmapSegment};
use pizza_engine::traits::StoreReader;

use std::env;
use std::io::{self, BufRead, Write};
use std::path::Path;
use std::sync::Arc;
use std::time::Instant;

use spin::RwLock;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Write a line to stdout, silently ignoring broken-pipe errors.
fn write_line(s: &str) {
    let stdout = io::stdout();
    let mut out = stdout.lock();
    if writeln!(out, "{}", s).is_err() {
        // Broken pipe — exit cleanly instead of panicking.
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
// Main
// ---------------------------------------------------------------------------

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("Usage: do_query <idx_dir>");
        std::process::exit(1);
    }
    let idx_dir = Path::new(&args[1]);

    let schema = create_schema();
    let ctx = Arc::new(Context::new(schema.clone()));

    // Open V8 segment (PFOR-Delta, lazy loading via mmap)
    let start = Instant::now();
    let v8_path = idx_dir.join("segment.v8");
    let segment = MmapSegment::open(&v8_path).expect("Failed to open segment.v8");
    eprintln!(
        "Opened segment (mmap): {} docs in {:.2}s",
        segment.doc_count,
        start.elapsed().as_secs_f64()
    );

    // Build LayeredStore with a single mmap-backed ImmutableSegment
    let immutable = ImmutableSegment::from_mmap_segment(segment);
    let mut layered = LayeredStore::new();
    layered.register_immutable_segment(immutable);

    let store = Arc::new(RwLock::new(layered));
    let searcher: Searcher<LayeredStore> = Searcher::new(ctx.clone(), store.clone());
    let snapshot = {
        let mut s = store.write();
        s.create_snapshot()
    };

    let mut total_queries = 0u64;
    let mut total_query_ns = 0u128;

    // Process queries from stdin
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

        total_queries += 1;
        let q_start = Instant::now();

        // Build OriginalQuery + QueryContext — bypass QueryContext::new()
        // to avoid per-query UUID generation (~2-3µs overhead).
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

        // Parse once via the standard Searcher pipeline
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
                let elapsed_us = q_start.elapsed().as_micros();
                if elapsed_us > 5000 {
                    eprintln!(
                        "[SLOW] {}us  k={}  hits={}  query={}",
                        elapsed_us, size, n, query_str
                    );
                }
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
                    // Sort by score DESC, then by doc_id ASC for consistent tiebreaking
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

        total_query_ns += q_start.elapsed().as_nanos();
    }

    eprintln!(
        "Processed {} queries in {:.2}ms (avg {:.2}us/q)",
        total_queries,
        total_query_ns as f64 / 1_000_000.0,
        total_query_ns as f64 / total_queries.max(1) as f64 / 1_000.0,
    );
}
