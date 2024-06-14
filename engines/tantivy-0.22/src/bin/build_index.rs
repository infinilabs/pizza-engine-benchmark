use std::env;
use std::io::{BufRead, BufReader};
use std::path::Path;
use std::time::Instant;
use futures::executor::block_on;
use tantivy::schema::*;
use tantivy::{Document, Index, IndexWriter};
use serde::Deserialize;
use serde_json::Value;
use tantivy::doc;


fn main() {
    let args: Vec<String> = env::args().collect();
    main_inner(&Path::new(&args[1])).unwrap();
}

#[derive(Deserialize)]
struct InputDocument {
    id: Option<String>,
    text: Option<String>,
}

fn create_schema() -> Schema {
    let mut schema_builder = Schema::builder();
    schema_builder.add_text_field("id", STORED);
    schema_builder.add_text_field("text", TEXT);
    schema_builder.build()
}

fn main_inner(output_dir: &Path) -> tantivy::Result<()> {
    env_logger::init();

    let schema = create_schema();
    let index = Index::create_in_dir(output_dir, schema.clone())?;
    let mut start = Instant::now();

    let mut i = 0;
    {
        let mut index_writer = index.writer_with_num_threads(4, 2_000_000_000)?;
        let stdin = std::io::stdin();
        let reader = BufReader::new(stdin.lock());

        let id_field = schema.get_field("id").unwrap();
        let text_field = schema.get_field("text").unwrap();

        for line in reader.lines() {
            let line = line?;
            if line.trim().is_empty() {
                continue;
            }
            let input_doc: Result<InputDocument, _> = serde_json::from_str(&line);
            if let Ok(input_doc) = input_doc {
                index_writer.add_document(doc!(
                    id_field => input_doc.id.unwrap_or_default(),
                    text_field => input_doc.text.unwrap_or_default()
                ))?;
            } else {
                eprintln!("Failed to parse line as JSON: {}", line);
            }

            i += 1;
            if i % 100_000 == 0 {
                let duration = start.elapsed();
                println!("{} documents processed in {}ms", i, duration.as_millis());
                start = Instant::now();
            }
        }

        index_writer.commit()?;
        index_writer.wait_merging_threads()?;
    }

    // let segment_ids = index.searchable_segment_ids()?;
    // let mut index_writer: IndexWriter<D> = index.writer(1_500_000_000)?;
    // block_on(index_writer.merge(&segment_ids))?;
    // block_on(index_writer.garbage_collect_files())?;
    Ok(())
}
