use rucene;
use std::env;
use std::io::{self, BufRead};
use std::path::Path;
use rucene::core::index::writer::{IndexWriter, IndexWriterConfig};
use rucene::core::doc::{Fieldable, Field, FieldType, IndexOptions};
use rucene::core::util::VariantValue;
use rucene::core::analysis::WhitespaceTokenizer;
use std::sync::Arc;
use rucene::core::store::directory::FSDirectory;
use serde_derive::Deserialize;

fn indexed_text_field_type() -> FieldType {
    let mut field_type = FieldType::default();
    field_type.index_options = IndexOptions::DocsAndFreqsAndPositions;
    field_type.store_term_vectors = false;
    field_type.store_term_vector_offsets = false;
    field_type.store_term_vector_positions = false;
    field_type
}


struct StringReader {
    text: String,
    index: usize,
}

impl StringReader {
    fn new(text: String) -> Self {
        StringReader { text, index: 0 }
    }
}

impl io::Read for StringReader {
    fn read(&mut self, buf: &mut [u8]) -> io::Result<usize> {
        let remain = buf.len().min(self.text.len() - self.index);
        if remain > 0 {
            buf[..remain].copy_from_slice(&self.text.as_bytes()[self.index..self.index + remain]);
            self.index += remain;
        }
        Ok(remain)
    }
}

fn new_index_text_field(field_name: String, text: String) -> Field {
    let token_stream = WhitespaceTokenizer::new(Box::new(StringReader::new(text)));
    Field::new(
        field_name,
        indexed_text_field_type(),
        None,
        Some(Box::new(token_stream)),
    )
}

fn new_stored_text_field(field_name: String, text: String) -> Field {
    let mut field_type = FieldType::default();
    field_type.stored = true;
    Field::new(
        field_name,
        field_type,
        Some(VariantValue::VString(text)),
        None,
    )
}

#[derive(Deserialize)]
struct Doc {
    id: String,
    text: String
}

impl Doc {
    pub fn rucene_doc(&self) -> Vec<Box<dyn Fieldable>>  {
        vec![
            Box::new(new_stored_text_field("id".to_string(), self.id.clone())),
            Box::new(new_index_text_field("text".to_string(), self.text.to_ascii_lowercase()))
        ]
    }
}


fn main() {
    let args: Vec<String> = env::args().collect();
    main_inner(&Path::new(&args[1])).unwrap();
}


fn main_inner(output_dir: &Path) -> rucene::error::Result<()> {
    let config = Arc::new(IndexWriterConfig::default());
    let directory = Arc::new(FSDirectory::with_path(&output_dir)?);

    let writer = IndexWriter::new(directory, config)?;
    let stdin = std::io::stdin();
    let mut i = 0;
    for line in stdin.lock().lines() {
        let line = line?;
        if line.trim().is_empty() {
            continue;
        }
        if i % 10_000 == 0 {
            println!("doc {}", i)
        }
        // crash if we don't commit from time to time
        if i % 1_100_000 == 0 {
            writer.commit()?;
        }
        i += 1;
        let doc_obj: Doc = serde_json::from_str(&line)?;
        writer.add_document(doc_obj.rucene_doc())?;
    }
    writer.commit()?;
    writer.force_merge(1, true)?;
    Ok(())
}
