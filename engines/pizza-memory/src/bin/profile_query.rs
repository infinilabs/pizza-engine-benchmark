//! Profiling harness for pizza-memory query performance.
//!
//! Usage: profile_query <corpus_json> [duration_secs]
//!
//! Loads the corpus into MemoryStore, then runs a fixed set of representative
//! queries in a tight loop for `duration_secs` (default 60). Attach dtrace
//! to the process PID during the query phase to capture a flamegraph.

use pizza_engine::context::Context;
use pizza_engine::document::{DocID, DraftDoc, FieldValue, Property, Schema};
use pizza_engine::search::iterator::CombinationStrategy;
use pizza_engine::search::query::{Operator, TrackTotalHits};
use pizza_engine::search::{OriginalQuery, QueryContext, Searcher};
use pizza_engine::store::MemoryStore;
use pizza_engine::traits::{StoreReader, StoreWriter};

use serde::Deserialize;
use std::env;
use std::io::{BufRead, BufReader};
use std::sync::Arc;
use std::time::{Duration, Instant};

use spin::RwLock;

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

fn load_corpus(corpus_path: &str) -> (MemoryStore, Arc<Context>) {
    let schema = create_schema();
    let ctx = Arc::new(Context::new(schema.clone()));

    let mut store = MemoryStore::new();
    store.open(&schema).unwrap();

    eprintln!("Reading corpus from: {}", corpus_path);
    let file = std::fs::File::open(corpus_path).expect("open corpus file");
    let reader = BufReader::with_capacity(4 << 20, file);

    let start = Instant::now();
    let batch_size = 100_000;
    let mut batch: Vec<DraftDoc> = Vec::with_capacity(batch_size);
    let mut doc_id: u32 = 1;
    let mut total = 0u32;

    for line in reader.lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => continue,
        };
        if line.trim().is_empty() {
            continue;
        }
        let input_doc: InputDocument = match serde_json::from_str(&line) {
            Ok(d) => d,
            Err(_) => continue,
        };
        let text = input_doc.text.unwrap_or_default();

        let mut fields = hashbrown::HashMap::new();
        fields.insert("text".to_string(), FieldValue::Text(text));
        batch.push(DraftDoc::new_with_id_and_fields(DocID::ID(doc_id), fields));
        doc_id += 1;

        if batch.len() >= batch_size {
            store.bulk_create(&ctx, &schema, batch.split_off(0));
            total += batch_size as u32;
            if total % 100_000 == 0 {
                eprintln!("  loaded {} docs ({:.2}s)", total, start.elapsed().as_secs_f64());
            }
        }
    }
    if !batch.is_empty() {
        total += batch.len() as u32;
        store.bulk_create(&ctx, &schema, batch);
    }
    store.flush().unwrap();

    eprintln!(
        "Loaded {} docs in {:.2}s",
        total,
        start.elapsed().as_secs_f64()
    );

    (store, ctx)
}

/// Representative queries covering different query types:
/// - High-frequency single term (OR, huge postings)
/// - AND intersection (two common terms)
/// - Phrase query
/// - OR union (two terms)
/// - AND intersection (rare terms)
/// - Single rare term
const QUERIES: &[&str] = &[
    "the",                         // single high-freq term → COUNT scan
    "+hello +world",               // AND intersection
    "\"hello world\"",             // phrase query
    "hello world",                 // OR union
    "+bowel +obstruction",         // AND intersection (medium freq)
    "\"bowel obstruction\"",       // phrase query (medium freq)
    "+griffith +observatory",      // AND intersection (rare)
    "\"griffith observatory\"",    // phrase query (rare)
    "griffith observatory",        // OR union (rare)
    "obama",                       // single term
    "the quick brown fox",         // multi-term OR
    "+new +york +city",            // 3-way AND
];

fn run_query(
    searcher: &Searcher<MemoryStore>,
    query_str: &str,
    snapshot: &<MemoryStore as StoreReader>::Snapshot,
    size: usize,
) -> usize {
    let original_query = OriginalQuery::QueryString(query_str.into());
    let query_ctx = QueryContext {
        from: 0,
        size,
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

    let result = searcher.query(&query_ctx, &parsed_query, snapshot).unwrap();
    result.total_hits
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("Usage: profile_query <corpus_json> [duration_secs]");
        std::process::exit(1);
    }
    let corpus_path = &args[1];
    let duration_secs: u64 = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(60);

    // ── Load corpus ──────────────────────────────────────────────────
    let (mut store, ctx) = load_corpus(corpus_path);
    let snapshot = store.create_snapshot();
    let store = Arc::new(RwLock::new(store));
    let searcher: Searcher<MemoryStore> = Searcher::new(ctx.clone(), store.clone());

    // ── Warm up ──────────────────────────────────────────────────────
    eprintln!("Warming up...");
    for q in QUERIES {
        let hits = run_query(&searcher, q, &snapshot, 10);
        eprintln!("  query={:40} hits={}", q, hits);
    }

    // ── Print PID and wait for dtrace attachment ─────────────────────
    let pid = std::process::id();
    eprintln!("\n========================================");
    eprintln!("PID: {}", pid);
    eprintln!("Attach dtrace now:");
    eprintln!("  sudo dtrace -x ustackframes=100 -n 'profile-997 /pid == {}/ {{ @[ustack()] = count(); }} tick-{}s {{ exit(0); }}' -o /tmp/pizza_query.stacks", pid, duration_secs);
    eprintln!("Or just wait — query loop starts in 3 seconds...");
    eprintln!("========================================\n");
    std::thread::sleep(Duration::from_secs(3));

    // ── Query loop ───────────────────────────────────────────────────
    let deadline = Instant::now() + Duration::from_secs(duration_secs);
    let mut iterations = 0u64;
    let mut total_hits = 0u64;

    eprintln!("Starting query loop for {}s...", duration_secs);
    let loop_start = Instant::now();

    while Instant::now() < deadline {
        for q in QUERIES {
            // Alternate between COUNT (size=0) and TOP_10 (size=10)
            let count_hits = run_query(&searcher, q, &snapshot, 0);
            total_hits += count_hits as u64;

            let top10_hits = run_query(&searcher, q, &snapshot, 10);
            total_hits += top10_hits as u64;

            iterations += 2;
        }
    }

    let elapsed = loop_start.elapsed();
    eprintln!("\n========================================");
    eprintln!("Query loop finished.");
    eprintln!("  Duration:   {:.2}s", elapsed.as_secs_f64());
    eprintln!("  Iterations: {} ({:.0} queries/sec)", iterations, iterations as f64 / elapsed.as_secs_f64());
    eprintln!("  Total hits: {}", total_hits);
    eprintln!("========================================");
}
