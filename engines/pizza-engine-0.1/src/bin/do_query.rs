//! Query a pizza-engine V8 index for the search benchmark game.
//!
//! Usage: do_query <idx_dir>
//!
//! Opens the V8 segment from `<idx_dir>/segment.v8` via mmap, then reads
//! query commands from stdin in the format: COMMAND\tquery_string
//!
//! Supported commands: COUNT, TOP_10, TOP_100, TOP_1000,
//!                     TOP_10_COUNT, TOP_100_COUNT, TOP_1000_COUNT,
//!                     CHECK_COUNT, CHECK_TOP_10, CHECK_TOP_100, CHECK_TOP_1000
//!
//! Direct MmapFrozenSegment path — bypasses LayeredStore/Searcher overhead:
//!   MmapFrozenSegment → parse_query_string_to_query → search_topk / count

use pizza_engine::context::Context;
use pizza_engine::document::{Property, Schema};
use pizza_engine::store::{MmapFrozenSegment, parse_query_string_to_query};

use std::env;
use std::io::{self, BufRead, Write};
use std::path::Path;
use std::time::Instant;

const DEFAULT_FIELD: &str = "text";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Write a line to stdout, silently ignoring broken-pipe errors.
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
    let ctx = Context::new(schema.clone());

    // Open the V8 segment directly via mmap (no LayeredStore wrapping)
    let start = Instant::now();
    let seg_path = idx_dir.join("segment.v8");
    if !seg_path.exists() {
        eprintln!("No segment.v8 found in {}", idx_dir.display());
        std::process::exit(1);
    }

    let segment = MmapFrozenSegment::open(&seg_path)
        .unwrap_or_else(|e| panic!("Failed to open {}: {:?}", seg_path.display(), e));

    eprintln!(
        "Opened V8 segment (mmap): {} docs in {:.2}s",
        segment.doc_count,
        start.elapsed().as_secs_f64()
    );

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

        // Parse the query string once into a structured Query
        let query = parse_query_string_to_query(query_str, DEFAULT_FIELD);

        match command {
            "COUNT" | "TOP_10_COUNT" | "TOP_100_COUNT" | "TOP_1000_COUNT" | "CHECK_COUNT" => {
                let count = segment.count(&ctx, &schema, &query, DEFAULT_FIELD);
                write_line(&count.to_string());
            }
            "TOP_10" | "TOP_100" | "TOP_1000" => {
                let k = match command {
                    "TOP_10" => 10usize,
                    "TOP_100" => 100,
                    "TOP_1000" => 1000,
                    _ => unreachable!(),
                };
                let hits = segment.search_topk(&ctx, &schema, &query, DEFAULT_FIELD, k);
                write_line(&hits.len().to_string());
            }
            "CHECK_TOP_10" | "CHECK_TOP_100" | "CHECK_TOP_1000" => {
                let k = match command {
                    "CHECK_TOP_10" => 10usize,
                    "CHECK_TOP_100" => 100,
                    "CHECK_TOP_1000" => 1000,
                    _ => unreachable!(),
                };
                let mut hits = segment.search_topk(&ctx, &schema, &query, DEFAULT_FIELD, k);
                // Sort by score DESC, then by doc_id ASC for consistent tiebreaking
                hits.sort_by(|a, b| {
                    b.score.partial_cmp(&a.score)
                        .unwrap_or(std::cmp::Ordering::Equal)
                        .then(a.doc_id.cmp(&b.doc_id))
                });
                let parts: Vec<String> = hits
                    .iter()
                    .map(|h| format!("{}:{:.6}", h.doc_id, h.score))
                    .collect();
                write_line(&parts.join(","));
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
