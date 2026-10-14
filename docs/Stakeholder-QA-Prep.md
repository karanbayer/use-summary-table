# Stakeholder Q&A prep — Use Summary Tables Extractor

For first-time **regulatory colleagues**. Use these as spoken answers in the demo/Q&A.
Be precise: do not oversell. Prefer “draft + human check” over “fully automated.”

---

## 0 · Architecture (spoken answers)

**Q: Is this one AI or many agents?**  
**Two AI agents**, plus an optional remediation stage:

1. **Extractor (Sonnet)** — drafts the 28-column rows from the label  
2. **QC agent (Sonnet, fresh conversation)** — independent audit; severity Clean → Critical  
3. **Remediation (Opus)** — only if QC is High/Critical; ≤2 cycles — a stage, not a third standing agent  

Then the **human** reviews source trail, edits, and exports. Humans are not counted as AI agents.  
(Same split as the Copilot path: `extraction-main-agent` → `QC-agent`.)

---

## 1 · What is this, really?

**Q: What does the tool do?**  
It reads a pesticide-label PDF and drafts a **28-column EPA Use Summary Table**. You review it on screen, correct cells if needed, and download Excel. It does **not** submit anything to EPA or write into other systems.

**Q: Is the AI making regulatory decisions?**  
No. The AI proposes structured rows. A human decides what is good enough to use. Export is a human action.

**Q: Can I put in one label or many?**  
Either. One label → all uses from that label. Ten labels → all uses from each.  
**Schema is fixed (28 columns). Row count is not fixed** — it follows the label.

**Q: What about “149 pages → 155 rows”?**  
That was one **golden-record benchmark** on **five labels** used to measure accuracy. It is an **example**, not a fixed output size.

---

## 2 · Accuracy & “can we trust AI?”

**Q: How accurate is it?**  
On the five golden-record labels, field-level accuracy was about **88%** vs expert tables (representative run also described as ~149 pages → ~155 rows).  
That is strong for a first draft — **not** “good enough to skip review.”

**Q: Why isn’t it 100%?**  
Labels are long, inconsistent, and full of footnotes, conditionals, and multi-line restrictions. Hard fields historically include things like drift/soil restrictions and some yearly-max derivations. The tool is designed so those weak spots are **visible**, not hidden.

**Q: Does the AI invent values?**  
By design, no. If the label is silent → **NS** (Not Specified). If the column does not apply → **NA**. Cells should not be blank. Some cells may be **◆ derived** by a documented convention rule (hover to see which rule) — still reviewable, not silent guessing.

**Q: What if the model is wrong on a rate or PHI?**  
That is exactly why every row can be expanded to **page + source text**, cells are editable, and Low-confidence / coverage warnings exist. Wrong cells get corrected before anyone relies on the Excel.

**Q: Does independent QC mean I don’t need to check?**  
No. Independent QC is a **second model pass** that flags High/Critical issues and can trigger bounded remediation. It reduces obvious mistakes; it does **not** replace the regulatory reader.

---

## 3 · Proofreading, provenance, traceability

**Q: How do I proofread?**  
1. Filter to **Low confidence** first.  
2. Open coverage warnings (crops detected but barely filled).  
3. Expand **▸** on a row → see **page** and **source wording**.  
4. Double-click any cell to correct it (edited cells are marked).  
5. Only then download Excel.

**Q: Where does each value come from?**  
Each row carries **source file**, **page**, and **evidence text**. That is the provenance trail for challenge and audit.

**Q: Can I see which values were derived vs copied?**  
Yes. Cells marked **◆** came from a documented derivation rule, not verbatim copy. Hover / docs explain the rule.

**Q: Is there an audit trail of AI calls?**  
Yes — **metadata only** (time, status, duration, estimated tokens/cost, QC severity). **Not** raw label text in the audit store.

---

## 4 · Human checks & “control stations”

**Q: Do humans still check every table?**  
Yes. The operating model is **AI draft → human spot-check → human export**. Training material states you do not export without review.

**Q: How often / how deep is the human check?**  
Practically: every export path assumes a reviewer. Depth is risk-based — start with Low confidence, High/Critical QC findings, and high-impact fields (rates, PHI, REI, restrictions). Spot-check is minutes, not 100+ hours of blank-sheet transcription — but it is still a real check against the label.

**Q: What are the “review stations”?**  
After extraction, **3 guided stations** run before the final table is released for export:

