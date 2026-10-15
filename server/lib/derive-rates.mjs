// Post-extraction rate/count derivations enforced in code, because the model
// skips them when they live only in the prompt. Rules: knowledge/derivation-rules.md
// D5. Only fills NS/NA/blank cells; records the rule in row.__derived.
//
// Copy of worker/src/derive-rates.js (the Docker image ships server/ only);
// scripts/check-derive-sync.sh fails if the copies drift.

const COL = {
  target: "App. Target",
  cc: "A.I. Max Total Rate/C.C. (lb a.i./A)",
  yr: "A.I. Max Total Rate/Yr. (lb a.i./A)",
  nCC: "Max # Apps/C.C.",
  nYr: "Max # Apps/Yr.",
  ccyr: "Max No. of CC/yr"
};
const EMPTY = new Set(["", "NS", "NA", "N/A", "na", "ns", "n/a"]);
const YEAR_CAP_RE = /per\s+(?:calendar\s+|crop\s+)?year|\/\s*year|per\s+12[- ]month/i;

const isEmpty = v => EMPTY.has(String(v ?? "").trim());

// D5.4 — single rate from the printed product rate. The model reads the product
// rate correctly but often converts it to lb a.i./A wrongly (wrong concentration,
// or the yearly cap taken as the rate). Only for single-active labels, so one
// concentration applies to every row.
const SINGLE = "A.I. Max Single Rate/App. (lb a.i./A)";
const PRODUCT_RATE_RE = /(\d+(?:\.\d+)?)(?:\s*(?:[-–]|to)\s*(\d+(?:\.\d+)?))?\s*(fl\.?\s*oz|fluid\s+ounces?|pints?|pt|quarts?|qt|gal(?:lons?)?)\.?\s*(?:product\s*)?(?:\/\s*A\b|per\s+acre)/gi;
const CAP_RE = /(?:do\s+not\s+apply\s+more\s+than|maximum[^.;]{0,30}?)\s*(\d+(?:\.\d+)?)\s*(fl\.?\s*oz|fluid\s+ounces?|pints?|pt|quarts?|qt|gal(?:lons?)?)/gi;
const CONC_RES = [
  /contains?\s+(\d+(?:\.\d+)?)\s*(?:lbs?|pounds?)\s+of\s+[A-Za-z][A-Za-z\s-]{0,40}?\s+per\s+(?:U\.?S\.?\s+)?gallon/i,
  /(\d+(?:\.\d+)?)\s*(?:lbs?|pounds?)\s*(?:of\s+)?(?:a\.?\s?i\.?|active\s+ingredient)[^.;\n]{0,20}?(?:per|\/)\s*gal/i
];

function flOzPerUnit(unit) {
  const u = unit.toLowerCase().replace(/\./g, "");
  if (/^(fl ?oz|fluid)/.test(u)) return 1;
  if (/^(pt|pint)/.test(u)) return 16;
  if (/^(qt|quart)/.test(u)) return 32;
  if (/^gal/.test(u)) return 128;
  return null;
}

/** lb a.i./gal when the label has exactly one active ingredient and states it; else null. */
export function singleActiveConcentration(labelText) {
  const text = String(labelText || "");
  const box = text.match(/ACTIVE\s+INGREDIENTS?(?:\s*\(S\))?\s*:([\s\S]{0,1500}?)OTHER\s+INGREDIENTS?/i);
  if (!box || (box[1].match(/\d+(?:\.\d+)?\s*%/g) || []).length !== 1) return null;
  for (const re of CONC_RES) {
    const m = text.match(re);
    const v = m ? parseFloat(m[1]) : NaN;
    if (isFinite(v) && v > 0) return v;
  }
  return null;
}

function deriveSingleRate(row, lbPerGal, put) {
  if (!lbPerGal) return;
  const current = String(row[SINGLE] ?? "").trim();
  if (current.includes(";")) return;
  const rates = [...String(row["App Rate (lb ai/A)"] ?? "").matchAll(PRODUCT_RATE_RE)]
    .map(m => parseFloat(m[2] || m[1]) * (flOzPerUnit(m[3]) || NaN))
    .filter(isFinite);
  if (!rates.length) return;
  const flOz = Math.max(...rates);
  const capText = `${row["Additional Information"] ?? ""} ${row["Additional Restrictions for Use/Use Site"] ?? ""}`;
  const caps = new Set([...capText.matchAll(CAP_RE)]
    .map(m => parseFloat(m[1]) * (flOzPerUnit(m[2]) || NaN))
    .filter(isFinite).map(v => v.toFixed(2)));
  if (caps.has(flOz.toFixed(2))) return;
  const lbAi = flOz * lbPerGal / 128;
  const stated = parseFloat((current.split("(")[0].match(/\d+(?:\.\d+)?/) || [])[0]);
  if (isEmpty(current) || !isFinite(stated) || Math.abs(stated - lbAi) / lbAi > 0.03) {
    put(SINGLE, String(Math.round(lbAi * 1000) / 1000), "D5.4-single-rate");
  }
}

export function deriveRateCounts(row, lbPerGal = null) {
  if (!row.__derived || typeof row.__derived !== "object") row.__derived = {};
  const put = (col, value, rule) => {
    row[col] = value;
    row.__derived[col] = rule;
  };

  deriveSingleRate(row, lbPerGal, put);

  // D5.2 — a seed treatment is one application on one crop cycle.
  if (/seed/i.test(String(row[COL.target] ?? ""))) {
    for (const col of [COL.nCC, COL.nYr, COL.ccyr]) {
      if (isEmpty(row[col])) put(col, "1", "D5.2-seed");
    }
  }

  // D5.1 — a per-year cap means one crop cycle per year (schema-reference Rule 5.1).
  const capText = `${row["Additional Information"] ?? ""} ${row["Additional Restrictions for Use/Use Site"] ?? ""}`;
  if (isEmpty(row[COL.ccyr]) && !isEmpty(row[COL.yr]) && YEAR_CAP_RE.test(capText)) {
    put(COL.ccyr, "1", "D5.1-year-cap");
  }

  // D5.3 — Rule 5.1 cascade: with one crop cycle a year, C.C. and Yr. columns are equal.
  if (String(row[COL.ccyr] ?? "").trim() === "1") {
    for (const [cc, yr] of [[COL.cc, COL.yr], [COL.nCC, COL.nYr]]) {
      if (isEmpty(row[cc]) && !isEmpty(row[yr])) put(cc, row[yr], "D5.3-cascade");
      else if (isEmpty(row[yr]) && !isEmpty(row[cc])) put(yr, row[cc], "D5.3-cascade");
    }
  }
  return row;
}
