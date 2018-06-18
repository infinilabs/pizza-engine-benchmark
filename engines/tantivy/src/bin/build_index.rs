#[macro_use]
extern crate tantivy;
extern crate core;

extern crate serde;
#[macro_use]
extern crate serde_derive;
extern crate serde_json;


use tantivy::schema::SchemaBuilder;
use tantivy::schema::IntOptions;
use tantivy::Index;

use std::env;
use std::io::BufRead;
use std::io::Result;
use std::path::Path;
use tantivy::schema::Cardinality;
use tantivy::schema::{TEXT, STORED};

fn main() {
    let args: Vec<String> = env::args().collect();
    main_inner(&Path::new(&args[1])).unwrap();
}

#[derive(Debug, Serialize, Deserialize)]
struct InputDocument {
    id: String,
    text: String
}

fn main_inner(output_dir: &Path) -> Result<()> {
    let mut schema_builder = SchemaBuilder::default();

    let id_field = schema_builder.add_text_field("id", STORED);
    let text_field = schema_builder.add_text_field("text", TEXT);

    let schema = schema_builder.build();

    let index = Index::create_dir(output_dir, schema).expect("failed to create index");

    // 4 GB heap
    let mut index_writer = index.writer(200_000_000).expect("failed to create index writer");

    let stdin = std::io::stdin();

    for line in stdin.lock().lines() {
        let line = line?;
        if line.trim().is_empty() {
            continue;
        }
        let input_doc: InputDocument = serde_json::from_str(&line)?;
        index_writer.add_document(doc!(
            id_field => input_doc.id,
            text_field => input_doc.text
        ));
    }

    index_writer.commit().expect("failed to commit");
    index_writer.wait_merging_threads().expect("Failed while waiting merging threads");
    Ok(())
}
