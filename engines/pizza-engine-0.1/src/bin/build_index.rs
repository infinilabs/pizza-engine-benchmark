//! Fast index builder for the search benchmark game.
//!
//! Usage: build_index <idx_dir> < corpus.json
//!
//! 3-stage pipeline:
//!   Stage 1 (reader):  stdin → JSON parse → batch of raw texts
//!   Stage 2 (builder): inlined standard analyzer → term interning → sort-merge
//!                       → lean entries → `commit_lean()`
//!   Stage 3 (writer):  serializes V8 segment to disk

use pizza_engine::document::{Property, Schema};
use pizza_engine::store::CompactSegment;
use pizza_engine::store::ScorePrecision;

use rayon::prelude::*;
use rustc_hash::FxHashMap;
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

/// Chunk size for parallel tokenization within a batch.
const CHUNK_SIZE: usize = 8_000;

fn create_schema() -> Schema {
    let mut schema = Schema::new();
    schema
        .add_property("text", Property::as_text(Some("standard")))
        .unwrap();
    schema.freeze();
    schema
}

// ---------------------------------------------------------------------------
// Term interning
// ---------------------------------------------------------------------------

/// Each unique term gets a u32 id.
#[derive(Default)]
struct TermInternPool {
    term_to_id: FxHashMap<String, u32>,
    id_to_term: Vec<String>,
}

impl TermInternPool {
    fn intern(&mut self, term: &str) -> u32 {
        if let Some(&id) = self.term_to_id.get(term) {
            return id;
        }
        let id = self.id_to_term.len() as u32;
        let owned = term.to_string();
        self.term_to_id.insert(owned.clone(), id);
        self.id_to_term.push(owned);
        id
    }

    /// Sort terms lexicographically and return (sorted_terms, old_to_new mapping).
    fn build_sorted_mapping(&self) -> (Vec<String>, Vec<u32>) {
        let mut sorted: Vec<(String, u32)> = self
            .id_to_term
            .iter()
            .enumerate()
            .map(|(old_id, term)| (term.clone(), old_id as u32))
            .collect();
        sorted.sort_unstable_by(|a, b| a.0.cmp(&b.0));

        let mut old_to_new = vec![0u32; self.id_to_term.len()];
        let mut sorted_strs = Vec::with_capacity(sorted.len());
        for (new_id, (s, old_id)) in sorted.into_iter().enumerate() {
            old_to_new[old_id as usize] = new_id as u32;
            sorted_strs.push(s);
        }
        (sorted_strs, old_to_new)
    }
}

/// Index entry: (term_id, doc_id, tf, pos_start) with position tracking.
#[derive(Clone, Copy)]
struct IndexEntry {
    term_id: u32,
    doc_id: u32,
    tf: u32,
    pos_start: u32, // offset into positions arena
}

// ---------------------------------------------------------------------------
// Inlined standard analyzer
// ---------------------------------------------------------------------------

#[inline]
fn is_cjk_ideograph(c: char) -> bool {
    matches!(c,
        '\u{4E00}'..='\u{9FFF}' |
        '\u{3400}'..='\u{4DBF}' |
        '\u{20000}'..='\u{2A6DF}' |
        '\u{2A700}'..='\u{2B73F}' |
        '\u{2B740}'..='\u{2B81F}' |
        '\u{2B820}'..='\u{2CEAF}' |
        '\u{2CEB0}'..='\u{2EBEF}' |
        '\u{30000}'..='\u{3134F}' |
        '\u{F900}'..='\u{FAFF}' |
        '\u{2F800}'..='\u{2FA1F}'
    )
}

