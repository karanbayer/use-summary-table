// Knowledge blobs for the server-side job pipeline (same compiled JSON the
// Cloudflare Worker uses). Read via fs so Node needs no JSON import assertions.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const compiledPath = path.resolve(
  __dirname,
  "../../knowledge/compiled/knowledge-compiled.json"
);

if (!fs.existsSync(compiledPath)) {
  throw new Error(
    `knowledge-compiled.json missing at ${compiledPath} — copy knowledge/compiled into the image`
  );
}

const compiled = JSON.parse(fs.readFileSync(compiledPath, "utf8"));

export const EXTRACTION_RULES_MD = compiled.EXTRACTION_RULES_MD;
export const DERIVATION_RULES_MD = compiled.DERIVATION_RULES_MD;
export const SCHEMA_REFERENCE_MD = compiled.SCHEMA_REFERENCE_MD;
export const UNIT_CONVERSIONS_MD = compiled.UNIT_CONVERSIONS_MD;
export const GOLDEN_EXAMPLE_V2_TXT = compiled.GOLDEN_EXAMPLE_V2_TXT;
