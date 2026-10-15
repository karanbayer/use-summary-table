#!/usr/bin/env bash
# Fails if the three copies of the rate/count derivation rules drift apart.
set -euo pipefail
cd "$(dirname "$0")/.."

body() { sed -n '/^const COL = {/,$p' "$1" | sed 's/^export //'; }
browser() { sed -n '/^\/\/ BEGIN derive-rates/,/^\/\/ END derive-rates/p' app/index.html | sed '1d;$d'; }

diff <(body worker/src/derive-rates.js) <(body server/lib/derive-rates.mjs) >/dev/null \
  || { echo "server/lib/derive-rates.mjs differs from worker/src/derive-rates.js"; exit 1; }
diff <(body worker/src/derive-rates.js) <(browser) >/dev/null \
  || { echo "app/index.html derive-rates block differs from worker/src/derive-rates.js"; exit 1; }
echo "derive-rates copies in sync"
