# Stakeholder Demo Script

## Use Summary Tables Extractor

**Duration:** 7–10 minutes  
**Goal:** Show the user journey, extraction quality controls, and the path to governed Bayer deployment.

## Before the Demo

- Open the current deployed app or `app/index.html`.
- Keep one text-based sample label ready, preferably SIVANTO 400 SL or another known sample.
- Keep a second label ready only if the first run completes quickly.
- Do not demo with a personal credential visible.
- Have the stakeholder brief available: [STAKEHOLDER-BRIEF.md](STAKEHOLDER-BRIEF.md).

## Opening: 30 Seconds

Say:

> This tool converts a pesticide-label PDF into a structured Use Summary Table. It is not an autonomous EPA submission system. The model proposes structured rows, the application checks them, and a human reviews the evidence before export.

## Demo Flow

### 1. Upload: 45 seconds

1. Open the application.
2. Upload the sample pesticide label.
3. Point out the file list and the Run Extraction control.

Say:

> The document stays in the application flow as a source document. We preserve page boundaries so every result can be traced back to the label.

### 2. Extract: 60–90 seconds

1. Start extraction.
2. Show the page progress and run log.
3. If AI mode is enabled, point out the extraction and QC stages.
4. Explain that deterministic mode is available when model access is unavailable.

Say:

> The system has two paths. The deterministic path is fast and does not consume model credits. The AI path reads the full label with the extraction rules, emits structured rows, and then runs an independent QC review.

### 3. Results: 90 seconds

Show:

- row count;
- source-file grouping;
- confidence badges;
- `NS` and `NA` conventions;
- application method separation;
- rate, PHI, REI, and restriction columns.

Say:

> One row represents a use, use site, and application method. A foliar and soil use are separate rows because their rates, timing, restrictions, or PHI can differ.

### 4. Traceability: 60 seconds

1. Expand a row.
2. Show page number and source evidence.
3. Show a low-confidence row or coverage warning.

Say:

> The system does not ask the reviewer to trust a blank or unexplained value. It shows where the row came from and highlights places that need attention.

### 5. Human review: 60 seconds

1. Search for a crop.
2. Filter to low confidence if available.
3. Sort by a column.
4. Double-click one safe demonstration cell and edit it.
5. Show the edited marker.
6. Complete or describe the review stations.

Say:

> The human remains the decision-maker. An edit is explicit, visible, and retained in the export. The tool does not submit the table to EPA or write to another system.

### 6. Export: 45 seconds

1. Click Excel export.
2. Open the workbook.
3. Show the combined sheet and label-specific sheet.
4. Point out wrapped text, filters, confidence/provenance fields, and derived-field marking.

Say:

> The deliverable is a reviewable workbook rather than an opaque model response.

### 7. Architecture and governance: 90 seconds

Show this flow verbally or on a whiteboard:

```text
PDF
 -> page-preserving text extraction / OCR
 -> structured extraction
 -> independent QC
 -> bounded remediation for serious defects
 -> runtime validation
 -> human review
 -> Excel export
```

Then explain the target hosting path:

```text
Bayer IAM/MFA user
 -> Agentrix/AWS-hosted application
 -> Bayer AI Gateway
 -> approved Claude model
```

Say:

> The current pilot uses a server-side mGA relay. The target deployment moves hosting to Agentrix/AWS and model access to Bayer AI Gateway through the Entra application identity. The personal model credential will not be part of the target runtime, and telemetry will record metadata such as latency, model, and token counts without recording label text or prompts.

## Key Questions to Invite

- Which label types matter most for the first QA cohort?
- What accuracy threshold is acceptable for review-assisted use?
- Which fields require mandatory second-person review?
- What should the team budget and daily usage cap be?
- Is synchronous processing sufficient for the first Agentrix release?
- Which platform controls can Agentrix/AWS inherit and evidence for the security assessment?

## Honest Caveats

State these plainly if asked:

- The output is decision support and requires human review.
- OCR requires the local Tesseract asset for scanned labels.
- Very large labels currently use a full-document model call rather than document chunking.
- The current Cloudflare pilot uses mGA and is not the final Agentrix/AI Gateway runtime.
- The Agentrix/AWS migration still requires the approved container, gateway, OAuth, tracing, and storage contracts.

## If the Demo Goes Wrong

### AI budget or gateway error

Switch to deterministic mode and say:

> The governed model path is unavailable in this environment, so I am showing the deterministic fallback. The production target will use the approved AI Gateway application identity and team budget.

### No rows appear

Use the prepared text-based sample and explain that the original label may require OCR or a parser-specific regression fix.

### Slow remediation

Explain:

> Remediation is intentionally bounded. A difficult document may require an additional correction and QC pass, but the application will not retry indefinitely.

### Export issue

Show the on-screen results and source evidence, then state that export is a separate finalization step and can be repeated after review.

## Closing: 30 Seconds

Say:

> The value is not just calling an LLM. The product combines extraction, provenance, independent QC, bounded correction, cost controls, and human approval into a workflow that a regulatory analyst can inspect. The next release step is to run the same workflow on Agentrix/AWS with Bayer AI Gateway and an application-owned budget.
