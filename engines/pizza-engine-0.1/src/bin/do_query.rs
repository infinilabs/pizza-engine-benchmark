//! Query a pizza-engine index for the search benchmark game.
//!
//! Usage: do_query <idx_dir>
//!
//! Opens the CompactSegment from `<idx_dir>/segment.v8` via mmap with
//! lazy loading, then reads query commands from stdin in the
//! format: COMMAND\tquery_string
//!
//! Supported commands: COUNT, TOP_10, TOP_100, TOP_1000,
//!                     TOP_10_COUNT, TOP_100_COUNT, TOP_1000_COUNT,
//!                     CHECK_COUNT, CHECK_TOP_10, CHECK_TOP_100, CHECK_TOP_1000
//!
//! Uses the standard pizza-engine Searcher pipeline:
//!   MmapSegment → MmapStoreAdapter (StoreReader) → Searcher → parse_and_query

use pizza_engine::context::Context;
use pizza_engine::document::{Document, Property, Schema};
use pizza_engine::error::Result;
use pizza_engine::search::collector::Hit;
use pizza_engine::search::explain::ExplainNode;
use pizza_engine::search::query::TrackTotalHits;
use pizza_engine::search::{OriginalQuery, QueryContext, QueryPlan, SearchResult, Searcher};
use pizza_engine::store::MmapSegment;
use pizza_engine::traits::StoreReader;

use std::env;
use std::io::{self, BufRead, Write};
use std::path::Path;
use std::sync::Arc;
use std::time::Instant;

use spin::RwLock;

// ---------------------------------------------------------------------------
// MmapStoreAdapter — bridges MmapSegment into the StoreReader trait
// ---------------------------------------------------------------------------

/// A read-only [`StoreReader`] adapter for [`MmapSegment`].
///
/// Wraps an immutable V8 segment and delegates search operations to
/// the V8 PFOR-Delta / BMW / WAND optimized codepaths while exposing
/// the standard Searcher-compatible interface.
struct MmapStoreAdapter {
    segment: MmapSegment,
    schema: Schema,
}

/// Trivial snapshot — MmapSegment is immutable so no versioning is needed.
#[derive(Clone, Copy, Debug, Default)]
struct MmapSnapshot;

impl StoreReader for MmapStoreAdapter {
    type Snapshot = MmapSnapshot;

    fn create_snapshot(&mut self) -> MmapSnapshot {
        MmapSnapshot
    }

    fn search(
        &self,
        ctx: &Context,
        query_plan: &QueryPlan<Self>,
        _explain: &mut Option<ExplainNode>,
        _snapshot: &MmapSnapshot,
    ) -> Result<SearchResult> {
        let query = query_plan.get_query();
        let field_name = &query_plan.query_context.default_field;
        let size = query_plan.query_context.size;
        let track = &query_plan.query_context.track_total_hits;

        // COUNT mode: track_total_hits is true, or size == 0
        if matches!(track, TrackTotalHits::Boolean(true)) || size == 0 {
            let count = self.segment.count(ctx, &self.schema, query, field_name);
            return Ok(SearchResult {
                tracing_id: String::new(),
                explains: None,
                total_hits: count,
                hits: None,
            });
        }

        // TOP_K mode
        let hits: Vec<Hit> =
            self.segment
                .search_topk(ctx, &self.schema, query, field_name, size);

        let documents: Vec<Document> = hits
            .iter()
            .map(|h| Document {
                id: h.doc_id,
                key: None,
                score: Some(h.score),
                fields: hashbrown::HashMap::new(),
            })
            .collect();

        Ok(SearchResult {
            tracing_id: String::new(),
            explains: None,
            total_hits: documents.len(),
            hits: Some(documents),
        })
    }

    fn get_document_by_id(
        &self,
        _doc_id: u32,
        _snapshot: &MmapSnapshot,
    ) -> Result<Option<Document>> {
        Ok(None) // V8 segment stores inverted index only, no source docs
    }

    fn get_document_by_key(
        &self,
        _key: &str,
        _snapshot: &MmapSnapshot,
    ) -> Result<Option<Document>> {
        Ok(None)
    }
}

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

    // Open V8 segment (PFOR-Delta, lazy loading)
    let start = Instant::now();
    let v8_path = idx_dir.join("segment.v8");
    let segment = MmapSegment::open(&v8_path).expect("Failed to open segment.v8");
    eprintln!(
        "Opened segment (mmap): {} docs in {:.2}s",
        segment.doc_count,
        start.elapsed().as_secs_f64()
    );

    // Wrap segment in StoreReader adapter and create Searcher
    let store = Arc::new(RwLock::new(MmapStoreAdapter {
        segment,
        schema: schema.clone(),
    }));
    let searcher: Searcher<MmapStoreAdapter> = Searcher::new(ctx.clone(), store.clone());
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

        // Build OriginalQuery + QueryContext through the standard pipeline
        let original_query = OriginalQuery::QueryString(query_str.into());
        let mut query_ctx = QueryContext::new(original_query, false);
        query_ctx.default_field = "text".into();

        // Parse once via the standard Searcher pipeline
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
