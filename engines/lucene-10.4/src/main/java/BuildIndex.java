import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.UncheckedIOException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

import org.apache.lucene.analysis.CharArraySet;
import org.apache.lucene.analysis.standard.StandardAnalyzer;
import org.apache.lucene.document.Document;
import org.apache.lucene.document.Field;
import org.apache.lucene.document.StoredField;
import org.apache.lucene.document.TextField;
import org.apache.lucene.index.IndexWriter;
import org.apache.lucene.index.IndexWriterConfig;
import org.apache.lucene.index.IndexWriterConfig.OpenMode;
import org.apache.lucene.store.Directory;
import org.apache.lucene.store.FSDirectory;

import com.eclipsesource.json.Json;
import com.eclipsesource.json.JsonObject;

public class BuildIndex {

        public static void main(String[] args) throws Exception {
                if (args.length < 1) {
                        System.err.println("Usage: java BuildIndex <output_path>");
                        System.exit(1);
                }

                final Path outputPath = Paths.get(args[0]);

                final StandardAnalyzer standardAnalyzer = new StandardAnalyzer(CharArraySet.EMPTY_SET);
                final IndexWriterConfig config = new IndexWriterConfig(standardAnalyzer)
                                .setRAMBufferSizeMB(1024)
                                .setOpenMode(OpenMode.CREATE);

                try (Directory dir = FSDirectory.open(outputPath);
                         IndexWriter writer = new IndexWriter(dir, config);
                         BufferedReader bufferedReader = new BufferedReader(new InputStreamReader(System.in))) {

                        final BlockingQueue<String[]> workQueue = new ArrayBlockingQueue<>(1000);
                        final AtomicBoolean done = new AtomicBoolean();

                        final Thread[] threads = new Thread[Runtime.getRuntime().availableProcessors()];
                        final AtomicInteger indexed = new AtomicInteger();
                        final long start = System.currentTimeMillis();

                        for (int i = 0; i < threads.length; ++i) {
                                threads[i] = new Thread(() -> {
                                        try {
                                                Document document = new Document();
                                                StoredField idField = new StoredField("id", "");
                                                TextField textField = new TextField("text", "", Field.Store.NO);
                                                document.add(idField);
                                                document.add(textField);

                                                long batchStartTime = start;

                                                while (true) {
                                                        String[] item = workQueue.poll(100, TimeUnit.MILLISECONDS);
                                                        if (item == null) {
                                                                if (done.get()) {
                                                                        break;
                                                                } else {
                                                                        continue;
                                                                }
                                                        }

                                                        String lineNo = item[0];
                                                        String text = item[1];
                                                        idField.setStringValue(lineNo);
                                                        textField.setStringValue(text);

                                                        try {
                                                                writer.addDocument(document);
                                                                int numIndexed = indexed.incrementAndGet();
                                                                if (numIndexed % 100_000 == 0) {
                                                                        long end = System.currentTimeMillis();
                                                                        long duration = end - batchStartTime;
                                                                        System.out.printf("%d documents processed in %dms%n", numIndexed, duration);
                                                                        batchStartTime = end;
                                                                }
                                                        } catch (IOException e) {
                                                                throw new UncheckedIOException(e);
                                                        }
                                                }
                                        } catch (InterruptedException e) {
                                                Thread.currentThread().interrupt();
                                        }
                                });
                        }

                        System.out.println("Start indexing...");
                        for (Thread thread : threads) {
                                thread.start();
                        }

                        String line;
                        int lineNumber = 0;
                        while ((line = bufferedReader.readLine()) != null) {
                                line = line.trim();
                                if (line.isEmpty()) continue;
                                lineNumber++;
                                JsonObject parsed_doc = Json.parse(line).asObject();
                                String text = parsed_doc.get("text").asString();
                                workQueue.put(new String[]{String.valueOf(lineNumber), text});
                        }

                        done.set(true);
                        for (Thread thread : threads) {
                                thread.join();
                        }

                        System.out.println("Merge segments...");
                        writer.forceMerge(1, true);

                } catch (IOException e) {
                        e.printStackTrace();
                }
        }
}
