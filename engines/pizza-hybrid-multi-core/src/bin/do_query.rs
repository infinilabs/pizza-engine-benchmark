//! Query a pizza-engine hybrid LayeredStore for the search benchmark game.
//! Multi-core variant with parallel_query feature and RAYON_NUM_THREADS=8.
//!
//! Usage: do_query <idx_dir>
//!
//! Loads a multi-layer index:
//!   - 3 × 1M-doc MmapSegment V8 files → ImmutableSegments
//!   - 1M docs → frozen mutable MemoryStore segment
//!   - 1M docs → active mutable MemoryStore segment
//!
//! This tests realistic multi-segment search: immutable (mmap) + frozen
//! (in-memory, read-only) + active (in-memory, mutable) layers.

use pizza_engine::context::Context;
use pizza_engine::document::{DocID, DraftDoc, FieldValue, Property, Schema};
use pizza_engine::search::iterator::CombinationStrategy;
use pizza_engine::search::query::{Operator, TrackTotalHits};
use pizza_engine::search::{OriginalQuery, QueryContext, Searcher};
use pizza_engine::store::{ImmutableSegment, LayeredStore, MmapSegment};
use pizza_engine::traits::{StoreReader, StoreWriter};

use std::env;
use std::io::{self, BufRead, Write};
use std::path::Path;
use std::sync::Arc;
use std::time::Instant;

use spin::RwLock;

const DOCS_PER_SEGMENT: usize = 1_000_000;

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

/// Read docs from corpus_mem.bin.  Returns (start_doc_id, Vec<String>).
fn read_mem_docs(idx_dir: &Path) -> (u32, Vec<String>) {
    let bin_path = idx_dir.join("corpus_mem.bin");
    let data = std::fs::read(&bin_path).expect("Failed to read corpus_mem.bin");
    let mut pos = 0usize;

    // First 4 bytes: starting doc_id
    let start_doc_id = u32::from_le_bytes(data[pos..pos + 4].try_into().unwrap());
    pos += 4;

    let mut texts = Vec::new();
    while pos + 4 <= data.len() {
        let len = u32::from_le_bytes(data[pos..pos + 4].try_into().unwrap()) as usize;
        pos += 4;
        if pos + len > data.len() {
            break;
        }
        let text = std::str::from_utf8(&data[pos..pos + len])
            .unwrap_or("")
            .to_string();
        pos += len;
        texts.push(text);
    }
    (start_doc_id, texts)
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

    let start = Instant::now();

    // ── Layer 1: Load immutable V8 segments from disk ──────────────────
    let mut layered = LayeredStore::new_epoch();
    layered.open(&schema).unwrap();

    let mut immutable_count = 0u32;
    let mut loaded_segments = 0u64;
    for seg_idx in 1u64.. {
        let v8_path = idx_dir.join(format!("segment_{}.v8", seg_idx));
        if !v8_path.exists() {
            break;
        }
        let mmap_seg = MmapSegment::open(&v8_path).expect("Failed to open V8 segment");
        let doc_count = mmap_seg.doc_count;
        let immutable = ImmutableSegment::from_mmap_segment(mmap_seg);
        layered.register_immutable_segment(immutable);
        immutable_count += doc_count;
        loaded_segments += 1;
        eprintln!(
            "  Loaded immutable segment {} ({} docs) in {:.2}s",
            seg_idx,
            doc_count,
            start.elapsed().as_secs_f64()
        );
    }

    // Fast path: when additional immutable segments exist (segment_4+),
    // run fully immutable and skip expensive mutable rebuild.
    let use_immutable_only = loaded_segments >= 4;

    let (frozen_count, active_count) = if use_immutable_only {
        eprintln!(
            "  Using immutable-only mode ({} segments), skipping mutable load",
            loaded_segments
        );
        (0usize, 0usize)
    } else {
        // ── Legacy Layer 2 & 3: rebuild mutable layers from corpus_mem.bin ──
        let (start_doc_id, mem_texts) = read_mem_docs(idx_dir);
        let mem_total = mem_texts.len();
        eprintln!(
            "  Read {} memory docs (starting doc_id={}) in {:.2}s",
            mem_total,
            start_doc_id,
            start.elapsed().as_secs_f64()
        );

        // Split: first DOCS_PER_SEGMENT → frozen mutable, rest → active mutable
        let frozen_count = mem_total.min(DOCS_PER_SEGMENT);
        let active_start = frozen_count;

        // Write frozen mutable docs into the active store, then freeze it
        {
            let batch_size = 100_000;
            let mut batch: Vec<DraftDoc> = Vec::with_capacity(batch_size);
            let mut doc_id = start_doc_id;

            for i in 0..frozen_count {
                let mut fields = hashbrown::HashMap::new();
                fields.insert("text".to_string(), FieldValue::Text(mem_texts[i].clone()));
                batch.push(DraftDoc::new_with_id_and_fields(DocID::ID(doc_id), fields));
                doc_id += 1;

                if batch.len() >= batch_size {
                    layered.mutable_mut().bulk_create(&ctx, &schema, batch.split_off(0));
                }
            }
            if !batch.is_empty() {
                layered.mutable_mut().bulk_create(&ctx, &schema, batch);
            }
            layered.flush().unwrap();

            // Compact the mutable segment before freezing for fast queries.
            layered.mutable_mut().compact_for_queries();

            // Freeze: moves active → FrozenMutableSegment, creates fresh active
            layered.freeze_active_segment(&schema, 4).unwrap();
            eprintln!(
                "  Frozen mutable: {} docs, elapsed {:.2}s",
                frozen_count,
                start.elapsed().as_secs_f64()
            );
        }

        // Write active mutable docs
        {
            let batch_size = 100_000;
            let mut batch: Vec<DraftDoc> = Vec::with_capacity(batch_size);
            let mut doc_id = start_doc_id + frozen_count as u32;

            for i in active_start..mem_total {
                let mut fields = hashbrown::HashMap::new();
                fields.insert("text".to_string(), FieldValue::Text(mem_texts[i].clone()));
                batch.push(DraftDoc::new_with_id_and_fields(DocID::ID(doc_id), fields));
                doc_id += 1;

                if batch.len() >= batch_size {
                    layered.mutable_mut().bulk_create(&ctx, &schema, batch.split_off(0));
                }
            }
            if !batch.is_empty() {
                layered.mutable_mut().bulk_create(&ctx, &schema, batch);
            }
            layered.flush().unwrap();
            eprintln!(
                "  Active mutable: {} docs, elapsed {:.2}s",
                mem_total - frozen_count,
                start.elapsed().as_secs_f64()
            );
        }

        // Compact the active mutable segment for fast queries.
        layered.mutable_mut().compact_for_queries();
        (frozen_count, mem_total - frozen_count)
    };

    eprintln!(
        "LayeredStore ready: {} immutable + {} frozen + {} active = {} total in {:.2}s",
        immutable_count,
        frozen_count,
        active_count,
        immutable_count as usize + frozen_count + active_count,
        start.elapsed().as_secs_f64()
    );

    // ── Build searcher ─────────────────────────────────────────────────
    let store = Arc::new(RwLock::new(layered));
    let searcher: Searcher<LayeredStore> = Searcher::new(ctx.clone(), store.clone());
    let snapshot = {
        let mut s = store.write();
        s.create_snapshot()
    };

    eprintln!("Ready. Waiting for queries on stdin...");

    // ── Query loop ─────────────────────────────────────────────────────
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
