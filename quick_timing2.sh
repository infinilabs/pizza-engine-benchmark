#!/bin/bash
# Quick timing test with warmup 
BIN=/Users/medcl/rust/search-benchmark-game/engines/pizza-engine-0.1/target/release/do_query
IDX=/Users/medcl/rust/search-benchmark-game/engines/pizza-engine-0.1/idx

# Build test input: 3 warmup, then 1 measured per query
QUERIES=(
    "helen of troy"
    "cured of cancer"  
    "the breakfast club"
    "the garden of eden"
    "lord of the rings"
    "the actors studio"
    "new york population"
    "the preakness"
    "to be or not to be"
    "city in iran"
    "tallest trees in the world"
    "the incredibles"
    "immigration to mexico"
    "becoming a widow"
    "time in denver"
    "the british embassy"
    "jesus as a child"
    "texas state legislature"
    "canon powershot"
    "+scottsdale +az"
    "+canon +powershot"
    "the"
    "new york"
)

input=""
# Global warmup: run all queries once to warm mmap
for q in "${QUERIES[@]}"; do
    input+="TOP_10	${q}
"
done
# Then run each 5 more times
for i in $(seq 1 5); do
    for q in "${QUERIES[@]}"; do
        input+="TOP_10	${q}
"
    done
done

echo "Running $(echo "$input" | wc -l) queries..."
printf "$input" | "$BIN" "$IDX" 2>&1 | grep "Processed\|SLOW"
