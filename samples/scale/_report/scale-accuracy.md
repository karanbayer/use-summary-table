# Scale + accuracy report

Generated: 2026-10-14T16:47:54Z

**Verdict:** FAILED — no successful extracts. See error_classes. Retry after fixing root cause.

## Jobs

- Wave A: `done_with_errors` — https://use-summary-table.pages.dev/?job=24a4f61f-f3d3-456d-89b6-6c3bdca03a44
- Wave B: `done_with_errors` — https://use-summary-table.pages.dev/?job=59b38ca9-adbb-4cc4-8781-d30b29c3a214
- Wave C: `processing` — https://use-summary-table.pages.dev/?job=b0678198-398e-49e4-9e9a-efceed7c0155

## Reliability summary

| Metric | Value |
|---|---|
| Files | 29 |
| Done | 0 |
| Error | 27 |
| Processing / queued | 1 / 1 |
| Success rate | 0.0 |

### Error classes

- `gateway_auth_403`: 13
- `empty_extract`: 13
- `none`: 2
- `kv_input_missing`: 1

## Accuracy method (works on labels you have never seen)

1. **Reliability** — did the file finish (`done`) with rows?
2. **QC status** — Clean / High / Unavailable (Unavailable ≠ regulatory-final).
3. **Rate-gap proxy** — Evidence mentions fl oz/qt/AE but `App Rate (lb ai/A)` is NS (under-extraction, not hallucination). No golden required.
4. **Golden accuracy** — only for files with `samples/expected/*` (e.g. Sivanto 400 SL).

Unknown future labels: do **not** special-case product names. Detect unit/rate mismatches mechanically, convert when concentration is on the label, and let QC raise `RATE-UNIT-GAP` when NS remains beside product units.

## How metrics change with scale

### By page bin

| Pages | N | Success | Avg rows (done) | Avg rate-gap | Avg NS-rate share |
|---|---|---|---|---|---|
| 01-09p | 10 | 0.0 | None | None | None |
| 10-19p | 10 | 0.0 | None | None | None |
| 100p+ | 2 | 0.0 | None | None | None |
| 20-39p | 5 | 0.0 | None | None | None |
| 40-99p | 2 | 0.0 | None | None | None |

### By tier

| Tier | N | Success | Error classes |
|---|---|---|---|
| large | 7 | 0.0 | `{'empty_extract': 7}` |
| mega | 2 | 0.0 | `{'none': 2}` |
| small | 20 | 0.0 | `{'gateway_auth_403': 13, 'empty_extract': 6, 'kv_input_missing': 1}` |

### By wave

| Wave | N | Success | Done rows avg |
|---|---|---|---|
| A | 5 | 0.0 | None |
| B | 10 | 0.0 | None |
| C | 14 | 0.0 | None |

## Parameters that influence accuracy / reliability

| Parameter | Effect |
|---|---|
| **Pages / mega tier** | More chunks → more Gateway calls → more stream/auth exposure; higher rate-gap risk if front-matter concentration is missed |
| **Gateway auth health** | 403 Bedrock/credentials → success_rate collapses (this run) |
| **Queue concurrency** | c=1 slower but more stable; c>1 can amplify 403/429 |
| **Wave position / time** | Later files may hit budget/rate-limit or expired KV input |
| **QC path** | Unavailable means rows exist but not regulatory-final |
| **Unit conversion coverage** | Labels stating fl oz + lb/gal must convert; AE pounds on label must be preferred over NS |

## Per-file detail

