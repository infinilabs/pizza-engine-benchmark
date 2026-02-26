//! Build a pizza-engine immutable index from the benchmark corpus.
//!
//! Usage: build_index <idx_dir> < corpus.json
//!
//! Reads JSON lines from stdin (each with "id" and "text" fields),
//! builds CompactSegments (FST + posting lists + pre-computed BM25)
//! in batches and persists them as `.cseg` files.
//!
//! At query time the `.cseg` files are loaded directly — no text
//! re-analysis or index rebuilding is needed.

use pizza_engine::context::Context;
use pizza_engine::document::{FieldValue, Property, Schema};
use pizza_engine::store::CompactSegmentBuilder;
use pizza_engine::writer::builder::{FrozenDoc, FrozenEpochData};

use serde::Deserialize;
use std::env;
use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::sync::mpsc;
use std::sync::Arc;
use std::thread;
use std::time::Instant;

#[derive(Deserialize)]
struct InputDocument {
    #[serde(default)]
    id: Option<String>,
    #[serde(default)]
    text: Option<String>,
}

const BATCH_SIZE: u32 = 200_000;

fn create_schema() -> Schema {
    let mut schema = Schema::new();
    schema
        .add_property("text", Property::as_text(Some("standard")))
        .unwrap();
    schema.freeze();
    schema
}

fn main() {
    env_logger::init();
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("Usage: build_index <idx_dir> < corpus.json");
        std::process::exit(1);
    }
    let idx_dir = PathBuf::from(&args[1]);

    let schema = create_schema();
    let ctx = Arc::new(Context::new(schema.clone()));

    // --- 3-stage pipeline ---
    // Stage 1 (reader thread):  stdin → parse JSON → fill batches → send Vec<FrozenDoc>
    // Stage 2 (builder thread): receive batch → build_lean (rayon) → send CompactSegment
    // Stage 3 (writer thread):  receive CompactSegment → to_bytes → write .cseg

    // Channel: reader → builder  (bounded 1 so reader doesn't get too far ahead)
    let (batch_tx, batch_rx) = mpsc::sync_channel::<(u64, Vec<FrozenDoc>, Instant)>(1);

    // Channel: builder → writer  (bounded 1)
    let (seg_tx, seg_rx) = mpsc::sync_channel::<(u64, u32, pizza_engine::store::CompactSegment, Instant)>(1);

    // --- Stage 1: Reader thread ---
    let reader_handle = thread::spawn(move || {
        let stdin = std::io::stdin();
        let reader = BufReader::with_capacity(1 << 20, stdin.lock());

        let mut epoch_id: u64 = 1;
        let mut doc_id: u32 = 1;
        let mut batch_docs: Vec<FrozenDoc> = Vec::with_capacity(BATCH_SIZE as usize);
        let mut start = Instant::now();
        let mut total_docs: u64 = 0;

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
                Err(e) => {
                    eprintln!("Failed to parse line: {}", e);
                    continue;
                }
            };

            let text = input_doc.text.unwrap_or_default();
            let mut fields = hashbrown::HashMap::new();
            fields.insert("text".to_string(), FieldValue::Text(text));

            batch_docs.push(FrozenDoc {
                doc_id,
                key: input_doc.id,
                fields,
            });

            doc_id += 1;
            total_docs += 1;

            if batch_docs.len() as u32 >= BATCH_SIZE {
                let batch = std::mem::replace(
                    &mut batch_docs,
                    Vec::with_capacity(BATCH_SIZE as usize),
                );
                batch_tx.send((epoch_id, batch, start)).ok();
                start = Instant::now();
                epoch_id += 1;
            }
        }

        // Flush remaining
        if !batch_docs.is_empty() {
            batch_tx.send((epoch_id, batch_docs, start)).ok();
        }

        total_docs
    });

    // --- Stage 2: Builder thread ---
    let builder_ctx = Arc::clone(&ctx);
    let builder_schema = schema.clone();
    let builder_handle = thread::spawn(move || {
        while let Ok((epoch_id, docs, start)) = batch_rx.recv() {
            let doc_count = docs.len() as u32;

            let mut data = FrozenEpochData::new(epoch_id);
            data.documents = docs;
            data.doc_count = doc_count;
            data.op_count = doc_count;

            let builder = CompactSegmentBuilder::new(&builder_ctx, &builder_schema);
            let compact = builder.build_lean(&data);

            seg_tx.send((epoch_id, doc_count, compact, start)).ok();
        }
    });

    // --- Stage 3: Writer (on main thread) ---
    while let Ok((epoch_id, doc_count, compact, start)) = seg_rx.recv() {
        let path = compact
            .save_to_dir(&idx_dir)
            .expect("Failed to save compact segment");

        let elapsed = start.elapsed();
        eprintln!(
            "Segment {} saved ({} docs) in {:.2}s -> {}",
            epoch_id,
            doc_count,
            elapsed.as_secs_f64(),
            path.display()
        );
    }

    let total_docs = reader_handle.join().expect("reader thread panicked");
    builder_handle.join().expect("builder thread panicked");

    eprintln!("Done. Total documents indexed: {}", total_docs);
}
