# DECISIONS — accepted decision log (append-only)

> Append new decisions with the next D-number. Never rewrite or delete existing
> entries — supersede with a new entry that names what it replaces.
> Status values: `proposed` / `accepted` / `superseded by D-xxx` / `reversed`.

---

## D-001 — OCR engine: local Surya 2.5 via llama.cpp, no cloud OCR

- **Decision:** Run OCR fully locally: Surya 2.5 (GGUF Q8_0 + mmproj) served by llama.cpp in docker container `surya-llama` (127.0.0.1:8080). No cloud OCR APIs.
- **Context:** Project processes real personal Persian insurance/ID documents.
- **Alternatives considered:** Google DocAI / Azure / Textract — rejected: paid + privacy risk for personal documents + network dependency.
- **Consequences:** Local assets required (`datasets/surya_gguf/`), GPU needed, engine startup time.
- **Risks:** Model quality limits on old scans (olmOCR OldScan 44.3% per report 0.11.1).
- **Status:** accepted
- **Source:** `generalocr /general_ocr-main/README.md` (Local Surya section); `2026-11-15_TableFields.md` §0.5.4.
- **Date:** 2026-11-14 (inferred from reports) · recorded 2026-11-21

## D-002 — Preprocessing: default raw; never binarize/contrast/denoise for Surya

- **Decision:** Default = no preprocessing (raw image to Surya). `enhance` (v2.2: illumination gate + upscale + projection deskew) and `docprep geometry` are opt-in. Never use binarization/adaptive/contrast/sharpen on images sent to Surya.
- **Context:** A/B evidence: raw 5/5 fields; full docprep pipeline 0/5 + numeric noise; contrast+denoise 1/5. Surya's internal preprocessing is only `scale_to_fit` (3072×2048 cap, LANCZOS, 28px grid) — verified in surya v0.23.0 code.
- **Alternatives considered:** Tesseract-oriented preprocessing packages — designed for a different engine family.
- **Consequences:** Default OFF keeps good-document quality (8/45/42 per report §0.5.1); degraded/dark scans need the opt-in toggle.
- **Risks:** Users may enable `full` for A/B — expected to regress (documented in UI menu).
- **Status:** accepted
- **Source:** commit `941bafe` (research + evidence); TableFields report §0.5, §0.10.2, §0.11.
- **Date:** 2026-11-16 · recorded 2026-11-21

## D-003 — Feature work = post-processing only; engine logic untouched

- **Decision:** New features (table fields, KV pairing, refine, UI) are implemented in `webui/server.py` + frontend. The Detector/Recognizer/OCR engine logic is not modified for feature work.
- **Context:** Engine behavior is benchmarked and evidence-tuned; feature changes must not regress OCR quality.
- **Consequences:** Feature scope confined to post-processing + UI layers.
- **Risks:** Some UX improvements may need engine changes — these require a new decision + A/B evidence.
- **Status:** accepted
- **Source:** `2026-11-15_TableFields.md` §3 ("هیچ تغییری در Detector/Recognizer").
- **Date:** 2026-11-15 · recorded 2026-11-21

## D-004 — JSON keeps all fields; UI hides unlabeled fields

- **Decision:** All extracted fields (including keyless/unlabeled) stay in JSON (`blocks[].fields[]`). The UI list/image show only fields with a real key label; unlabeled ones are hidden from display but never deleted.
- **Context:** User feedback on insurance doc: unlabeled cells showed as "بدون عنوان" noise.
- **Alternatives considered:** Fabricating labels by pairing cells — rejected as unstable inference (cells swap order between identical runs; see §10.8 of the report).
- **Consequences:** No data loss; display stays clean; counts differ between JSON and UI by design.
- **Status:** accepted
- **Source:** `2026-11-15_TableFields.md` §10.2, §10.8.
- **Date:** 2026-11-15 · recorded 2026-11-21

## D-005 — No fabricated geometry: honest `bbox: null`

