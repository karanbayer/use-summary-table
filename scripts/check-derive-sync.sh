#!/usr/bin/env bash
# Fails if the three copies of the rate/count derivation rules drift apart.
set -euo pipefail
cd "$(dirname "$0")/.."

body() { sed -n '/^const COL = {/,$p' "$1" | sed 's/^export //'; }
if ! diff <(body worker/src/derive-rates.js) <(body server/lib/derive-rates.mjs) >/dev/null; then
  echo "server/lib/derive-rates.mjs differs from worker/src/derive-rates.js"; exit 1
fi

# The browser copy uses DERIVE_ prefixed constants; compare the rule bodies only.
rules() { sed -n '/D5.2 — a seed treatment/,/^  return row;/p' "$1" | sed 's/DERIVE_YEAR_CAP_RE/YEAR_CAP_RE/'; }
if ! diff <(rules worker/src/derive-rates.js) <(sed -n '/BEGIN derive-rates/,/END derive-rates/p' app/index.html | rules /dev/stdin) >/dev/null; then
  echo "app/index.html derive-rates block differs from worker/src/derive-rates.js"; exit 1
fi
echo "derive-rates copies in sync"
