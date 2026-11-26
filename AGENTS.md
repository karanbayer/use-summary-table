# AGENTS.md

Instructions for the GitHub Copilot coding agent working autonomously in this repository.

## 1 · Project Context

**Use Summary Tables Extractor** — a prototype web app that reads pesticide label PDFs and
extracts every crop and every use into a schema-compliant table, viewable on screen and
downloadable as `.xlsx` or `.csv`.

- **Frontend-only.** No backend, no database, no server process.
- **Requirements live in `specs/PRD.md`** (R1–R17). Every change must trace to a requirement.
- **Task checklist is `specs/Tasks.md`** — update it when work is finished (`[ ]` → `[x]`).
- **Demo walkthrough is `specs/Demo.md`** — keep it in step with the UI when you change it.
- The whole app is `app/index.html`. Sample labels and expected output live in `samples/`.

## 2 · Build and Test

**There is no build step.** Do not add one — no bundler, no transpiler, no package manager.

To verify a change:

1. Open `app/index.html` directly in a browser (`open app/index.html`).
2. Upload a PDF from `samples/` and click **Run Extraction**.
3. Confirm the core flow still works:
   - Results table renders, grouped by source file
   - Search, confidence filter, and column sorting respond
   - Row expansion (**▸**) shows page and source text
   - Double-click cell editing saves and marks the cell
   - Excel and CSV downloads produce valid files
   - Saved runs persist across a page reload; compare and merge work
4. Check the browser console for errors before opening a PR.

For anything beyond a trivial change, work through the relevant sections of
`tests/manual-checklist.md` and record the outcome in the PR description.

## 3 · Coding Standards

- **Vanilla JavaScript only.** No React, Vue, Angular, Svelte, jQuery, or build tooling.
- **Keep all code in `app/index.html`** — HTML, CSS, and JS stay in that one file.
- **`SCHEMA` is the single source of truth** for columns. Never hard-code column names elsewhere.
- Match the existing style: 2-space indent, `const`/`let`, template literals, and section
  banner comments tying code back to its task and requirement.
- Escape user/PDF-derived content with the existing `esc()` helper before inserting into HTML.
- Make small, self-contained changes — one task per PR.
- **Follow `.github/copilot-instructions.md`**; it takes precedence over this file.

## 4 · What NOT To Do

- ❌ Do not add backend services, APIs, or a database.
- ❌ Do not add authentication, login, or user accounts.
- ❌ Do not install packages or add a `package.json` / `node_modules`.
- ❌ Do not add secret keys, API keys, tokens, or passwords.
- ❌ Do not call external services at runtime. PDF.js and SheetJS via CDN are the only
  permitted remote libraries; Tesseract.js must stay bundled locally in `app/vendor/`.
- ❌ Do not implement features that aren't already in `specs/PRD.md` — open an issue proposing
  the requirement first.

## 5 · Pull Request Expectations

- State which requirement (R#) and task the change satisfies.
- Update `specs/Tasks.md`, and add a short note if the outcome differs from the "Done when" line.
- Note anything you could not verify — for example, behaviour needing a real label PDF that
  isn't committed to `samples/`.

## 6 · Deploying (the agent does this, not the owner)

When a change is ready, commit and push it yourself; the owner should not have to run git or deploy steps.
- `git pull` first (rebase is configured): after every deploy the workflow commits "Release x.y.z [skip ci]" to
  `main`, so a push without pulling is rejected.
- Push to `bayer-int` `main`, `personal` and `bayer` (mirrors). App changes deploy automatically to Agentrix **Development**; docs-only
  changes (`*.md`, `docs/`, `specs/`, `tests/`) do not deploy.
- Then watch the run (`gh run watch` on `bayer-int/use-summary-table`, workflow "Deploy to Agentrix"), `git pull` the release
  commit, and tell the owner the version it deployed.
- Never edit the version by hand, never add a `VERSION` file, never deploy with the Agentrix **Deploy** button: the
  workflow raises the one version (`scripts/bump_version.py`; Dockerfile, `agent-card.json`, `agenthub-agent.yaml`).
  To redeploy without a code change: `gh workflow run "Deploy to Agentrix" -R bayer-int/use-summary-table`.
- Production changes only by **Promote to QA → Promote to Prod** in Agentrix, which the owner clicks (until Agentrix
  promotes automatically). Tell the owner which version to promote and what changed for users.

## 7 · Planning with a second model (any tool)

Before building a change that is more than a typo or a copy fix:
1. Plan first, without changing files: what is asked and who is affected; how it works today (code, and the real data
 read-only); consequences and risks; 2–3 options with a recommendation.
2. Get an independent second plan from a **different model** than the one you run on (another model family if
 possible, for example Gemini if you are Claude, Claude or GPT if you are Gemini):
   - If your tool can start a sub-agent on another model (Cursor can), do it: read-only, with the request as it came
     and these rules, told not to change files, commit, push or call write APIs.
   - If it cannot (for example Copilot in VS Code, Claude Code), write out the planning prompt ready to paste and ask
     the owner to run it in a second chat with another model picked in the tool's model menu, then paste the answer back.
3. Show the owner both recommendations side by side and what one found that the other missed; the owner chooses.
 Then build, test and deploy as in §6.

If no second model is available, say so and go on with your own plan. Why: in a comparison on 26 Nov 2026 (two real
AgriGuide requests, three models) the second models found points the first plan missed, including a flaw in a change
already shipped.