- **Decision:** When no real detection line exists for a field, emit `bbox: null` + `bbox_status` ("none"/"real line"/"union") — never split the table rectangle or guess coordinates.
- **Context:** A previous approach fabricated box positions; violates project evidence principle.
- **Consequences:** UI shows «بدون مختصات معتبر» for geometry-less fields.
- **Status:** accepted
- **Source:** `2026-11-15_TableFields.md` §3.4, §9.
- **Date:** 2026-11-15 · recorded 2026-11-21

## D-006 — LLM text refine (`?refine=1`) with hard numeric-safety guards, default OFF

- **Decision:** Optional Persian text correction via free LLM tier; server-side guards: (1) every numeric sequence must survive byte-identical, (2) per-line similarity ≥ 0.5, else original line returned. Off by default.
- **Context:** LLMs improve Persian word errors (یال/تهرات/رافندگی) but may alter digits; numbers must never be touched.
- **Consequences:** Deterministic worst case = original text; free tier is slow/nondeterministic.
- **Status:** accepted
- **Source:** commit `fa59c14`; TableFields report §0.8.4 (unit test: `۰۰۰→۰۰۱` attempt rejected).
- **Date:** 2026-11-16 · recorded 2026-11-21

## D-007 — Backups before risky changes

- **Decision:** Create a dated tarball in `backups/` before risky changes to `generalocr /general_ocr-main/` (e.g. `backups/2026-11-15_pre_table_fields.tar.gz`), with a documented restore command.
- **Consequences:** Rollback option always exists for webui changes.
- **Status:** accepted
- **Source:** `backups/` contents; TableFields report §8.
- **Date:** 2026-11-14..15 · recorded 2026-11-21

## D-008 — Evidence reports in `docs/reports/` with screenshots + test counts

- **Decision:** Each feature ships with a dated report (Persian, repo convention `YYYY-MM-DD_<Name>.md` or a dated folder) containing: real-user need, real-data verification, implementation, executed test counts, screenshots, known limitations, and rollback notes.
- **Consequences:** Strong historical evidence trail; reports may go stale — per authority matrix they are leads, not current status.
- **Status:** accepted
- **Source:** 14 report files/folders in `docs/reports/`.
- **Date:** 2026-11-14..16 · recorded 2026-11-21

## D-009 — Git: single repo `main`; push requires owner approval

- **Decision:** Work lands as local commits on `main` (remote `origin = git@github.com:msmbagheri/documentocr.git`). `git push` requires explicit owner approval and is permission-gated (`ask` in `.opencode/opencode.jsonc`).
- **Context:** Report 0.7 said "remote not configured" — stale; remote verified present and synced 2026-11-21 (supersedes that note).
- **Status:** accepted
- **Source:** `git remote -v` (verified 2026-11-21); `.opencode/opencode.jsonc`.
- **Date:** 2026-11-21 · recorded 2026-11-21

## D-010 — Reliability & anti-drift protocol installed (project-wide)

- **Decision:** Install: `AGENTS.md` rulebook, `docs/PROJECT_STATE.md`, this log, `.opencode/skills/project-reliability/SKILL.md`, `tools/drift_audit.py` + `tools/test_drift_audit.py`, `.opencode/opencode.jsonc` permissions, README orientation note.
- **Context:** Mission (owner, 2026-11-21): permanent evidence-driven reliability system; control hallucination/drift/false-completion risk.
- **Alternatives considered:** Global-only instructions (rejected: cross-project contamination observed live this session); heavy governance platform (rejected: unnecessary complexity).
- **Consequences:** Future agents must follow the workflow (§7 of AGENTS.md); audit is enforced-when-run, most rules advisory.
- **Risks:** Compliance depends on agents reading instructions; audit not yet wired into CI.
- **Status:** accepted
- **Source:** `docs/reports/2026-11-21_ReliabilityProtocol.md`.
- **Date:** 2026-11-21 · recorded 2026-11-21