1. **Document snapshot** — file, pages, product, reg # / form sanity  
2. **Extraction sanity** — row/use counts, coverage warnings, sample source snippets  
3. **High-risk field check** — rates, timing, PHI/REI/MRI, geographic restrictions  

**Yes** advances; **No** pauses so you can edit, then resume. You also keep **▸** source trail, confidence filter, coverage warnings, QC notes, and cell edit.

**Q: Can the chat “fix” the table without me noticing?**  
No. Chat can **propose** an edit; you must click **Apply**. Nothing writes itself into the table.

---

## 5 · Cost & money

**Q: How much does a run cost?**  
Typical estimate: about **$0.50–$0.75 per label** for a normal (clean) AI path. Hard labels that escalate to Opus remediation cost more.

**Q: How do you stop runaway spend?**  
- **Daily app budget guard** (`DAILY_BUDGET_USD`, default **$100/day** on Agentrix) — refuses new AI work when the day cap is hit  

- **Rate limit** (default ~20 requests/minute)  
- **Kill switch** — stops AI paths quickly without redeploy  
- Remediation cycles are **bounded** (not infinite retries)  
- Deterministic (non-AI) mode uses **zero** model credits  

**Q: What about the AI Gateway “$2,000” budget?**  
**Do not quote $2k unless you have confirmed it in the Gateway portal.** Period (monthly vs annual) was **not verified** in project docs. Safe line: *“Spend goes through Bayer AI Gateway under the application identity; the app also enforces its own daily cost cap. I can pull the exact Gateway envelope from the portal if you want the figure.”*

**Q: Who pays?**  
Usage is attributed to the **application / team** via Entra → AI Gateway (Agentrix path), not a personal browser API key.

---

## 6 · Compliance & regulated use

**Q: Is this validated for GxP / can we submit the AI output as-is?**  
Treat output as a **draft aid for submission prep**. A human remains accountable for the table used in regulatory work. Do not describe it as “validated autonomous submission.”

**Q: Does it submit to EPA?**  
No. Explicitly out of scope.

**Q: What if the label is a scanned image?**  
OCR fallback exists (Tesseract, bundled). Quality can be lower on poor scans — review harder; or use a text-layer PDF when possible.

**Q: Training / who can operate it?**  
Operator training checklist exists (`TRAINING.md`): human-in-the-loop, NS vs NA, QC panels, Apply-only chat edits, escalate on systematic failure. Keep the sign-off table current for your pilot/production users.

---

## 7 · Cybersecurity & data exchange

**Q: Does label text leave Bayer?**  
AI calls go through **Bayer’s governed path** (Agentrix relay → **Entra M2M** → **Bayer AI Gateway** → approved Claude models). The **browser never holds the model credential**. Calls are same-origin to our API, not from the browser straight to a public Anthropic URL.

**Q: Is raw label text stored forever in an audit log?**  
Audit records are **metadata-only** — not raw label text. Job/input retention for background jobs is short-lived (order of days in the job store design).

**Q: Could a malicious label “prompt-inject” the model into exfiltrating data?**  
Mitigations stacked:

1. System prompt: treat label text as **data**, never instructions  
2. Content-safety flag for injection-like phrases (flags for review; does not silently trust)  
3. Browser **CSP** `connect-src 'self'` — page JS cannot call arbitrary external origins  
4. No model secrets in the browser  
5. Chat edits still need human **Apply**  
6. Human review before anything is used  

No stack is perfect; the honest line is **defense in depth + human remains the decision maker**.

**Q: Kill switch?**  
Yes — can disable AI extraction paths quickly if something looks wrong at scale.

**Q: Who has access?**  
Access is gated (pilot gate / platform auth on Agentrix). Broader rollout should use proper per-user Bayer IAM — do not claim enterprise SSO completeness if your audience knows the pilot history; say what is true for the **current Agentrix deployment** in your environment.

**Q: Any data sent to third-party CDNs?**  
Core path is designed to avoid random third-party script calls; libraries are vendored. AI goes only through Bayer Gateway.

---

## 8 · Multiple EPA schemas / generalising the output

**Q: EPA has more than one output schema. Can we add another?**  
**Yes.** Same label → same Agentrix / AI Gateway / 2-agent pattern. What changes is a **schema pack** (columns, fill rules, derivation, QC checks, golden examples) — not a new hosting stack.

**Q: Easy or hard?**  

