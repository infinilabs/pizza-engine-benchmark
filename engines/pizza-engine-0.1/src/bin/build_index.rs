//! Fast index builder for the search benchmark game.
//!
//! Usage: build_index <idx_dir> < corpus.json
//!
//! Reads JSON documents from stdin, packs them into `FrozenEpochData`, and
//! delegates tokenization, term-interning, sort-merge, and BM25 pre-computation
//! to the engine's generic `CompactSegmentBuilder::build_lean()` API.
//!
//! 3-stage pipeline:
//!   Stage 1 (reader):  stdin → JSON parse → FrozenDoc list
//!   Stage 2 (builder): CompactSegmentBuilder::build_lean (parallel analysis + sort-merge)
//!   Stage 3 (writer):  serializes V8 segment to disk

use pizza_engine::context::Context;
use pizza_engine::document::{FieldValue, Property, Schema};
use pizza_engine::store::CompactSegmentBuilder;
use pizza_engine::writer::builder::{FrozenDoc, FrozenEpochData};

use serde::Deserialize;
use std::env;
use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::time::Instant;

#[derive(Deserialize)]
struct InputDocument {
    #[serde(default)]
    text: Option<String>,
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
        eprintln!("Usage: build_index <idx_dir> < corpus.json");
        std::process::exit(1);
    }
    let idx_dir = PathBuf::from(&args[1]);
    std::fs::create_dir_all(&idx_dir).expect("Failed to create idx dir");

    let schema = create_schema();
    let ctx = Context::new(schema.clone());

    let start = Instant::now();
    let stdin = std::io::stdin();
    let reader = BufReader::with_capacity(4 << 20, stdin.lock());

    // ── Stage 1: Read documents from stdin JSON ────────────────────────────
    let mut documents = Vec::new();
    let mut doc_id: u32 = 1;
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
        fields.insert("text".into(), FieldValue::Text(text));
        documents.push(FrozenDoc {
            doc_id,
            key: None,
            fields,
        });
        doc_id += 1;
    }

    let doc_count = documents.len();
    eprintln!(
        "Read {} docs in {:.2}s",
        doc_count,
        start.elapsed().as_secs_f64()
    );

    // ── Stage 2: Build segment via engine's generic builder ────────────────
    let epoch_data = FrozenEpochData {
        epoch_id: 0,
        doc_count: doc_count as u32,
        documents,
        deleted_doc_ids: Vec::new(),
        op_count: doc_count as u32,
        data_size: 0,
    };

    let builder = CompactSegmentBuilder::new(&ctx, &schema);
    let segment = builder.build_lean(&epoch_data);
    eprintln!(
        "Segment built in {:.2}s",
        start.elapsed().as_secs_f64(),
    );

    // ── Stage 3: Serialize V8 (PFOR-Delta, lazy-loading format) ────────────
    let v8_start = Instant::now();
    let v8_bytes = segment.to_bytes_v8();
    let v8_path = idx_dir.join("segment.v8");
    std::fs::write(&v8_path, &v8_bytes).expect("Failed to write v8 segment");
    eprintln!(
        "v8 serialized: {} bytes ({:.1} MB) in {:.2}s",
        v8_bytes.len(),
        v8_bytes.len() as f64 / (1024.0 * 1024.0),
        v8_start.elapsed().as_secs_f64(),
    );

    eprintln!(
        "Done. Indexed {} docs, total time: {:.2}s",
        doc_count,
        start.elapsed().as_secs_f64(),
    );
}
