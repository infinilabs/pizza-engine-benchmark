use hashbrown;
use futures::executor::block_on;
use std::env;
use std::fs::{File, OpenOptions};
use std::io::BufRead;
use std::path::Path;
use std::rc::Rc;
use engine::document::{Document, FieldValue, Property, Schema};
use engine::{Context, EngineConfig, Snapshot};
pub use engine::analysis::{BUILTIN_ANALYZER_STANDARD, BUILTIN_ANALYZER_WHITESPACE};
use engine::search::{QueryEngine, RawQuery};
use engine::store::StoreEngine;
use hashbrown::HashMap;
use std::io::Write;
use std::time::Instant;

pub fn main() {
    let guard = pprof::ProfilerGuard::new(10000).unwrap();

    let args: Vec<String> = env::args().collect();
    let file_path=&args[1];

    //prepare index
    let mut schema = Schema::new();
    schema.properties.add_property("text", Property::as_text(Some(BUILTIN_ANALYZER_WHITESPACE)));
    schema.freeze();

    let cfg = EngineConfig::new(0, 1);
    let context = Context::new(cfg, schema);
    let ctx: Rc<Context> = Rc::new(context);
    let mut store = StoreEngine::new(ctx.clone());
    let query = QueryEngine::new(ctx.clone());

    //build index
    {
        let mut seq=common::utils::sequencer::Sequencer::new(0,1,5_000_000);
        let stdin = std::io::stdin();

        // let file_path = Path::new(file_path).join("log.dict");
        // let mut file = OpenOptions::new()
        //     .create(true)
        //     .append(true)
        //     .open(file_path).unwrap();

        let mut start = Instant::now();
        for line in stdin.lock().lines() {
            let line = line.unwrap();
            if line.trim().is_empty() {
                continue;
            }

            //// write to file
            // writeln!(file, "{}", line).unwrap();

            //build index
            let mut  doc = Document::new(seq.next().unwrap());
            if seq.current() % 100_000 == 0 {
                let duration = start.elapsed();
                println!("{} in {}s", seq.current(),duration.as_secs());
                start = Instant::now();
            }
            doc.add_fields_from_json(&line);
            store.add_document(&doc);

            if seq.current()>=300000{
                break;
            }

        }

        let snapshot = ctx.create_snapshot();
    }

    if let Ok(report) = guard.report().build() {
        let file = File::create("flamegraph.svg").unwrap();
        let mut options = pprof::flamegraph::Options::default();
        options.image_width = Some(2500);
        report.flamegraph_with_options(file, &mut options).unwrap();
    };
}
