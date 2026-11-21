#!/usr/bin/env python3
"""Evaluation suite for tools/drift_audit.py — the audit itself must be testable.

Builds disposable fixture git-repositories under /tmp/opencode (never inside the
real repo), injects representative failure scenarios, and asserts the audit's
findings and exit codes. Run from anywhere:

    python3 tools/test_drift_audit.py

Exit code 0 = all scenarios passed. Each scenario result is printed with
PASS/FAIL and the finding counts observed.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

AUDIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "drift_audit.py")
FIXTURE_BASE = os.environ.get("DRIFT_FIXTURE_BASE", "/tmp/opencode/drift_fixtures")

HEALTHY_STATE = """# PROJECT_STATE
Last updated: {today}
Verified against commit: {sha}

## Current task
none
"""

README_OK = "readme\n<!-- reliability:orientation -->\n"
DECISIONS_OK = """# DECISIONS
## D-001 — sample
- **Status:** accepted
- **Source:** somewhere real
"""

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def run(cmd: list[str], cwd: str | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=env)


def write(root: str, rel: str, content: str) -> None:
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def git(root: str, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    identity = ["-c", "user.email=t@t.local", "-c", "user.name=t"]
    return run(["git", *identity, *args], cwd=root, env=env)


def make_repo(name: str, files: dict[str, str] | None = None) -> str:
    root = os.path.join(FIXTURE_BASE, name)
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root, exist_ok=True)
    run(["git", "init", "-q", "-b", "main"], cwd=root)
    # a first commit so HEAD/sha checks have history
    write(root, "seed.txt", "seed\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "seed")
    sha = git(root, "rev-parse", "--short=7", "HEAD").stdout.strip()
    write(root, "AGENTS.md", "rulebook\n")
    write(root, "docs/REPORT_TEMPLATE.md", "template\n")
    write(root, "tools/drift_audit.py", "tool\n")
    write(root, "tools/test_drift_audit.py", "tool\n")
    write(root, ".opencode/opencode.jsonc", "{}\n")
    write(root, ".opencode/skills/project-reliability/SKILL.md", "skill\n")
    write(root, "docs/DECISIONS.md", DECISIONS_OK)
    write(root, "docs/PROJECT_STATE.md", HEALTHY_STATE.format(today=__import__("datetime").date.today().isoformat(), sha=sha))
    write(root, "README.md", README_OK)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "protocol files")
    if files:
        for rel, content in files.items():
            write(root, rel, content)
    return root


def audit(root: str, *extra: str) -> tuple[int, list[dict]]:
    r = run([sys.executable, AUDIT, "--root", root, "--json", *extra])
    if r.returncode not in (0, 1):
        return r.returncode, [{"severity": "ERROR", "check": "runner", "message": r.stderr[-400:]}]
    data = json.loads(r.stdout)
    return data["exit"], data["findings"]


def sev(findings: list[dict], s: str) -> list[dict]:
    return [f for f in findings if f["severity"] == s]


# --- scenarios ---------------------------------------------------------------

def scenario_healthy() -> None:
    """Clean fixture repo → audit exits 0 with no BLOCK/WARN."""
    root = make_repo("healthy")
    code, findings = audit(root)
    check("S01 healthy repo exits 0", code == 0, f"exit={code} findings={findings}")
    check("S01 no BLOCK/WARN", not sev(findings, "BLOCK") and not sev(findings, "WARN"), str(findings))


def scenario_missing_required() -> None:
    """Protocol file removed → BLOCK."""
    root = make_repo("missing_required")
    os.remove(os.path.join(root, "docs", "DECISIONS.md"))
    code, findings = audit(root)
    check("S02 missing protocol file → BLOCK", code == 1 and any("DECISIONS.md" in f["message"] for f in sev(findings, "BLOCK")), str(findings))


def scenario_uncommitted() -> None:
    """Uncommitted modification → WARN (BLOCK under --strict)."""
    root = make_repo("uncommitted")
    write(root, "seed.txt", "changed\n")
    code, findings = audit(root)
    check("S03 uncommitted change → WARN", code == 0 and any(f["check"] == "git-clean" for f in sev(findings, "WARN")), str(findings))
    code_s, _ = audit(root, "--strict")
    check("S03 strict mode → exit 1", code_s == 1, f"strict exit={code_s}")


def scenario_fabricated_state_sha() -> None:
    """PROJECT_STATE 'Verified against commit' points to a nonexistent sha → BLOCK."""
    root = make_repo("fabricated_sha")
    write(root, "docs/PROJECT_STATE.md", HEALTHY_STATE.format(today=__import__("datetime").date.today().isoformat(), sha="deadbee"))
    code, findings = audit(root)
    check("S04 fabricated state commit → BLOCK", code == 1 and any("does not exist in history" in f["message"] for f in sev(findings, "BLOCK")), str(findings))


def scenario_stale_state() -> None:
    """State sha is an ancestor but 'Last updated' predates the latest commit → WARN."""
    root = make_repo("stale_state")
    write(root, "docs/PROJECT_STATE.md", HEALTHY_STATE.format(today="2020-01-01", sha=git(root, "rev-parse", "--short=7", "HEAD").stdout.strip()))
    code, findings = audit(root)
    check("S05 stale state date → WARN", code == 0 and any("newer than PROJECT_STATE" in f["message"] for f in sev(findings, "WARN")), str(findings))


def scenario_fabricated_report_commit() -> None:
    """Newest report cites a commit that does not exist → BLOCK (fabricated provenance)."""
    root = make_repo("report_bad_commit")
    write(root, "docs/reports/2099-01-01_Feature.md", "Implemented, committed `0badc0d` and all tests pass.")
    code, findings = audit(root)
    check("S06 report cites nonexistent commit → BLOCK", code == 1 and any("0badc0d" in f["message"] for f in sev(findings, "BLOCK")), str(findings))


def scenario_missing_test_evidence() -> None:
    """Newest report claims tests in a file that does not exist → WARN (missing evidence)."""
    root = make_repo("report_missing_test")
    sha = git(root, "rev-parse", "--short=7", "HEAD").stdout.strip()
    write(root, "docs/reports/2099-01-01_Feature.md", f"Executed `webui/tests/ui_feature.py` 12/12 PASS. commit `{sha}`.")
    code, findings = audit(root)
    check("S07 report cites missing test file → WARN", code == 0 and any("ui_feature.py" in f["message"] for f in sev(findings, "WARN")), str(findings))
    check("S07 real commit ref not flagged", not any("does not exist in history" in f["message"] for f in findings), str(findings))


def scenario_missing_screenshot() -> None:
    """Report references a screenshot that does not exist → WARN."""
    root = make_repo("report_missing_shot")
    write(root, "docs/reports/2099-01-01_Feature.md", "Evidence: docs/reports/2099-01-01_Feature/proof.png")
    _, findings = audit(root)
    check("S08 report cites missing screenshot → WARN", any("proof.png" in f["message"] for f in sev(findings, "WARN")), str(findings))


def scenario_tracked_secret() -> None:
    """A tracked .env containing an API key → BLOCK."""
    root = make_repo("tracked_secret")
    write(root, ".env", "FONT_PATH=/x\nAPI_KEY=sk-abcdef123456\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "add env")
    code, findings = audit(root)
    check("S09 tracked secret env → BLOCK", code == 1 and any("possible secret" in f["message"] for f in sev(findings, "BLOCK")), str(findings))


def scenario_nonsecret_env() -> None:
    """A tracked .env with only benign values → no secret finding."""
    root = make_repo("benign_env")
    write(root, ".env", "FONT_PATH=/x\nPAGE_WIDTH=2480\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "benign env")
    _, findings = audit(root)
    check("S10 benign env not flagged", not any(f["check"] == "env-secrets" and f["severity"] == "BLOCK" for f in findings), str(findings))


def scenario_malformed_decisions() -> None:
    """A D-entry without Status/Source → WARN."""
    root = make_repo("bad_decisions")
    write(root, "docs/DECISIONS.md", "# DECISIONS\n## D-001 — vague thing\nsome text\n")
    _, findings = audit(root)
    msgs = " | ".join(f["message"] for f in sev(findings, "WARN"))
    check("S11 malformed decision → WARN", "D-001" in msgs and "Status" in msgs, msgs)


def scenario_readme_stale() -> None:
    """README without orientation marker → WARN."""
    root = make_repo("stale_readme")
    write(root, "README.md", "# only the old project description\n")
    _, findings = audit(root)
    check("S12 stale README → WARN", any("orientation" in f["message"] for f in sev(findings, "WARN")), str(findings))


def scenario_not_a_repo() -> None:
    """Non-git directory → BLOCK with a clear message, not a crash."""
    root = os.path.join(FIXTURE_BASE, "not_a_repo")
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root, exist_ok=True)
    code, findings = audit(root)
    check("S13 non-git root → BLOCK", code == 1 and any(f["check"] == "git" for f in sev(findings, "BLOCK")), str(findings))


def main() -> int:
    os.makedirs(FIXTURE_BASE, exist_ok=True)
    scenario_healthy()
    scenario_missing_required()
    scenario_uncommitted()
    scenario_fabricated_state_sha()
    scenario_stale_state()
    scenario_fabricated_report_commit()
    scenario_missing_test_evidence()
    scenario_missing_screenshot()
    scenario_tracked_secret()
    scenario_nonsecret_env()
    scenario_malformed_decisions()
    scenario_readme_stale()
    scenario_not_a_repo()

    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\nEvaluation suite: {passed}/{total} PASS")
    # keep fixtures for inspection, but cap growth
    shutil.rmtree(FIXTURE_BASE, ignore_errors=True)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
