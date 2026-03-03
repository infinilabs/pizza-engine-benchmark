#!/bin/bash
cd /Users/medcl/rust/search-benchmark-game

echo "=== Testing Pizza ==="
for q in "+griffith +observatory" '"griffith observatory"' "griffith observatory" "the"; do
    result=$(echo -e "COUNT\t$q" | make -s -C engines/pizza-engine-0.1 serve 2>/dev/null)
    echo "  $q -> $result"
done

echo ""
echo "=== Reference: Lucene ==="
for q in "+griffith +observatory" '"griffith observatory"' "griffith observatory" "the"; do
    result=$(echo -e "COUNT\t$q" | make -s -C engines/lucene-9.9.2 serve 2>/dev/null)
    echo "  $q -> $result"
done
