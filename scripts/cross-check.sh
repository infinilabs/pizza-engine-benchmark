#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENGINES_CSV=""
LIMIT=""
INCLUDE_CSV=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --engines)
      ENGINES_CSV="${2:-}"
      shift 2
      ;;
    --limit)
      LIMIT="${2:-}"
      shift 2
      ;;
    --include)
      INCLUDE_CSV="${2:-}"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: $0 [--engines e1,e2,...] [--limit N] [--include TOP_10,TOP_100,COUNT]" >&2
      exit 2
      ;;
  esac
done

ENGINES_ENV="${ENGINES:-}"
if [[ -n "$ENGINES_CSV" ]]; then
  ENGINES_ENV="${ENGINES_CSV//,/ }"
fi
if [[ -z "$ENGINES_ENV" ]]; then
  ENGINES_ENV="lucene-9.9.2-bp tantivy-0.22 pizza-engine-0.1"
fi

COMMANDS_ENV="${COMMANDS:-}"
if [[ -n "$INCLUDE_CSV" ]]; then
  COMMANDS_ENV="${INCLUDE_CSV//,/ }"
fi
if [[ -z "$COMMANDS_ENV" ]]; then
  COMMANDS_ENV="COUNT TOP_10 TOP_100"
fi

QUERY_FILE="$ROOT_DIR/queries.txt"
if [[ -n "$LIMIT" ]]; then
  TMP_QUERY_FILE="$(mktemp)"
  head -n "$LIMIT" "$QUERY_FILE" > "$TMP_QUERY_FILE"
  QUERY_FILE="$TMP_QUERY_FILE"
  trap 'rm -f "$TMP_QUERY_FILE"' EXIT
fi

ENGINES="$ENGINES_ENV" COMMANDS="$COMMANDS_ENV" python3 src/cross_check.py "$QUERY_FILE"
