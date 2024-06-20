use std::collections::BinaryHeap;
use std::env;
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;
use std::rc::Rc;
use std::time::Instant;
use engine::document::{Document, FieldValue, Property, Schema};
use engine::{Context, EngineConfig, Snapshot};
use engine::analysis::{BUILTIN_ANALYZER_STANDARD, BUILTIN_ANALYZER_WHITESPACE};
use engine::search::{QueryEngine, RawQuery};
use engine::store::StoreEngine;
use hashbrown::HashMap;

fn main() {
    let args: Vec<String> = env::args().collect();
    main_inner(&Path::new(&args[1]))
}

fn main_inner(index_dir: &Path){

    //prepare search
    let mut schema = Schema::new();
    schema.properties.add_property("id", Property::as_keyword());
    schema.properties.add_property("text", Property::as_text(Some(BUILTIN_ANALYZER_STANDARD)));
    schema.freeze();

    let cfg = EngineConfig::new(0, 1);
    let context = Context::new(cfg, schema);
    let ctx: Rc<Context> = Rc::new(context);
    let mut store = StoreEngine::new(ctx.clone());
    let query = QueryEngine::new(ctx.clone());

    //build index
    {
        let mut seq=common::utils::sequencer::Sequencer::new(0,1,5_000_000);

        let file_path = "/Users/medcl/Documents/rust/search-benchmark-game/corpus-lite.json";
        let file = File::open(file_path).expect("Failed to open file");
        let reader = BufReader::new(file);

        let mut start = Instant::now();

        for line in reader.lines() {
            let line = line.expect("Failed to read line");
            if line.trim().is_empty() {
                continue;
            }
            //build index
            let mut  doc = Document::new(seq.next().unwrap());
            if seq.current() % 100_000 == 0 {
                let duration = start.elapsed();
                // println!("{} in {}s", seq.current(),duration.as_secs());
                start = Instant::now();
            }
            doc.add_fields_from_json(&line);
            store.add_document(&doc);

        }
    }

    // println!("all docs:{}",store.index.invert_index.get_all_doc_ids().len());

    let snapshot = ctx.create_snapshot();

    let stdin = std::io::stdin();
    for line_res in stdin.lock().lines() {
        let line = line_res.unwrap();
        let fields: Vec<&str> = line.split("\t").collect();
        assert_eq!(
            fields.len(),
            2,
            "Expected a line in the format <COMMAND> query."
        );
        let command = fields[0];
        let keyword = fields[1];

        let raw_query = &RawQuery::QueryString(keyword.to_string());
        let count;
        match command {
            "COUNT" => {
                let result = query.process_query(&store, &snapshot, raw_query);
                // println!("query:{:?}",result.explains);
                count = result.documents.len()
            }
            "TOP_10" => {
                let result = query.process_query(&store, &snapshot, raw_query);
                count = 1
            }
            "TOP_100" => {
                let result = query.process_query(&store, &snapshot, raw_query);
                count = 1
            }
            "TOP_100_COUNT" => {
                let result = query.process_query(&store, &snapshot, raw_query);
                count = result.documents.len()
            }
            _ => {
                println!("UNSUPPORTED");
                continue;
            }
        }
        println!("{}", count);
    }
}