/// Tokenize a document using an inlined standard analyzer (lowercase + whitespace/punct split).
/// Collects (term_id, tf, positions) per unique term via the intern pool.
fn tokenize_document(
    text: &str,
    doc_id: u32,
    intern_pool: &mut TermInternPool,
    entries: &mut Vec<IndexEntry>,
    positions: &mut Vec<u32>,
    doc_lengths: &mut FxHashMap<u32, u32>,
) {
    // Lowercase in-place
    let mut buf = text.as_bytes().to_vec();
    buf.make_ascii_lowercase();
    // SAFETY: ASCII lowercase preserves UTF-8 validity
    let lowered = unsafe { std::str::from_utf8_unchecked(&buf) };

    // Track per-term positions for this document
    let mut term_positions: FxHashMap<u32, Vec<u32>> = FxHashMap::default();
    let mut token_count: u32 = 0;
    let mut word_start: usize = 0;

    for (i, c) in lowered.char_indices() {
        if c.is_whitespace() || c.is_ascii_punctuation() {
            if word_start < i {
                let term = &lowered[word_start..i];
                let tid = intern_pool.intern(term);
                term_positions.entry(tid).or_default().push(token_count);
                token_count += 1;
            }
            word_start = i + c.len_utf8();
        } else if is_cjk_ideograph(c) {
            // Flush preceding word
            if word_start < i {
                let term = &lowered[word_start..i];
                let tid = intern_pool.intern(term);
                term_positions.entry(tid).or_default().push(token_count);
                token_count += 1;
            }
            // CJK char as single token
            let term = &lowered[i..i + c.len_utf8()];
            let tid = intern_pool.intern(term);
            term_positions.entry(tid).or_default().push(token_count);
            token_count += 1;
            word_start = i + c.len_utf8();
        }
    }
    // Trailing word
    if word_start < lowered.len() {
        let term = &lowered[word_start..];
        let tid = intern_pool.intern(term);
        term_positions.entry(tid).or_default().push(token_count);
        token_count += 1;
    }

    doc_lengths.insert(doc_id, token_count);

    for (tid, pos_list) in term_positions {
        entries.push(IndexEntry {
            term_id: tid,
            doc_id,
            tf: pos_list.len() as u32,
            pos_start: positions.len() as u32,
        });
        positions.extend_from_slice(&pos_list);
    }
}

/// Parallel chunk processing: tokenize a chunk of (doc_id, text) pairs.
fn process_chunk(chunk: &[(u32, String)]) -> (TermInternPool, Vec<IndexEntry>, Vec<u32>, FxHashMap<u32, u32>) {
    let mut pool = TermInternPool::default();
    let mut entries = Vec::with_capacity(chunk.len() * 50);
    let mut positions = Vec::with_capacity(chunk.len() * 150);
    let mut doc_lengths = FxHashMap::default();
    for (doc_id, text) in chunk {
        tokenize_document(text, *doc_id, &mut pool, &mut entries, &mut positions, &mut doc_lengths);
    }
    (pool, entries, positions, doc_lengths)
}

