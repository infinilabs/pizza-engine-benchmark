import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.file.Path;
import java.nio.file.Paths;

import org.apache.lucene.analysis.CharArraySet;
import org.apache.lucene.analysis.standard.StandardAnalyzer;
import org.apache.lucene.index.DirectoryReader;
import org.apache.lucene.index.IndexReader;
import org.apache.lucene.index.StoredFields;
import org.apache.lucene.queryparser.classic.ParseException;
import org.apache.lucene.queryparser.classic.QueryParser;
import org.apache.lucene.search.IndexSearcher;
import org.apache.lucene.search.Query;
import org.apache.lucene.search.ScoreDoc;
import org.apache.lucene.search.TopScoreDocCollector;
import org.apache.lucene.search.similarities.BM25Similarity;
import org.apache.lucene.store.FSDirectory;

public class DoQuery {
    public static void main(String[] args) throws IOException, ParseException {
        final Path indexDir = Paths.get(args[0]);
        try (IndexReader reader = DirectoryReader.open(FSDirectory.open(indexDir));
                BufferedReader bufferedReader = new BufferedReader(new InputStreamReader(System.in))) {
            final IndexSearcher searcher = new IndexSearcher(reader);
            searcher.setQueryCache(null);
            searcher.setSimilarity(new BM25Similarity(1.2f, 0.75f));
            final QueryParser queryParser = new QueryParser("text", new StandardAnalyzer(CharArraySet.EMPTY_SET));
            String line;
            while ((line = bufferedReader.readLine()) != null) {
                final String[] fields = line.trim().split("\t");
                assert fields.length == 2;
                final String command = fields[0];
                final String query_str = fields[1];
                Query query = queryParser.parse(query_str);
                final int count;
                switch (command) {
                case "COUNT":
                case "UNOPTIMIZED_COUNT":
                    count = searcher.count(query);
                    break;
                case "TOP_10":
                {
                    final TopScoreDocCollector topScoreDocCollector = TopScoreDocCollector.create(10, 10);
                    searcher.search(query, topScoreDocCollector);
                    count = 1;
                }
                break;
                case "TOP_100":
                {
                    final TopScoreDocCollector topScoreDocCollector = TopScoreDocCollector.create(100, 100);
                    searcher.search(query, topScoreDocCollector);
                    count = 1;
                }
                break;
                case "TOP_1000":
                {
                    final TopScoreDocCollector topScoreDocCollector = TopScoreDocCollector.create(1000, 1000);
                    searcher.search(query, topScoreDocCollector);
                    count = 1;
                }
                break;
                case "TOP_10_COUNT":
                {
                    final TopScoreDocCollector topScoreDocCollector = TopScoreDocCollector.create(10, Integer.MAX_VALUE);
                    searcher.search(query, topScoreDocCollector);
                    count = topScoreDocCollector.getTotalHits();
                }
                break;
                case "TOP_100_COUNT":
                {
                    final TopScoreDocCollector topScoreDocCollector = TopScoreDocCollector.create(100, Integer.MAX_VALUE);
                    searcher.search(query, topScoreDocCollector);
                    count = topScoreDocCollector.getTotalHits();
                }
                break;
                case "TOP_1000_COUNT":
                {
                    final TopScoreDocCollector topScoreDocCollector = TopScoreDocCollector.create(1000, Integer.MAX_VALUE);
                    searcher.search(query, topScoreDocCollector);
                    count = topScoreDocCollector.getTotalHits();
                }
                break;
                default:
                    // Handle CHECK_* commands
                    if (command.startsWith("CHECK_")) {
                        String checkType = command.substring(6); // e.g. "COUNT", "TOP_10", "TOP_100"
                        StoredFields storedFields = searcher.storedFields();
                        switch (checkType) {
                        case "COUNT":
                            System.out.println(searcher.count(query));
                            break;
                        case "TOP_10":
                        case "TOP_100":
                        case "TOP_1000":
                        {
                            int n = Integer.parseInt(checkType.substring(4));
                            final TopScoreDocCollector collector = TopScoreDocCollector.create(n, n);
                            searcher.search(query, collector);
                            ScoreDoc[] scoreDocs = collector.topDocs().scoreDocs;
                            // Collect (lineNumber, score) pairs
                            long[][] results = new long[scoreDocs.length][1];
                            float[] scores = new float[scoreDocs.length];
                            String[] ids = new String[scoreDocs.length];
                            for (int i = 0; i < scoreDocs.length; i++) {
                                ids[i] = storedFields.document(scoreDocs[i].doc).get("id");
                                scores[i] = scoreDocs[i].score;
                            }
                            // Build index array and sort by (score DESC, lineNumber ASC)
                            Integer[] indices = new Integer[scoreDocs.length];
                            for (int i = 0; i < indices.length; i++) indices[i] = i;
                            java.util.Arrays.sort(indices, (a, b) -> {
                                int cmp = Float.compare(scores[b], scores[a]);
                                if (cmp != 0) return cmp;
                                return Long.compare(Long.parseLong(ids[a]), Long.parseLong(ids[b]));
                            });
                            StringBuilder sb = new StringBuilder();
                            for (int i = 0; i < indices.length; i++) {
                                if (i > 0) sb.append(",");
                                sb.append(ids[indices[i]]).append(":").append(String.format("%.6f", scores[indices[i]]));
                            }
                            System.out.println(sb.toString());
                            break;
                        }
                        default:
                            System.out.println("UNSUPPORTED");
                            break;
                        }
                        continue;  // skip the println(count) below
                    } else {
                        System.out.println("UNSUPPORTED");
                        count = 0;
                    }
                    break;
                }
                System.out.println(count);
            }
        }
    }
}
