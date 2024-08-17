use hashbrown;
use futures::executor::block_on;
use std::env;
use std::fs::{File, OpenOptions};
use std::io::BufRead;
use std::path::Path;
use std::rc::Rc;
use engine::document::{Document, FieldValue, Property, Schema};
use engine::context::Context;
use engine::context::Snapshot;
use engine::{ EngineBuilder};
pub use engine::analysis::{BUILTIN_ANALYZER_STANDARD, BUILTIN_ANALYZER_WHITESPACE};
use engine::store::{MemoryStore};
use hashbrown::HashMap;
use std::io::Write;
use std::sync::{Arc};
use spin::RwLock;
use std::time::Instant;
use engine::dictionary::DatTermDict;
pub use pizza_common as common;
pub use pizza_engine as engine;

pub fn main() {
    let guard = pprof::ProfilerGuard::new(10000).unwrap();

    let args: Vec<String> = env::args().collect();
    let file_path=&args[1];

    //prepare index
    let mut schema = Schema::new();
    schema.properties.add_property("id", Property::as_keyword());
    schema.properties.add_property("text", Property::as_text(Some(BUILTIN_ANALYZER_WHITESPACE)));
    schema.freeze();

    let mut builder = EngineBuilder::new();
    builder.set_schema(schema);
    builder.set_term_dict(DatTermDict::new(0));
    builder.set_data_store(Arc::new(RwLock::new(MemoryStore::new())));

    let mut engine = builder.build();
    engine.start();
    let mut writer = engine.acquire_writer();
    //build index
    {
        let mut seq=common::utils::sequencer::Sequencer::new(0,1,5_000_000);
        let stdin = std::io::stdin();

        let mut start = Instant::now();
        for line in stdin.lock().lines() {
            let line = line.unwrap();
            if line.trim().is_empty() {
                continue;
            }

            //build index
            let mut  doc = Document::new(seq.next().unwrap());
            if seq.current() % 100_000 == 0 {
                writer.flush();
                let duration = start.elapsed();
                println!("{} in {}ms", seq.current(),duration.as_millis());
                start = Instant::now();
            }
            let mut fields = HashMap::new();
            doc.add_fields_from_json(&line,&mut fields);
            writer.add_document(doc);

            if seq.current()>=300000{
                break;
            }

        }
    }

    if let Ok(report) = guard.report().build() {
        let file = File::create("index-flamegraph.svg").unwrap();
        let mut options = pprof::flamegraph::Options::default();
        options.image_width = Some(1024);
        report.flamegraph_with_options(file, &mut options).unwrap();
    };
}
