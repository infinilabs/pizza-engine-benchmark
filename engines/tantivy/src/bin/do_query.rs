#![macro_use]
extern crate tantivy;

use tantivy::Index;
use tantivy::query::QueryParser;
use tantivy::tokenizer::TokenizerManager;
use tantivy::collector::{chain, TopCollector, CountCollector};

use std::env;
use std::io::BufRead;
use std::io::Result;
use std::path::Path;

fn main() {
    let args: Vec<String> = env::args().collect();
    main_inner(&Path::new(&args[1])).unwrap()
}

fn main_inner(index_dir: &Path) -> Result<()> {
    let index = Index::open(index_dir).expect("failed to open index");
    let text_field = index.schema().get_field("text").expect("no all field?!");
    let query_parser = QueryParser::new(
        index.schema(),
        vec![text_field],
        TokenizerManager::default());

    let searcher = index.searcher();

    let stdin = std::io::stdin();
    for line_res in stdin.lock().lines() {
        let line = line_res?;
        let fields: Vec<&str> = line.split("\t").collect();
        assert_eq!(fields.len(), 2, "Expected a line in the format <COMMAND> query.");
        let command = fields[0];
        let query = query_parser.parse_query(fields[1]).expect("failed to parse query!");
        let count;
        match command {
            "COUNT" => {
                count = query.count(&*searcher).expect("Search failed");
            }
            "NO_SCORE" => {
                let mut count_collector = CountCollector::default();
                query.search(&*searcher, &mut count_collector);
                count = count_collector.count();
            }
            "TOP_10" => {
                let mut top_k = TopCollector::with_limit(10);
                let mut count_collector = CountCollector::default();
                {
                    let mut multi_collector = chain().push(&mut top_k).push(&mut count_collector);
                    query.search(&*searcher, &mut multi_collector).unwrap();
                }
                count = count_collector.count();
            }
            _ => {
                panic!("Command unknown {}", command);
            }
        }
        println!("{}", count);
    }

    Ok(())
}
