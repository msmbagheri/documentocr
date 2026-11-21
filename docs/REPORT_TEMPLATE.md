# Closeout report template — use for every substantial task

> Copy this file into `docs/reports/YYYY-MM-DD_<Slug>.md` and fill it in.
> Keep history in the report; update `docs/PROJECT_STATE.md` separately.
> Every completion claim needs evidence appropriate to its importance
> (AGENTS.md §2: status labels + evidence levels E0–E3).

# <Task> — Closeout (YYYY-MM-DD)

**Status labels used:** VERIFIED / INFERRED / ASSUMED / UNVERIFIED / BLOCKED
**Objective (1 line):** …
**Scope:** … · **Out of scope:** …

## 1. Changes (file-by-file)

| File | Change | In-scope |
|---|---|---|
| … | … | ✔/✘ |

## 2. Verification matrix

| Deliverable | Ladder status (Proposed→Planned→Implemented→Tested→Verified→Operational→Accepted) | Evidence (E-level) |
|---|---|---|
| … | … | … |

## 3. Executed tests

| Suite / command | Result | Evidence |
|---|---|---|
| … | n/n PASS | command output in … |

Never list a test you did not execute in this session without labeling it UNVERIFIED.

## 4. Drift audit

`python3 tools/drift_audit.py` result: … (BLOCK: n, WARN: n) + how findings were resolved.

## 5. Decisions

New entries appended to `docs/DECISIONS.md`: D-xxx (list) — or "none".

## 6. Incomplete / known limitations / risks

- …

## 7. Project state update

`docs/PROJECT_STATE.md` updated: Last updated = YYYY-MM-DD, Verified against commit = <sha>.

## 8. Scope statement

**Scope held** / **Scope EXPANDED (reason)**
