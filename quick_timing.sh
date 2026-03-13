#!/bin/bash
# Quick timing test for specific slow queries 
# Measures last-iteration time (warmed up) for each query
BIN=/Users/medcl/rust/search-benchmark-game/engines/pizza-engine-0.1/target/release/do_query
IDX=/Users/medcl/rust/search-benchmark-game/engines/pizza-engine-0.1/idx

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
    "tallest trees in the world"
    "texas state legislature"
    "+scottsdale +az"
    "+canon +powershot"
    "canon powershot"
)

echo "=== TOP_10 Quick Timing Test ==="
echo "Format: hits  time_us  query"
for q in "${QUERIES[@]}"; do
    # 10 iterations, take last (warmed)
    input=""
    for i in $(seq 1 10); do
        input+="TOP_10	${q}
"
    done
    result=$(printf "$input" | "$BIN" "$IDX" 2>/dev/null | tail -1)
    echo "  ${result}  \"${q}\""
done

echo ""
echo "=== TOP_100 Quick Timing Test ==="
for q in "${QUERIES[@]}"; do
    input=""
    for i in $(seq 1 10); do
        input+="TOP_100	${q}
"
    done
    result=$(printf "$input" | "$BIN" "$IDX" 2>/dev/null | tail -1)
    echo "  ${result}  \"${q}\""
done

echo ""
echo "=== COUNT Quick Timing Test ==="
for q in "${QUERIES[@]}"; do
    input=""
    for i in $(seq 1 10); do
        input+="COUNT	${q}
"
    done
    result=$(printf "$input" | "$BIN" "$IDX" 2>/dev/null | tail -1)
    echo "  ${result}  \"${q}\""
done
