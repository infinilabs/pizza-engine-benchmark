//! v7 CompactSegment BMW query engine for the search benchmark game.
//!
//! Usage: do_query_bmw <idx_dir>
//!
//! Opens the v7 CompactSegment from `<idx_dir>/segment.v7` via mmap with
//! lazy loading.  Core data is decompressed on first query; positions are
//! decompressed on first phrase query.

use pizza_engine::context::Context;
use pizza_engine::document::{Property, Schema};
use pizza_engine::search::query::{Operator, Query};
use pizza_engine::search::{OriginalQuery, QueryContext};
use pizza_engine::search::query::TrackTotalHits;
use pizza_engine::store::MmapSegment;

use std::env;
use std::io::{self, BufRead, Write};
use std::path::Path;
use std::time::Instant;

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

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("Usage: do_query_bmw <idx_dir>");
        std::process::exit(1);
    }
    let idx_dir = Path::new(&args[1]);

    let schema = create_schema();
    let ctx = Context::new(schema.clone());

    // Prefer V8 (PFOR-Delta, lazy loading) if available, fallback to V7
    let start = Instant::now();
    let v8_path = idx_dir.join("segment.v8");
    let v7_path = idx_dir.join("segment.v7");
    let (segment, version_label) = if v8_path.exists() {
        let seg = MmapSegment::open(&v8_path).expect("Failed to open segment.v8");
        (seg, "v8")
    } else {
        let seg = MmapSegment::open(&v7_path).expect("Failed to open segment.v7");
        (seg, "v7")
    };
    eprintln!(
        "Opened {} segment (mmap): {} docs in {:.2}s",
        version_label,
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

        match command {
            "COUNT" => {
                let count = segment.count_with_query_string(&ctx, &schema, query_str, "text");
                write_line(&count.to_string());
            }
            "TOP_10" | "TOP_100" | "TOP_1000" => {
                let size = match command {
                    "TOP_10" => 10,
                    "TOP_100" => 100,
                    "TOP_1000" => 1000,
                    _ => unreachable!(),
                };
                let hits = segment.search_topk_with_query_string(&ctx, &schema, query_str, "text", size);
                write_line(&hits.len().to_string());
            }
            "TOP_10_COUNT" | "TOP_100_COUNT" | "TOP_1000_COUNT" => {
                let count = segment.count_with_query_string(&ctx, &schema, query_str, "text");
                write_line(&count.to_string());
            }
            "CHECK_COUNT" => {
                let count = segment.count_with_query_string(&ctx, &schema, query_str, "text");
                write_line(&count.to_string());
            }
            "CHECK_TOP_10" | "CHECK_TOP_100" | "CHECK_TOP_1000" => {
                let size = match command {
                    "CHECK_TOP_10" => 10,
                    "CHECK_TOP_100" => 100,
                    "CHECK_TOP_1000" => 1000,
                    _ => unreachable!(),
                };
                let mut hits = segment.search_topk_with_query_string(&ctx, &schema, query_str, "text", size);
                // Sort by score DESC, then by doc_id ASC for consistent tiebreaking
                hits.sort_by(|a, b| {
                    b.score.partial_cmp(&a.score)
                        .unwrap_or(std::cmp::Ordering::Equal)
                        .then(a.doc_id.cmp(&b.doc_id))
                });
                let parts: Vec<String> = hits.iter()
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

    eprintln!("Processed {} queries in {:.2}ms (avg {:.2}us/q)",
        total_queries,
        total_query_ns as f64 / 1_000_000.0,
        total_query_ns as f64 / total_queries.max(1) as f64 / 1_000.0,
    );
}
