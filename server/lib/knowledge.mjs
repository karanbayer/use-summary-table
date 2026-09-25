// Knowledge blobs for the server-side job pipeline.
// File lives next to this module (server/lib/knowledge-compiled.json) so the
// Docker image always includes it — root .dockerignore excludes knowledge/.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const candidates = [
  path.join(__dirname, "knowledge-compiled.json"),
  path.resolve(__dirname, "../../knowledge/compiled/knowledge-compiled.json")
];

function loadCompiled() {
  for (const compiledPath of candidates) {
    if (fs.existsSync(compiledPath)) {
      return JSON.parse(fs.readFileSync(compiledPath, "utf8"));
    }
  }
  throw new Error(
    "knowledge-compiled.json missing — expected at server/lib/knowledge-compiled.json in the image"
  );
}

const compiled = loadCompiled();

export const EXTRACTION_RULES_MD = compiled.EXTRACTION_RULES_MD;
export const DERIVATION_RULES_MD = compiled.DERIVATION_RULES_MD;
export const SCHEMA_REFERENCE_MD = compiled.SCHEMA_REFERENCE_MD;
export const UNIT_CONVERSIONS_MD = compiled.UNIT_CONVERSIONS_MD;
export const GOLDEN_EXAMPLE_V2_TXT = compiled.GOLDEN_EXAMPLE_V2_TXT;
