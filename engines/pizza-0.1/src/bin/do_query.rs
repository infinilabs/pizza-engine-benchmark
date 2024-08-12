use std::collections::BinaryHeap;
use std::env;
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;
use std::rc::Rc;
use std::sync::Arc;
use std::time::Instant;
use engine::document::{Document, FieldValue, Property, Schema};
use engine::{Context, EngineBuilder, Snapshot};
use engine::analysis::{BUILTIN_ANALYZER_STANDARD, BUILTIN_ANALYZER_WHITESPACE};
use engine::dictionary::DatTermDict;
use engine::search::{OriginalQuery, QueryContext};
use engine::store::{MemoryStore};
use hashbrown::HashMap;
use spin::RwLock;

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

    let mut builder = EngineBuilder::new();
    builder.set_schema(schema);
    builder.set_term_dict(DatTermDict::new(0));
    builder.set_data_store(Arc::new(RwLock::new(MemoryStore::new())));

    let mut engine = builder.build();
    engine.start();

    let mut writer = engine.acquire_writer();
    let searcher = engine.acquire_searcher();

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
                writer.flush();
                let duration = start.elapsed();
                // println!("{} in {}s", seq.current(),duration.as_secs());
                start = Instant::now();
            }
            let mut fields = HashMap::new();
            doc.add_fields_from_json(&line,&mut fields);
            writer.add_document(doc);
        }
        writer.flush();
    }

    // println!("all docs:{}",store.index.invert_index.get_all_doc_ids().len());

    let snapshot = engine.create_snapshot();
    // let guard = pprof::ProfilerGuard::new(10000).unwrap();

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

        let raw_query = OriginalQuery::QueryString(keyword.to_string());
        let mut query_context = QueryContext::new(raw_query, false);
        query_context.default_field="text".into();

        let query=searcher.parse_query(&query_context);
        let schema=engine.get_schema();

        let count;
        match command {
            "COUNT" => {
                let result = searcher.search(&query_context, &schema,&query, &snapshot);
                // println!("query:{:?}",result.explains);
                count = result.hits.len()
            }
            "TOP_10" => {
                // for i in 0..100{
                    let result = searcher.search(&query_context, &schema,&query, &snapshot);
                // }
                count = 1
            }
            "TOP_100" => {
                let result = searcher.search(&query_context, &schema,&query, &snapshot);
                count = 1
            }
            "TOP_100_COUNT" => {
                let result = searcher.search(&query_context, &schema,&query, &snapshot);
                count = result.hits.len()
            }
            _ => {
                println!("UNSUPPORTED");
                continue;
            }
        }
        println!("{}", count);
    }

    // if let Ok(report) = guard.report().build() {
    //     let file = File::create("search-flamegraph.svg").unwrap();
    //     let mut options = pprof::flamegraph::Options::default();
    //     options.image_width = Some(1024);
    //     report.flamegraph_with_options(file, &mut options).unwrap();
    // };
}
