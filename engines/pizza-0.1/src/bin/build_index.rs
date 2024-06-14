use hashbrown;
use futures::executor::block_on;
use std::env;
use std::fs::{File, OpenOptions};
use std::io::BufRead;
use std::path::Path;
use std::rc::Rc;
use engine::document::{Document, FieldValue, Property, Schema};
use engine::{Context, EngineConfig, Snapshot};
use engine::analysis::{BUILTIN_ANALYZER_STANDARD, BUILTIN_ANALYZER_WHITESPACE};
use engine::search::{QueryEngine, RawQuery};
use engine::store::StoreEngine;
use hashbrown::HashMap;
use std::io::Write;
use std::time::Instant;

fn main() {
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

    // let mut schema = Schema::new();
    // schema.properties.add_property("id", Property::as_keyword());
    // schema
    //     .properties
    //     .add_property("title", Property::as_text(Some("standard")));
    //
    // schema.properties.add_property(
    //     "content",
    //     Property::as_object()
    //         .add_property("slogan", Property::as_text(Some("whitespace")))
    //         .add_property("since", Property::as_integer())
    //         .add_property("website", Property::as_keyword())
    //         .add_property("tags", Property::as_keyword())
    //         .to_owned(),
    // );
    //
    // schema.freeze();
    //
    // let cfg = EngineConfig::new(0, 1);
    // let context = Context::new(cfg, schema);
    // let ctx: Rc<Context> = Rc::new(context);
    // let mut store = StoreEngine::new(ctx.clone());
    // let query = QueryEngine::new(ctx.clone());
    //
    // let doc = Document {
    //     id: 1,
    //     key: Some("doc1".to_string()),
    //     fields: {
    //         let mut m = HashMap::new();
    //         let mut nested_fields = HashMap::new();
    //         nested_fields.insert(
    //             "slogan".to_string(),
    //             FieldValue::Text("It's time for Pizza! Everyone loves Pizza!".to_string()),
    //         );
    //         nested_fields.insert("since".to_string(), FieldValue::Integer(2021));
    //         nested_fields.insert(
    //             "website".to_string(),
    //             FieldValue::Text("http://pizza.rs".to_string()),
    //         );
    //         nested_fields.insert(
    //             "tags".to_string(),
    //             FieldValue::Array(vec![
    //                 FieldValue::Text("search".to_string()),
    //                 FieldValue::Text("engine".to_string()),
    //             ]),
    //         );
    //
    //         m.insert(
    //             "id".to_string(),
    //             FieldValue::Text("pizza-release-blog-1".to_string()),
    //         );
    //         m.insert(
    //             "title".to_string(),
    //             FieldValue::Text("Introduction to Pizza".to_string()),
    //         );
    //         m.insert("content".to_string(), FieldValue::Object(nested_fields));
    //         m
    //     },
    // };
    //
    // store.add_document(&doc);
    //
    // let snapshot = ctx.create_snapshot();
    // tracing::log::info!("created snapshot: {:?}", snapshot);
    //
    // let doc = Document {
    //     id: 2,
    //     key: Some("doc2".to_string()),
    //     fields: {
    //         let mut m = HashMap::new();
    //         let mut nested_fields = HashMap::new();
    //         nested_fields.insert(
    //             "slogan".to_string(),
    //             FieldValue::Text("Pizza v1.0 is ready to download.".to_string()),
    //         );
    //         nested_fields.insert(
    //             "website".to_string(),
    //             FieldValue::Text("http://pizza.rs/blog/v1.0".to_string()),
    //         );
    //         nested_fields.insert(
    //             "tags".to_string(),
    //             FieldValue::Array(vec![
    //                 FieldValue::Text("release".to_string()),
    //                 FieldValue::Text("v1.0".to_string()),
    //             ]),
    //         );
    //
    //         m.insert(
    //             "id".to_string(),
    //             FieldValue::Text("pizza-release-blog-2".to_string()),
    //         );
    //         m.insert(
    //             "title".to_string(),
    //             FieldValue::Text("Pizza V1.0 just released".to_string()),
    //         );
    //         m.insert("content".to_string(), FieldValue::Object(nested_fields));
    //         m
    //     },
    // };
    //
    // store.add_document(&doc);
    //
    // let doc3_str = r#"
    //     {
    //        "_id":3,
    //        "_key":"doc3",
    //        "_source":{
    //           "content":{
    //              "tags":[
    //                 "pizza"
    //              ]
    //           },
    //           "id":"pizza-news-blog-3",
    //           "title":"A Pizza, in Rust flavour."
    //        }
    //     }
    //     "#;
    // let doc3: Document = serde_json::from_str(doc3_str).unwrap();
    // store.add_document(&doc3);
    //
    // // Now we should have a complete query context, the collections/shards/mapping/setting to search
    // // Capture a soft snapshot of the datasource and the metadata
    // let snapshot = ctx.create_snapshot();
    // tracing::log::info!("created snapshot: {:?}", snapshot);
    //
    // //let's search
    // process_and_assert(&query, &store, &snapshot, "pizza", &[1, 2, 3], 3);

}
