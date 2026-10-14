# Scale analysis (offline — no AI Gateway)

Corpus: **29 PDFs**, 770 pages, 10.57 MB.
PDF text extract (local): **19245 ms** total (p50 306 ms/file).

## Headline estimates

| Metric | Value |
|---|---|
| Est. Gateway calls | 341 |
| Est. cost (Sonnet mid) | $41.24 |
| Avg $/label | $1.42 |
| Labels/day @ $100 budget | ~70 |
| Wall clock @ concurrency=1 (current Worker) | 6.12 h |
| Wall clock @ concurrency=2 | 3.06 h |
| Wall clock @ concurrency=3 | 2.04 h |
| Two-pass (master) files | 15 |
| Single-chunk files | 14 |
| OCR-risk files | 0 |

## Wave sizing

| N labels | Est. $ | Calls | Hours c=1 | Hours c=2 | Fits $100? |
|---|---|---|---|---|---|
| 5 | $1.75 | 15 | 0.29 | 0.15 | yes |
| 10 | $9.44 | 80 | 1.46 | 0.73 | yes |
| 15 | $19.58 | 164 | 2.96 | 1.48 | yes |
| 20 | $29.24 | 243 | 4.36 | 2.18 | yes |
| 29 | $41.24 | 341 | 6.12 | 3.06 | yes |

## Recommended scaling parameters

- **worker max_concurrency**: `1` → **`2`** — c=1 is safest for Gateway stability; c=2 halves wall time if Gateway holds. Do not jump to 5 until a 5-label pilot succeeds at c=2.
- **batch wave size**: `all-at-once` → **`10`** — Avg ~$1.42/label → ~70 labels/day under $100. Wave so a failure doesn't burn the whole day.
- **DETAIL_SKELETON_BATCH**: `6` → **`6`** — Keep 6 — larger batches risk max_tokens truncation; smaller increases Pass-2 call count linearly.
- **EXTRACT_CHUNK_CHARS_LARGE**: `35000` → **`35000`** — 35k is the stability tradeoff already chosen for master labels; raising it increases Pass-1 failure rate more than it saves calls.
- **submit strategy**: `mixed sizes together` → **`small→medium→large waves`** — Small labels finish fast and validate the pipe; park 40p+ masters in a separate overnight wave.
- **DAILY_BUDGET_USD**: `100.0` → **`100.0`** — Full 29-label pack estimates $41.24; need headroom for QC retries/remediation.

## Tiers

- Small (<20p): 20
- Medium (20–39p): 5
- Large (40p+): 4

## Top 10 cost drivers

| File | Pages | Mode | Chunks (active/barren) | Est. calls | Est. $ | Est. min |
|---|---|---|---|---|---|---|
| 000524-00539-20231106 (3).pdf | 178 | two_pass | 19/9 | 52 | $6.29 | 55 |
| 000524-00659-20241213 (6).pdf | 171 | two_pass | 18/7 | 49 | $5.93 | 52 |
| 264-REUN_SIVANTO 300 SL_12_21_2023_BASE.pdf | 46 | two_pass | 12/2 | 33 | $4.01 | 35 |
| 264-1106_Indaziflam 200 SC Herbicide_5_19_2025_BASE.pdf | 31 | two_pass | 11/12 | 31 | $3.87 | 33 |
| 264-1105_Indaziflam 500SC Herbicide_6_2_2025_BASE.pdf | 27 | two_pass | 9/10 | 25 | $3.08 | 26 |
| 264-1141_SIVANTO® 200 SL_9_24_2020_BASE.pdf | 36 | two_pass | 8/1 | 23 | $2.81 | 24 |
| 264-1198_SIVANTO® 400 SL_9_5_2019_BASE.pdf | 40 | two_pass | 6/0 | 17 | $2.08 | 18 |
| 264-REGG_PLENEXOS SMART_02_20_2026_BASE.pdf | 16 | two_pass | 5/2 | 15 | $1.84 | 16 |
| 264-1203_Alion® Complete_3_15_2025_BASE.pdf | 22 | two_pass | 5/2 | 15 | $1.83 | 16 |
| 264-XXXX_USH679SC200_06_11_2025_BASE.pdf | 21 | two_pass | 4/4 | 12 | $1.47 | 13 |

## Practical run plan (fastest path to real numbers)

1. Wave A (validate): 5 smallest labels, Worker c=1 — confirm queue + QC.
2. Wave B (scale): next 10 medium — measure real $/label and min/label.
3. Wave C (stress): large/master labels overnight, still c=1 unless Wave B was clean at c=2.
4. Recalibrate this model from Wave A/B actuals (replace SEC_* and row heuristics).

Full JSON: `samples/scale/_report/scale-report.json`

