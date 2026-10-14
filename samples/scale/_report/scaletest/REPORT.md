# Scale test report

## Batch size29 — 29 labels

- settled 26/29, done 25, error 1, budget-blocked 0
- wall clock to last settled file: 1.83 h

| Tier | Files | Done | Error | Avg rows | Avg min/label | QC High/Critical |
|---|---|---|---|---|---|---|
| small <20p | 20 | 19 | 1 | 3.8 | 3.4 | 1 |
| medium 20-39p | 5 | 5 | 0 | 24.4 | 12.0 | 4 |
| large 40-99p | 2 | 1 | 0 | 44.0 | 10.7 | 1 |
| mega 100p+ | 2 | 0 | 0 | - | - | 0 |

| # | Pages | Status | Rows | QC | Min | Label / error |
|---|---|---|---|---|---|---|
| 0 | 4 | done | 0 | Clean | - | 264-1129_INDAZIFLAM TECHNICAL_8_2_2023_BASE.pdf (no uses) |
| 1 | 5 | done | 2 | Medium | - | 000380_ML_02.03_base.pdf |
| 2 | 5 | done | 1 | Low | - | 000387_ML_01.01_base.pdf |
| 3 | 5 | done | 0 | Clean | - | 264-PA31_Icafolin-methyl_06_09_2025_BASE.pdf (no uses) |
| 4 | 6 | done | 1 | Medium | 2.1 | 000383_ML_02.03_base.pdf |
| 5 | 7 | done | 2 | Medium | 2.1 | 000385_ML_02.04_base.pdf |
| 6 | 7 | done | 1 | Low | - | 001100_ML_03.01_base.pdf |
| 7 | 8 | done | 9 | Medium | 4.2 | 000386_ML_02.05_base.pdf |
| 8 | 8 | done | 6 | Medium | 2.1 | 000397_ML_03.03_base.pdf |
| 9 | 8 | done | 1 | Low | 2.1 | 000719_ML_03.02_base.pdf |
| 10 | 10 | done | 11 | Medium | 4.3 | 000382_ML_01.01_base.pdf |
| 11 | 10 | done | 7 | Medium | 2.1 | 000384_ML_04.03_base.pdf |
| 12 | 11 | done | 2 | Medium | 2.1 | 001086_ML_02.01_base.pdf |
| 13 | 11 | done | 2 | Medium | - | 264-1142_BYI 02960 480 FS_10_21_2025_BASE.pdf |
| 14 | 12 | done | 14 | Medium | 6.4 | 000381_ML_06.01_base.pdf |
| 15 | 15 | done | 1 | Medium | 2.1 | 264-XXXX_USH679EC412_06_11_2025_BASE.pdf |
| 16 | 16 | done | 5 | Medium | 2.1 | 264-REGG_PLENEXOS SMART_02_20_2026_BASE.pdf |
| 17 | 16 | error | 0 | - | - | 264-XXXX_USH679EC427_06_11_2025_BASE.pdf — Two-pass extraction produced no rows across all chunks (7 chunk(s); 7 skipped/failed) |
| 18 | 16 | done | 2 | Low | 4.3 | 264-XXXX_USH679SC470_06_11_2025_BASE.pdf |
| 19 | 18 | done | 6 | High | 8.5 | 264-XXXX_USH679SC450_06_11_2025_BASE.pdf |
| 20 | 21 | done | 6 | Medium | 4.3 | 264-XXXX_USH679SC200_06_11_2025_BASE.pdf |
| 21 | 22 | done | 11 | High | 6.4 | 264-1203_Alion® Complete_3_15_2025_BASE.pdf |
| 22 | 27 | done | 17 | Critical | 8.5 | 264-1105_Indaziflam 500SC Herbicide_6_2_2025_BASE.pdf |
| 23 | 31 | done | 36 | Critical | 10.7 | 264-1106_Indaziflam 200 SC Herbicide_5_19_2025_BASE.pdf |
| 24 | 36 | done | 52 | Critical | 29.9 | 264-1141_SIVANTO® 200 SL_9_24_2020_BASE.pdf |
| 25 | 40 | done | 44 | Critical | 10.7 | 264-1198_SIVANTO® 400 SL_9_5_2019_BASE.pdf |
| 26 | 46 | processing | 0 | - | - | 264-REUN_SIVANTO 300 SL_12_21_2023_BASE.pdf |
| 27 | 171 | processing | 0 | - | - | 000524-00659-20241213 (6).pdf |
| 28 | 178 | processing | 0 | - | - | 000524-00539-20231106 (3).pdf |

## Accuracy vs ground truth (benchmark/score.py, per-label GT subset)

| Label | Pages | Row recall | Field precision | QC |
|---|---|---|---|---|
| BYI 02960 480 FS | 11 | 2/2 (100%) | 74% | Medium |
| Plenexos Smart | 16 | 5/5 (100%) | 63% | Medium |
| Indaziflam 200 SC | 31 | 19/22 (86%) | 67% | Critical |
| Sivanto 200 SL | 36 | 48/48 (100%) | 64% | Critical |
| Sivanto 400 SL | 40 | 44/44 (100%) | 70% | Critical |
| Sivanto 300 SL | 46 | not finished (stalled) | | |

## Finding: labels needing >~30 min never finish on the queue Worker

Sivanto 300 SL (46p), 000524-00659 (171p) and 000524-00539 (178p) stayed at
"processing". The 178p label's chunk counter went 21/131 -> 12/131, i.e. the
invocation was killed and the message redelivered from the start. A killed
run never reaches writeFileResult, so the file never shows an error.
