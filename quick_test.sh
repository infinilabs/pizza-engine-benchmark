#!/bin/bash
# Quick benchmark of specific queries
cd /Users/medcl/rust/search-benchmark-game/engines/pizza-engine-0.1

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
)

echo "=== TOP_10 Quick Test ==="
for q in "${QUERIES[@]}"; do
    # Run 3 warmup + 10 measured iterations
    result=$(printf "TOP_10\t${q}\nTOP_10\t${q}\nTOP_10\t${q}\nTOP_10\t${q}\nTOP_10\t${q}\nTOP_10\t${q}\nTOP_10\t${q}\nTOP_10\t${q}\nTOP_10\t${q}\nTOP_10\t${q}\n" | ./target/release/do_query idx 2>/dev/null | tail -1)
    echo "  ${result}  \"${q}\""
done
