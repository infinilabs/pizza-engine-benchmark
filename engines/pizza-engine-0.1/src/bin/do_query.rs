//! Query a pizza-engine index for the search benchmark game.
//!
//! Usage: do_query <idx_dir>
//!
//! Loads pre-built CompactSegment `.cseg` files from idx_dir (FST +
//! posting lists + pre-computed BM25 — **no** text re-analysis or index
//! rebuilding needed), then reads query commands from stdin in the format:
//! COMMAND\tquery_string
//!
//! Supported commands: COUNT, TOP_10, TOP_100, TOP_10_COUNT, TOP_100_COUNT

use pizza_engine::document::{Property, Schema};
use pizza_engine::search::{OriginalQuery, QueryContext};
use pizza_engine::search::query::TrackTotalHits;
use pizza_engine::store::CompactSegment;
use pizza_engine::store::{ImmutableSegment, LayeredStore};
use pizza_engine::EngineBuilder;

use std::env;
use std::io::BufRead;
use std::path::Path;
use std::time::Instant;

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
        eprintln!("Usage: do_query <idx_dir>");
        std::process::exit(1);
    }
    let idx_dir = Path::new(&args[1]);

    let schema = create_schema();

    // Load pre-built CompactSegments directly from .cseg files
    let start = Instant::now();
    let compacts =
        CompactSegment::load_all_from_dir(idx_dir).expect("Failed to load compact segments");
    eprintln!(
        "Loaded {} compact segment(s) in {:.2}s",
        compacts.len(),
        start.elapsed().as_secs_f64()
    );

    // Register into LayeredStore (no rebuild — instant)
    let start = Instant::now();
    let mut layered = LayeredStore::new();
    let mut total_docs: u32 = 0;
    for compact in compacts {
        total_docs += compact.doc_count;
        let immutable = ImmutableSegment::from_compact_segment(compact);
        layered.register_immutable_segment(immutable);
    }
    eprintln!(
        "Registered {} immutable segment(s), {} total docs in {:.2}s",
        layered.segment_count(),
        total_docs,
        start.elapsed().as_secs_f64()
    );

    // Build the engine with LayeredStore
    let mut builder = EngineBuilder::new();
    builder.set_schema(schema);
    builder.set_data_store(layered);
    let engine = builder.build().expect("Failed to build engine");
    engine.start();

    let searcher = engine.acquire_searcher();
    let snapshot = engine.create_snapshot();

    // Process queries from stdin
    let stdin = std::io::stdin();
    for line_res in stdin.lock().lines() {
        let line = match line_res {
            Ok(l) => l,
            Err(_) => continue,
        };
        let fields: Vec<&str> = line.split('\t').collect();
        if fields.len() != 2 {
            println!("UNSUPPORTED");
            continue;
        }
        let command = fields[0];
        let query_str = fields[1];

        // Determine (size, track_total_hits, need_count) from command
        let (size, track, need_count) = match command {
            "COUNT"         => (0,   TrackTotalHits::Boolean(true),  true),
            "TOP_10"        => (10,  TrackTotalHits::Boolean(false), false),
            "TOP_100"       => (100, TrackTotalHits::Boolean(false), false),
            "TOP_10_COUNT"  => (10,  TrackTotalHits::Boolean(true),  true),
            "TOP_100_COUNT" => (100, TrackTotalHits::Boolean(true),  true),
            _ => {
                println!("UNSUPPORTED");
                continue;
            }
        };

        // Build QueryContext
        let original_query = OriginalQuery::QueryString(query_str.to_string());
        let mut query_context = QueryContext::new(original_query, false);
        query_context.default_field = "text".into();
        query_context.default_operator = pizza_engine::search::query::Operator::Or;
        query_context.size = size;
        query_context.track_total_hits = track;

        // Parse the query string
        let parsed_query = match searcher.parse(&query_context) {
            Some(Ok(pq)) => pq,
            _ => {
                println!("0");
                continue;
            }
        };

        // Execute (use `query` directly so track_total_hits is NOT overwritten)
        match searcher.query(&query_context, &parsed_query, &snapshot) {
            Ok(result) => {
                if need_count {
                    println!("{}", result.total_hits);
                } else {
                    let n = result.hits.as_ref().map_or(0, |v| v.len());
                    println!("{}", result.total_hits.max(n));
                }
            }
            Err(_e) => {
                println!("0");
            }
        }
    }
}