/// Merge parallel chunk results by re-interning into a single pool.
fn merge_chunks(
    chunks: Vec<(TermInternPool, Vec<IndexEntry>, Vec<u32>, FxHashMap<u32, u32>)>,
) -> (TermInternPool, Vec<IndexEntry>, Vec<u32>, FxHashMap<u32, u32>) {
    let mut merged_pool = TermInternPool::default();
    let total_entries: usize = chunks.iter().map(|(_, e, _, _)| e.len()).sum();
    let total_positions: usize = chunks.iter().map(|(_, _, p, _)| p.len()).sum();
    let mut merged_entries = Vec::with_capacity(total_entries);
    let mut merged_positions = Vec::with_capacity(total_positions);
    let mut merged_doc_lengths = FxHashMap::default();

    for (chunk_pool, chunk_entries, chunk_positions, chunk_doc_lengths) in chunks {
        merged_doc_lengths.extend(chunk_doc_lengths);

        // Build old_id -> new_id mapping for this chunk
        let mut id_remap = vec![0u32; chunk_pool.id_to_term.len()];
        for (old_id, term) in chunk_pool.id_to_term.iter().enumerate() {
            id_remap[old_id] = merged_pool.intern(term);
        }

        let base_pos = merged_positions.len() as u32;
        merged_positions.extend_from_slice(&chunk_positions);

        for entry in chunk_entries {
            merged_entries.push(IndexEntry {
                term_id: id_remap[entry.term_id as usize],
                doc_id: entry.doc_id,
                tf: entry.tf,
                pos_start: entry.pos_start + base_pos,
            });
        }
    }

    (merged_pool, merged_entries, merged_positions, merged_doc_lengths)
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("Usage: build_index <idx_dir> < corpus.json");
        std::process::exit(1);
    }
    let idx_dir = PathBuf::from(&args[1]);
    std::fs::create_dir_all(&idx_dir).expect("Failed to create idx dir");

    let _schema = create_schema();

    let start = Instant::now();
    let stdin = std::io::stdin();
    let reader = BufReader::with_capacity(4 << 20, stdin.lock());

    let mut doc_id: u32 = 1;
    let mut all_docs: Vec<(u32, String)> = Vec::new();
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
        all_docs.push((doc_id, text));
        doc_id += 1;
    }

    let doc_count = all_docs.len();
    eprintln!("Read {} docs in {:.2}s", doc_count, start.elapsed().as_secs_f64());

    // Parallel tokenization
    let chunk_results: Vec<_> = all_docs
        .par_chunks(CHUNK_SIZE)
        .map(|chunk| process_chunk(chunk))
        .collect();
    drop(all_docs); // free memory

    let (pool, mut entries, all_positions, fx_doc_lengths) = merge_chunks(chunk_results);
    eprintln!(
        "Tokenized: {} entries, {} positions in {:.2}s",
        entries.len(), all_positions.len(), start.elapsed().as_secs_f64()
    );

    // Build sorted term mapping and remap term_ids
    let (sorted_terms, old_to_new) = pool.build_sorted_mapping();

    // Remap term_ids in parallel
    entries.par_iter_mut().for_each(|e| {
        e.term_id = old_to_new[e.term_id as usize];
    });

    // Sort by (term_id, doc_id)
    entries.par_sort_unstable_by(|a, b| {
        a.term_id.cmp(&b.term_id).then(a.doc_id.cmp(&b.doc_id))
    });

    // Rearrange positions to match sorted entry order
    let rearrange_start = Instant::now();
    let mut sorted_positions: Vec<u32> = Vec::with_capacity(all_positions.len());
    let mut sorted_pos_offsets: Vec<u32> = Vec::with_capacity(entries.len());
    for e in &entries {
        sorted_pos_offsets.push(sorted_positions.len() as u32);
        let start_pos = e.pos_start as usize;
        sorted_positions.extend_from_slice(&all_positions[start_pos..start_pos + e.tf as usize]);
    }
    drop(all_positions);
    eprintln!(
        "Positions rearranged in {:.2}s",
        rearrange_start.elapsed().as_secs_f64(),
    );

    // Convert to the format build_from_full expects: Vec<(u32, u32, u32)>
    let flat_entries: Vec<(u32, u32, u32)> = entries
        .iter()
        .map(|e| (e.term_id, e.doc_id, e.tf))
        .collect();
    drop(entries);

    // Convert FxHashMap → hashbrown::HashMap
    let doc_lengths: hashbrown::HashMap<u32, u32> = fx_doc_lengths.into_iter().collect();

    eprintln!(
        "Building CompactSegment: {} docs, {} terms, {} entries, {} positions", 
        doc_count, sorted_terms.len(), flat_entries.len(), sorted_positions.len()
    );

    let build_start = Instant::now();
    let segment = CompactSegment::build_from_full(
        &sorted_terms,
        &flat_entries,
        sorted_positions,
        &sorted_pos_offsets,
        &doc_lengths,
        "text",
        ScorePrecision::U16,
    );
    drop(flat_entries);
    drop(sorted_pos_offsets);
    drop(doc_lengths);
    eprintln!(
        "CompactSegment built in {:.2}s",
        build_start.elapsed().as_secs_f64(),
    );

    // Serialize V8 (PFOR-Delta, lazy-loading format)
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
        start.elapsed().as_secs_f64()
    );
}
