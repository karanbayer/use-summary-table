// Post-extraction rate/count derivations enforced in code, because the model
// skips them when they live only in the prompt. Rules: knowledge/derivation-rules.md
// D5. Only fills NS/NA/blank cells; records the rule in row.__derived.
//
// Copied to server/lib/derive-rates.mjs and inlined in app/index.html;
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

export function deriveRateCounts(row) {
  if (!row.__derived || typeof row.__derived !== "object") row.__derived = {};
  const put = (col, value, rule) => {
    row[col] = value;
    row.__derived[col] = rule;
  };

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
