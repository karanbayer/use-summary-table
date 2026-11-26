#!/usr/bin/env bash
# The Agentrix image ships server/ only, so it needs its own copy of the jobs
# pipeline. Generate it from the Cloudflare Worker's so the two never drift.
#   scripts/sync-server-pipeline.sh          regenerate server/lib/pipeline.mjs
#   scripts/sync-server-pipeline.sh --check  fail if the copy is out of date
set -euo pipefail
cd "$(dirname "$0")/.."

generate() {
  printf '%s\n' "// GENERATED from worker/src/pipeline.js by scripts/sync-server-pipeline.sh — do not edit."
  sed -e 's#from "\./knowledge\.js"#from "./knowledge.mjs"#' \
      -e 's#from "\./governance\.js"#from "./governance.mjs"#' \
      -e 's#from "\./entra\.js"#from "./entra.mjs"#' \
      -e 's#from "\./derive-rates\.js"#from "./derive-rates.mjs"#' \
      -e 's#from "\./openai-chat\.js"#from "./openai-chat.mjs"#' \
      worker/src/pipeline.js
}

if [[ "${1:-}" == "--check" ]]; then
  diff <(generate) server/lib/pipeline.mjs >/dev/null \
    || { echo "server/lib/pipeline.mjs is stale — run scripts/sync-server-pipeline.sh"; exit 1; }
  echo "server pipeline in sync"
else
  generate > server/lib/pipeline.mjs
  echo "wrote server/lib/pipeline.mjs"
fi