| Wave | Tier | Pages | Status | Rows | QC | Rate-gap | Error class | File |
|---|---|---|---|---|---|---|---|---|
| A | small | 4 | error | 0 | None | None | gateway_auth_403 | 264-1129_INDAZIFLAM TECHNICAL_8_2_2023_BASE.pdf |
| A | small | 5 | error | 0 | None | None | gateway_auth_403 | 000387_ML_01.01_base.pdf |
| A | small | 5 | error | 0 | None | None | gateway_auth_403 | 000380_ML_02.03_base.pdf |
| A | small | 5 | error | 0 | None | None | gateway_auth_403 | 264-PA31_Icafolin-methyl_06_09_2025_BASE.pdf |
| A | small | 6 | error | 0 | None | None | gateway_auth_403 | 000383_ML_02.03_base.pdf |
| B | small | 7 | error | 0 | None | None | gateway_auth_403 | 000385_ML_02.04_base.pdf |
| B | small | 7 | error | 0 | None | None | gateway_auth_403 | 001100_ML_03.01_base.pdf |
| B | small | 8 | error | 0 | None | None | gateway_auth_403 | 000397_ML_03.03_base.pdf |
| B | small | 8 | error | 0 | None | None | kv_input_missing | 000719_ML_03.02_base.pdf |
| B | small | 8 | error | 0 | None | None | gateway_auth_403 | 000386_ML_02.05_base.pdf |
| B | small | 10 | error | 0 | None | None | gateway_auth_403 | 000382_ML_01.01_base.pdf |
| B | small | 10 | error | 0 | None | None | gateway_auth_403 | 000384_ML_04.03_base.pdf |
| B | small | 11 | error | 0 | None | None | gateway_auth_403 | 001086_ML_02.01_base.pdf |
| B | small | 11 | error | 0 | None | None | gateway_auth_403 | 264-1142_BYI 02960 480 FS_10_21_2025_BASE.pdf |
| B | small | 12 | error | 0 | None | None | empty_extract | 000381_ML_06.01_base.pdf |
| C | small | 15 | error | 0 | None | None | empty_extract | 264-XXXX_USH679EC412_06_11_2025_BASE.pdf |
| C | small | 16 | error | 0 | None | None | empty_extract | 264-REGG_PLENEXOS SMART_02_20_2026_BASE.pdf |
| C | small | 16 | error | 0 | None | None | empty_extract | 264-XXXX_USH679SC470_06_11_2025_BASE.pdf |
| C | small | 16 | error | 0 | None | None | empty_extract | 264-XXXX_USH679EC427_06_11_2025_BASE.pdf |
| C | small | 18 | error | 0 | None | None | empty_extract | 264-XXXX_USH679SC450_06_11_2025_BASE.pdf |
| C | large | 21 | error | 0 | None | None | empty_extract | 264-XXXX_USH679SC200_06_11_2025_BASE.pdf |
| C | large | 22 | error | 0 | None | None | empty_extract | 264-1203_Alion® Complete_3_15_2025_BASE.pdf |
| C | large | 27 | error | 0 | None | None | empty_extract | 264-1105_Indaziflam 500SC Herbicide_6_2_2025_BASE.pdf |
| C | large | 31 | error | 0 | None | None | empty_extract | 264-1106_Indaziflam 200 SC Herbicide_5_19_2025_BASE.pdf |
| C | large | 36 | error | 0 | None | None | empty_extract | 264-1141_SIVANTO® 200 SL_9_24_2020_BASE.pdf |
| C | large | 40 | error | 0 | None | None | empty_extract | 264-1198_SIVANTO® 400 SL_9_5_2019_BASE.pdf |
| C | large | 46 | error | 0 | None | None | empty_extract | 264-REUN_SIVANTO 300 SL_12_21_2023_BASE.pdf |
| C | mega | 171 | processing | 0 | None | None | none | 000524-00659-20241213 (6).pdf |
| C | mega | 178 | queued | 0 | None | None | none | 000524-00539-20231106 (3).pdf |

## Next steps

1. Fix Worker → AI Gateway Bedrock credentials (403) — without this, scale accuracy is undefined.
2. Re-queue: `python3 scripts/scale_run_live.py --mode submit-all`
3. Re-run this report: `python3 scripts/scale_accuracy_report.py`
4. Add goldens for 3–5 calibration labels to convert proxy → true accuracy.

JSON: `samples/scale/_report/scale-accuracy.json`

