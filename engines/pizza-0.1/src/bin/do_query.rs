use std::collections::BinaryHeap;
use std::env;
use std::io::BufRead;
use std::path::Path;
use std::rc::Rc;
use engine::document::{Document, FieldValue, Property, Schema};
use engine::{Context, EngineConfig, Snapshot};
use engine::analysis::BUILTIN_ANALYZER_STANDARD;
use engine::search::{QueryEngine, RawQuery};
use engine::store::StoreEngine;
use hashbrown::HashMap;

fn main() {
    let args: Vec<String> = env::args().collect();
    main_inner(&Path::new(&args[1]))
}

fn main_inner(index_dir: &Path){

    //prepare index
    let mut schema = Schema::new();
    schema.properties.add_property("text", Property::as_text(Some(BUILTIN_ANALYZER_STANDARD)));
    schema.freeze();

    let cfg = EngineConfig::new(0, 1);
    let context = Context::new(cfg, schema);
    let ctx: Rc<Context> = Rc::new(context);
    let mut store = StoreEngine::new(ctx.clone());
    let query = QueryEngine::new(ctx.clone());

    //build index
    let doc = Document {
        id: 1,
        key: None,
        fields: {
            let mut m = HashMap::new();
            m.insert(
                "text".to_string(),
                FieldValue::Text("pizza-release-blog-1".to_string()),
            );
            m
        },
    };
    store.add_document(&doc);

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

        let raw_query = &RawQuery::QueryString(command.to_string());
        let count;
        match command {
            "COUNT" => {
                let result = query.process_query(&store, &snapshot, raw_query);
                count = result.documents.len()
            }
            "TOP_100" => {
                let result = query.process_query(&store, &snapshot, raw_query);
                count = result.documents.len()
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
