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

// D5.4 — single rate from the printed product rate. The model reads the product
// rate correctly but often converts it to lb a.i./A wrongly (wrong concentration,
// or the yearly cap taken as the rate). Only for single-active labels, so one
// concentration applies to every row.
const SINGLE = "A.I. Max Single Rate/App. (lb a.i./A)";
const RATE_COLS = ["App Rate (lb ai/A)", SINGLE, COL.cc, COL.yr];
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

function activeIngredientBox(labelText) {
  const m = String(labelText || "").match(/ACTIVE\s+INGREDIENTS?(?:\s*\(S\))?\s*:([\s\S]{0,1500}?)OTHER\s+INGREDIENTS?/i);
  return m ? m[1] : null;
}

/** The chosen active's name when the label lists 2+ actives and names it; else null. */
export function chosenActiveForMultiAi(labelText, selectedAi) {
  const box = activeIngredientBox(labelText);
  const name = String(selectedAi || "").trim();
  if (!box || !name || (box.match(/\d+(?:\.\d+)?\s*%/g) || []).length < 2) return null;
  const key = s => s.toLowerCase().replace(/[^a-z]/g, "");
  return key(box).includes(key(name)) ? name : null;
}

// D5.5 — option B safety net: if a rate cell still lists every active
// ("0.086 SPD; 0.18 FPF"), keep only the chosen one ("0.18 (flupyradifurone)").
// House abbreviations come from the expert tables (extraction-rules R-3).
const AI_ABBREV = {
  icafolinmethyl: ["icm"], indaziflam: ["idf"], flufenacet: ["flu"], spidoxamat: ["spd"],
  flupyradifurone: ["fpf", "fpd"], bromoxyniloctanoate: ["bxn", "brx"],
  bromoxynilheptanoate: ["bxn", "brx"], bromoxynil: ["bxn", "brx"]
};
function aiTokens(name) {
  const n = String(name || "").toLowerCase().replace(/[^a-z]/g, "");
  if (!n) return [];
  const cons = n.replace(/[aeiou]/g, "");
  return [...new Set([n, n.slice(0, 6), cons.slice(0, 3), n[0] + cons.slice(1, 3), ...(AI_ABBREV[n] || [])])]
    .filter(t => t.length >= 3);
}

export function narrowToActive(cell, activeName) {
  const s = String(cell ?? "");
  if (!s.includes(";") || !activeName) return null;
  const toks = aiTokens(activeName);
  const hits = s.split(";").map(p => p.trim()).filter(Boolean).filter(p => {
    const label = p.replace(/[\d.\s\-–()]+/g, " ").toLowerCase().replace(/[^a-z]/g, "");
    return toks.some(t => label.includes(t) || (label.length >= 3 && t.startsWith(label)));
  });
  if (hits.length !== 1) return null;
  const value = hits[0]
    .replace(/\(?[A-Za-z][A-Za-z\s-]*\)?\s*$/, "")
    .replace(/^\(?[A-Za-z][A-Za-z\s-]*\)?\s*/, "")
    .trim();
  return /\d/.test(value) ? `${value} (${activeName.toLowerCase()})` : null;
}