| Change | Difficulty | Why |
|--------|------------|-----|
| Small variant of current UST (rename/reorder, add a few fields, same row meaning) | **Medium** | Schema + prompts + export + goldens |
| Different EPA table (different row grain, units, semantics) | **Hard** | New rules, QC, goldens, UI, SME time |
| “Any schema typed in” with no domain rules | **Very hard / not advisable** | Accuracy and QC collapse |

Rough effort: small variant **days–2 weeks**; second full schema **several weeks**; fully generic engine **months** (and still needs per-schema rules).

**Q: At what cost?**  
Mainly **people time** (regulatory SME + engineering + re-benchmark), not model $. Once a pack exists, run cost stays in the same ballpark (~$0.50–$0.75/label).

**Q: What would the architecture look like?**  
Today: one fixed 28-column `SCHEMA`.  
Target:

```text
Label PDF → choose Schema Pack → Extractor + QC using that pack
         → same review UI (source trail, edit) → Excel for that pack
```

Agentrix and AI Gateway **stay the same**. The variable layer is **knowledge + schema**, not infrastructure.

**Q: How easy is it to generalise to any output?**  
Easy-ish when outputs share the same idea (one row = use × site × method, NS/NA, page citation). Hard when templates mean different things. The bottleneck is **regulatory meaning + goldens**, not drawing columns on a slide.

**One-liner for the room:**  
> “We’re productionised for this EPA Use Summary schema. A second EPA schema is doable as a schema pack on the same pipeline — medium if it’s a cousin, harder if the row definition changes. Fully arbitrary schemas aren’t free.”

---

## 9 · Hard questions (critical observer)

**Q: If accuracy is 88%, aren’t we shipping a wrong table 12% of the time?**  
Field-level 88% means many cells match expert gold; it does **not** mean “12% of tables are useless.” Errors concentrate in harder fields. The workflow assumes **spot-check of risky cells**, not blind acceptance. Compare to 100+ hours of manual work, which also has human error — here the draft is faster and **traceable**.

**Q: Why should we use this if we still have to check?**  
Because checking a draft with page citations is much faster than building the table from a blank sheet. The value is **cycle time + consistency + provenance**, not removing humans.

**Q: What happens when a new label layout appears that the model has never seen?**  
That is why QC + human review exist. Systematic degradation should be escalated (drift check / owner). Knowledge/rules are updated from training logs when patterns of mistakes appear.

**Q: Can it silently fall back to a worse engine if AI fails?**  
Design intent: surface gateway/budget errors rather than silently substituting a different result. Deterministic mode is an **explicit** fallback the user can use, not a hidden swap.

**Q: Background jobs — if I close the tab, is my data safe?**  
Jobs run server-side; you reopen with the job link. Soft-async on Agentrix needs the service kept warm (**minScale = 1**). Pod restart can drop in-memory job state — be honest if asked about durability limits.

**Q: You already built an ARS agent from this — does that mean this is “done”?**  
It means the **pattern worked** (draft → human check → governed Gateway) and was reused. This tool still needs the same discipline every run.

**Q: What’s still imperfect? (say this before they find it)**  
- Hard restriction fields still need careful human eyes  
- 3-station review gate is enabled before final table release / export  

- Exact AI Gateway dollar envelope/period should be read from the portal, not guessed  
- Broader org rollout still benefits from clear operator training sign-off hygiene  

---

## 10 · One-liners for the demo

| Topic | Line |
|--------|------|
| Trust | “The model proposes; you decide; every cell can show its page and source.” |
| Accuracy | “~88% on our golden five labels — good draft, not a skip-review certificate.” |
| Cost | “About fifty to seventy-five cents per label on a normal run, with daily caps and a kill switch.” |
| Compliance | “No EPA submit, no silent writes — Excel only after a human is ready.” |
| Security | “Credentials stay server-side; calls go through Bayer AI Gateway; label text is data, not instructions.” |
| Genericity | “Schema fixed for this UST; rows and label count vary with what you upload.” |
| More EPA schemas | “Second schema = a schema pack on the same pipeline — doable, not a free toggle.” |

---

## 11 · If you don’t know

Safe phrases:

- “I don’t want to guess the Gateway budget period — I’ll confirm in the portal and follow up.”  
- “That’s a good candidate for the demo — let’s open a Low-confidence row and trace it live.”  
- “After extraction you’ll walk three short review stations — document snapshot, extraction sanity, then high-risk fields — before Excel export unlocks.”  
