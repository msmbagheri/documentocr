# PROJECT_STATE — documentocr (durable project state)

> Update this file at the closeout of every substantial task. Keep it concise —
> history lives in `docs/reports/`, decisions in `docs/DECISIONS.md`.
> The drift audit (`tools/drift_audit.py`) parses `Last updated` and
> `Verified against commit`.

Last updated: 2026-11-21
Verified against commit: 250074b

## Objective

Local, evidence-driven Persian document OCR: (a) synthesize Konkoor-style exam
pages with ground truth (`konkoor_synth`, root scripts) and (b) extract structured
content from real Persian documents (insurance/forms) with Surya 2.5, delivered
through a web UI (BoundingBoxViewer, table→fields→key/value hierarchy, saved
results). Fully local processing — personal documents never leave the machine.

## Project profile

- Type: software engineering + AI/agentic pipeline + applied research (hybrid).
- Maturity: working prototype, active feature development.
- Data sensitivity: HIGH — real personal insurance/ID documents in test data and saved results.
- External dependencies: llama.cpp docker image (ghcr.io), HuggingFace datasets cache, optional free LLM tier (`?refine=1`) — all optional to core function.
- Consequences of incorrect output: wrong extracted values presented as truth → mitigated by honest `bbox_status`/confidence and numeric-preservation guards (D-005, D-006).

## Current status / phase

Web UI + post-processing feature set complete through cross-block key/value
pairing (commit `250074b`, 2026-11-16). Engine and UI were DOWN at the 2026-11-21
protocol audit. Reliability & anti-drift protocol installed 2026-11-21.

## Completed deliverables

Per `docs/reports/` (reported status; not re-verified unless noted):

| Deliverable | Evidence |
|---|---|
| DocumentOCR WebUI (upload, OCR, JSON/text panels) | `2026-11-14_DocumentOCR_WebUI.md`, `2026-11-14_webui/` |
| BoundingBoxViewer (SVG overlay, selection sync) | `2026-11-14_BBoxViewer.md`, `2026-11-14_bbox_viewer/` |
| Saved results (save/restore, persistence) | `2026-11-15_SavedResults.md` |
| Table→Fields→Key/Value hierarchy + hidden-field UI policy | `2026-11-15_TableFields.md` |
| Preprocessing v2.2 + docprep geometry (opt-in, default OFF) | TableFields report §0.5, §0.10 |
| LLM text refine `?refine=1` with numeric-safety guards | TableFields report §0.8, commit `fa59c14` |
| Save-time + inline rename | TableFields report §0.9, commit `418732a` |
| Cross-block KV pairing in text blocks | commits `53a6760`, `250074b`; report §0.13 (unit 6/6 PASS per report) |
| Reliability protocol (AGENTS.md, state, decisions, skill, audit tools, permissions) | `2026-11-21_ReliabilityProtocol.md` (this session, VERIFIED) |

## Incomplete / open

- No open feature task recorded in reports as of 2026-11-16.
- Deferred options (documented, not scheduled): RapidUnDistort (UVDoc) for phone-photo warping; CI/hooks for the drift audit; `webui/tests/data/ocr-data/` is gitignored (test docs are session-local).

## Accepted decisions

See `docs/DECISIONS.md` (D-001 … D-011). Highlights: local-only OCR (D-001),
never binarize/contrast for Surya (D-002), post-processing only (D-003),
JSON keeps all fields / UI hides unlabeled (D-004), no fabricated geometry (D-005),
refine numeric guards (D-006), backups before risky changes (D-008),
push requires owner approval (D-010).

## Known limitations

- Table row↔line-cluster mapping depends on detected line count; missing lines yield `bbox: null` honestly (by design, D-005).
- `?refine=1` free tier is nondeterministic/slow (180 s timeout) — E2E test on it is flaky by nature.
- E2E suite requires the docker engine (GPU) + UI running; cannot run headless in a bare session.
- Trailing space in `generalocr ` folder name is a persistent tooling trap.
- Outer README still primarily describes the dormant konkoor_synth sub-project (orientation note added 2026-11-21).

## Constraints

- Personal documents stay local (D-001). Secrets only in shell env, never tracked.
- One git repo, branch `main`; push = owner approval (D-010, enforced via permissions).
- Do not touch unrelated containers on this host (e.g. `autoseo-*`).

## Dependencies

- Surya 2.5 GGUF models in `datasets/surya_gguf/` + text-detection cache at `~/.cache/datalab/`.
- Docker + GPU for the engine; Playwright (global, system python3) for tests; vendored `_docprep` package (opt-in).

## Risks

- Global OpenCode skills for other projects can leak into sessions (observed 2026-11-21; owner remediated; project skill overrides `project-reliability`).
- Advisory-only protocol rules rely on agent compliance; audit is manual-trigger until hooked into CI/pre-commit.
- Tracked `.env` files are non-secret today; the audit's secret scan guards future regressions.

## Environment / verification

See AGENTS.md §8 (commands). Engine `./run_ui.sh`; audit `python3 tools/drift_audit.py`;
audit self-test `python3 tools/test_drift_audit.py`.

## Current task

None — reliability protocol installation completed 2026-11-21
(see `docs/reports/2026-11-21_ReliabilityProtocol.md`).

## Recommended next step

Owner reviews the protocol report; optional follow-ups: wire `tools/drift_audit.py`
into a pre-commit hook or CI, and review remaining global OpenCode skills for
cross-project contamination.