/** lb a.i./gal when the label has exactly one active ingredient and states it; else null. */
export function singleActiveConcentration(labelText) {
  const text = String(labelText || "");
  const box = activeIngredientBox(text);
  if (!box || (box.match(/\d+(?:\.\d+)?\s*%/g) || []).length !== 1) return null;
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

// D2.10 / D2.1 / D3.10 — method columns. Label-level facts are read once per file.
const FOLIAR_EQUIP_RE = /(?:applied|apply)\s+as\s+a\s+foliar\s+application\s+using\s+(?:properly\s+calibrated\s+)?(.{0,200}?equipment)/i;
const SUMMARY_EQUIP_RE = /^\s*(?:ground|aerial|air)\b[\s;,/&]*(?:and\s+|or\s+)?(?:ground|aerial|air)?\s*$/i;
const PLANTHOUSE_RE = /planthouse|tray|transplant|potting/i;

export function labelMethodFacts(labelText) {
  const text = String(labelText || "").replace(/\s+/g, " ");
  const head = text.slice(0, 4000);
  const foliar = text.match(FOLIAR_EQUIP_RE);
  const kind = /\bherbicide\b/i.test(head) ? "herbicide"
    : /\b(?:insecticide|miticide)\b/i.test(head) ? "insecticide" : null;
  return { foliarEquipment: foliar ? foliar[1].trim() : null, kind };
}

function deriveMethod(row, facts, put) {
  if (!facts) return;
  const target = String(row["App. Target"] ?? "");
  const foliar = /foliar/i.test(target);
  const planthouse = PLANTHOUSE_RE.test(`${row["Use Site"] ?? ""} ${target} ${row["App. Timing (Site Status)"] ?? ""}`);
  const equip = String(row["App. Equipment"] ?? "");

  if (foliar && !planthouse && facts.foliarEquipment && (isEmpty(equip) || SUMMARY_EQUIP_RE.test(equip))) {
    put("App. Equipment", facts.foliarEquipment, "D2.10-label-equipment");
  }
  if (foliar && isEmpty(row["App. Type"]) && /ground|aircraft|aerial|boom|sprayer/i.test(String(row["App. Equipment"] ?? ""))) {
    put("App. Type", "Broadcast", "D2.1-broadcast");
  }
  if (isEmpty(row["App. Timing (other)"])) {
    const value = /seed/i.test(target) ? "Treatment of seed"
      : facts.kind === "insecticide" ? "When pests occur"
      : facts.kind === "herbicide" ? "When weeds germinate" : null;
    if (value) put("App. Timing (other)", value, "D3.10-default");
  }
}

// A single plain number ("0.365", "0.365 (14 fl oz/A)"); null for ranges and per-active lists.
function plainNumber(v) {
  const s = String(v ?? "").split("(")[0];
  if (s.includes(";") || /\d\s*[-–]\s*\d/.test(s)) return null;
  const nums = s.match(/\d+(?:\.\d+)?/g);
  return nums && nums.length === 1 ? parseFloat(nums[0]) : null;
}

// D5.6 — when one application uses the whole crop-cycle cap, the cycle allows exactly one
// application, and the year allows one per crop cycle.
function deriveOneAppPerCycle(row, put) {
  const single = plainNumber(row[SINGLE]);
  const cap = plainNumber(row[COL.cc]);
  if (!single || !cap || Math.abs(single - cap) / cap > 0.03) return;
  if (isEmpty(row[COL.nCC])) put(COL.nCC, "1", "D5.6-one-app-per-cycle");
  const cycles = plainNumber(row[COL.ccyr]);
  if (cycles && Number.isInteger(cycles) && isEmpty(row[COL.nYr])) put(COL.nYr, String(cycles), "D5.6-one-app-per-cycle");
}

export function deriveRateCounts(row, lbPerGal = null, chosenActive = null, methodFacts = null) {
  if (!row.__derived || typeof row.__derived !== "object") row.__derived = {};
  const put = (col, value, rule) => {
    row[col] = value;
    row.__derived[col] = rule;
  };

  if (chosenActive) {
    for (const col of RATE_COLS) {
      const narrowed = narrowToActive(row[col], chosenActive);
      if (narrowed) put(col, narrowed, "D5.5-chosen-active");
    }
  }

  // Herbicide labels keep the stated range in Max Single Rate (R-18), so the
  // top-of-range conversion only applies to other product types.
  if (methodFacts?.kind !== "herbicide") deriveSingleRate(row, lbPerGal, put);
  deriveMethod(row, methodFacts, put);

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

  deriveOneAppPerCycle(row, put);
  return row;
}
