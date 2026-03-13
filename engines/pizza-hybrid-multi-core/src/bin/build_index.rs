//! Index builder for pizza-hybrid-multi-core: immutable V8 segments + optional memory remainder.
//!
//! Usage: build_index <idx_dir> < corpus.json
//!
//! Reads docs from stdin JSON, then:
//!   - Builds immutable CompactSegment V8 files for all full 1M-doc chunks
//!   - Also builds one final partial immutable segment for any remaining docs
//!   - Writes corpus_mem.bin only for docs intentionally left for mutable layers

use pizza_engine::analysis::BUILTIN_ANALYZER_STANDARD;
use pizza_engine::context::Context;
use pizza_engine::document::{FieldValue, Property, Schema};
use pizza_engine::store::CompactSegmentBuilder;
use pizza_engine::writer::builder::{FrozenDoc, FrozenEpochData};

use serde::Deserialize;
use std::env;
use std::io::{BufRead, BufReader, BufWriter, Write};
use std::path::PathBuf;
use std::time::Instant;

const DOCS_PER_SEGMENT: usize = 1_000_000;
const NUM_IMMUTABLE_SEGMENTS: usize = 3;

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

    // ── Stage 1a: Read all documents from stdin ────────────────────────
    let mut all_texts: Vec<String> = Vec::new();
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
        all_texts.push(input_doc.text.unwrap_or_default());
    }
    let total_docs = all_texts.len();
    eprintln!(
        "Read {} docs in {:.2}s",
        total_docs,
        start.elapsed().as_secs_f64()
    );

    // ── Stage 1b: Compute global corpus statistics ─────────────────────
    // Tokenize every document (without building a full index) to obtain:
    //   * global_total_tokens: sum of token counts across all documents
    //   * global_term_dfs: per-term document frequency (# docs containing term)
    //
    // These are needed to normalise per-segment BM25 scores so that docs
    // from different segments are scored on the same scale (global avgdl
    // and global IDF), making WAND top-k correct across segments.
    eprintln!("Computing global corpus stats...");
    let stats_start = Instant::now();
    let analyzer = ctx
        .analysis
        .get_analyzer(BUILTIN_ANALYZER_STANDARD)
        .expect("standard analyzer must exist");
    let mut global_total_tokens: u64 = 0;
    let mut global_term_dfs: hashbrown::HashMap<String, u32> = hashbrown::HashMap::new();
    {
        let mut doc_terms: hashbrown::HashSet<String> = hashbrown::HashSet::new();
        for text in &all_texts {
            let mut text_clone = text.clone();
            let tokens = analyzer.analyze_and_return_tokens(&mut text_clone);
            global_total_tokens += tokens.len() as u64;
            doc_terms.clear();
            for token in tokens {
                doc_terms.insert(token.term.into_owned());
            }
            for term in &doc_terms {
                *global_term_dfs.entry(term.clone()).or_insert(0) += 1;
            }
        }
    }
    let global_doc_count = total_docs as u32;
    eprintln!(
        "Global stats: {} docs, {} total tokens, {} unique terms in {:.2}s",
        global_doc_count,
        global_total_tokens,
        global_term_dfs.len(),
        stats_start.elapsed().as_secs_f64()
    );

    // ── Stage 2: Build immutable V8 segments (at least 3; include final
    //            partial segment so query-time doc universe matches corpus) ──
    let num_segments = core::cmp::max(
        NUM_IMMUTABLE_SEGMENTS,
        (total_docs + DOCS_PER_SEGMENT - 1) / DOCS_PER_SEGMENT,
    );
    let immutable_docs = total_docs.min(num_segments * DOCS_PER_SEGMENT);
    for seg_idx in 0..num_segments {
        let seg_start = seg_idx * DOCS_PER_SEGMENT;
        let seg_end = ((seg_idx + 1) * DOCS_PER_SEGMENT).min(immutable_docs);
        if seg_start >= seg_end {
            break;
        }

        let epoch_id = (seg_idx + 1) as u64;
        let mut documents = Vec::with_capacity(seg_end - seg_start);
        for i in seg_start..seg_end {
            let doc_id = (i + 1) as u32; // 1-based
            let mut fields = hashbrown::HashMap::new();
            fields.insert("text".into(), FieldValue::Text(all_texts[i].clone()));
            documents.push(FrozenDoc {
                doc_id,
                key: None,
                fields,
            });
        }

        let doc_count = documents.len() as u32;
        let epoch_data = FrozenEpochData {
            epoch_id,
            doc_count,
            documents,
            deleted_doc_ids: Vec::new(),
            op_count: doc_count,
            data_size: 0,
        };

        let seg_build_start = Instant::now();
        let builder = CompactSegmentBuilder::new(&ctx, &schema);
        let mut segment = builder.build_lean(&epoch_data);
        // Normalise scores to global corpus statistics so that BM25 scores
        // from this segment are directly comparable to scores from other
        // segments (same global avgdl and global IDF for every term).
        segment.normalize_to_global_stats(global_doc_count, global_total_tokens, &global_term_dfs);
        eprintln!(
            "  Segment {} built ({} docs) in {:.2}s",
            epoch_id,
            doc_count,
            seg_build_start.elapsed().as_secs_f64()
        );

        let v8_bytes = segment.to_bytes_v8();
        let v8_path = idx_dir.join(format!("segment_{}.v8", epoch_id));
        std::fs::write(&v8_path, &v8_bytes).expect("Failed to write V8 segment");
        eprintln!(
            "  Segment {} written: {:.1} MB",
            epoch_id,
            v8_bytes.len() as f64 / (1024.0 * 1024.0)
        );
    }

    // ── Stage 3: Save remaining docs as corpus_mem.bin ─────────────────
    // When total_docs is an exact multiple of 1M, this file can be empty and
    // do_query will use immutable-only fast mode.
    let mem_start_idx = immutable_docs;
    let out_path = idx_dir.join("corpus_mem.bin");
    let out = std::fs::File::create(&out_path).expect("create corpus_mem.bin");
    let mut writer = BufWriter::with_capacity(4 << 20, out);

    // Write the starting doc_id (so do_query knows where IDs begin)
    let start_doc_id = (mem_start_idx + 1) as u32;
    writer.write_all(&start_doc_id.to_le_bytes()).unwrap();

    let mut mem_count: u32 = 0;
    for i in mem_start_idx..total_docs {
        let text_bytes = all_texts[i].as_bytes();
        let len = text_bytes.len() as u32;
        writer.write_all(&len.to_le_bytes()).unwrap();
        writer.write_all(text_bytes).unwrap();
        mem_count += 1;
    }
    writer.flush().unwrap();

    eprintln!(
        "Saved {} docs to corpus_mem.bin (starting doc_id={})",
        mem_count, start_doc_id
    );
    eprintln!(
        "Done. Total: {} docs, {} immutable + {} memory, time: {:.2}s",
        total_docs,
        immutable_docs,
        mem_count,
        start.elapsed().as_secs_f64(),
    );
}
