#!/usr/bin/env python3
"""Project drift audit for the documentocr repository.

Compares actual repository state against the authoritative protocol files and
flags drift: uncommitted work, missing protocol files, stale project state,
fabricated provenance (nonexistent commits), missing evidence artifacts
(test files / screenshots referenced by reports), tracked secrets, and
malformed decision records.

Usage:
    python3 tools/drift_audit.py [--root PATH] [--strict] [--all-reports] [--json]

Exit codes:
    0  no BLOCK findings (and, under --strict, no WARN findings)
    1  at least one BLOCK finding (or any finding under --strict)
    2  usage / environment error

The audit reports findings only — it never fixes anything automatically.
Enforced when run; it does not run by itself (wire into CI/hooks to automate).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date

# --- protocol files that must exist in the repository -----------------------
REQUIRED_FILES = [
    "AGENTS.md",
    "docs/PROJECT_STATE.md",
    "docs/DECISIONS.md",
    "docs/REPORT_TEMPLATE.md",
    ".opencode/skills/project-reliability/SKILL.md",
    ".opencode/opencode.jsonc",
    "tools/drift_audit.py",
    "tools/test_drift_audit.py",
]

ORIENTATION_MARKER = "reliability:orientation"
INNER_PROJECT = "generalocr /general_ocr-main"  # note: trailing space is real

SECRETS_KEY_RE = re.compile(r"(SECRET|TOKEN|PASSWORD|PASSWD|API_?KEY|PRIVATE)", re.I)
PLACEHOLDER_VALUES = {"", "changeme", "change-me", "xxx", "<your-key-here>", "none", "null"}

COMMIT_REF_RE = re.compile(r"(?:commit\w*|کامیت)\b\s*`?\s*([0-9a-f]{7,40})`?", re.I)
TEST_REF_RE = re.compile(r"(webui/tests/[A-Za-z0-9_./-]+\.py)")
DOC_FILE_REF_RE = re.compile(r"((?:docs/reports|webui/tests/data)/[^\s`\)\]，؛]+?\.(?:png|jpg|jpeg))")
DECISION_HEADING_RE = re.compile(r"^#{2,3}\s+D-\d+", re.M)


class Audit:
    def __init__(self, root: str, strict: bool = False):
        self.root = os.path.abspath(root)
        self.strict = strict
        self.findings: list[dict] = []

    def add(self, sev: str, check: str, msg: str) -> None:
        self.findings.append({"severity": sev, "check": check, "message": msg})

    def block(self, check: str, msg: str) -> None:
        self.add("BLOCK", check, msg)

    def warn(self, check: str, msg: str) -> None:
        self.add("WARN", check, msg)

    def info(self, check: str, msg: str) -> None:
        self.add("INFO", check, msg)

    # -- helpers ------------------------------------------------------------
    def git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", self.root, *args], capture_output=True, text=True
        )

    def read(self, rel: str) -> str | None:
        try:
            with open(os.path.join(self.root, rel), "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return None

    def exists(self, rel: str) -> bool:
        return os.path.exists(os.path.join(self.root, rel))

    def resolve_repo_file(self, ref: str) -> bool:
        """Resolve a path referenced from a report against both possible bases."""
        return self.exists(ref) or self.exists(os.path.join(INNER_PROJECT, ref))

    @staticmethod
    def expand_braces(path: str) -> list[str]:
        """Expand bash-style {a,b,c} shorthand (reports use it for screenshot lists)."""
        m = re.search(r"\{([^{}]+)\}", path)
        if not m:
            return [path]
        out: list[str] = []
        for alt in m.group(1).split(","):
            out.extend(Audit.expand_braces(path[: m.start()] + alt + path[m.end():]))
        return out

    # -- checks -------------------------------------------------------------
    def check_git_available(self) -> bool:
        r = self.git("rev-parse", "--git-dir")
        if r.returncode != 0:
            self.block("git", f"not a git repository: {self.root}")
            return False
        return True

    def check_repo_clean(self) -> None:
        r = self.git("status", "--porcelain")
        if r.returncode != 0:
            self.warn("git-clean", f"git status failed: {r.stderr.strip()}")
            return
        untracked, modified = [], []
        for line in r.stdout.splitlines():
            if not line.strip():
                continue
            (untracked if line.startswith("??") else modified).append(line[3:].strip())
        if untracked:
            self.warn(
                "git-clean",
                f"{len(untracked)} untracked file(s), not committed: {untracked[:8]}"
                + (" …" if len(untracked) > 8 else ""),
            )
        if modified:
            self.warn(
                "git-clean",
                f"{len(modified)} uncommitted change(s): {modified[:8]}"
                + (" …" if len(modified) > 8 else ""),
            )
        if not untracked and not modified:
            self.info("git-clean", "working tree clean (all protocol/project files committed)")

    def check_required_files(self) -> None:
        for rel in REQUIRED_FILES:
            if not self.exists(rel):
                self.block("required-files", f"missing required protocol file: {rel}")

    def check_state_freshness(self) -> None:
        text = self.read("docs/PROJECT_STATE.md")
        if text is None:
            return  # already flagged by required-files
        m = re.search(r"Verified against commit:\s*([0-9a-f]{7,40})", text)
        if not m:
            self.warn("state-freshness", "PROJECT_STATE.md has no 'Verified against commit:' line")
        else:
            sha = m.group(1)
            v = self.git("rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}")
            if v.returncode != 0:
                self.block(
                    "state-freshness",
                    f"PROJECT_STATE.md 'Verified against commit' sha {sha!r} does not exist in history (fabricated or typo?)",
                )
            else:
                anc = self.git("merge-base", "--is-ancestor", sha, "HEAD")
                if anc.returncode != 0:
                    self.warn(
                        "state-freshness",
                        f"PROJECT_STATE.md verified-commit {sha} is not an ancestor of HEAD — state may be stale",
                    )
                else:
                    self.info("state-freshness", f"PROJECT_STATE.md verified-commit {sha} is an ancestor of HEAD")
        m = re.search(r"Last updated:\s*(\d{4}-\d{2}-\d{2})", text)
        if not m:
            self.warn("state-freshness", "PROJECT_STATE.md has no 'Last updated:' date")
        else:
            last = date.fromisoformat(m.group(1))
            r = self.git("log", "-1", "--format=%cs")
            if r.returncode == 0 and r.stdout.strip():
                head_date = date.fromisoformat(r.stdout.strip()[:10])
                if head_date > last:
                    self.warn(
                        "state-freshness",
                        f"latest commit date {head_date} is newer than PROJECT_STATE.md 'Last updated' {last} — update the state file",
                    )
                else:
                    self.info("state-freshness", f"PROJECT_STATE.md last updated {last} ≥ latest commit date {head_date}")

    def check_report_artifacts(self, all_reports: bool = False) -> None:
        reports_dir = os.path.join(self.root, "docs", "reports")
        if not os.path.isdir(reports_dir):
            return
        reports = sorted(
            (f for f in os.listdir(reports_dir) if f.endswith(".md")),
            key=lambda n: (n[:10], n),
            reverse=True,
        )
        if not reports:
            return
        selected = reports if all_reports else reports[:1]
        self.info("report-artifacts", f"scanning report(s): {', '.join(selected)}")
        for name in selected:
            text = self.read(os.path.join("docs", "reports", name)) or ""
            for sha in sorted(set(COMMIT_REF_RE.findall(text))):
                v = self.git("rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}")
                if v.returncode != 0:
                    self.block(
                        "report-artifacts",
                        f"{name} references commit {sha!r} that does not exist in history (fabricated provenance?)",
                    )
            for ref in sorted(set(TEST_REF_RE.findall(text))):
                if not self.resolve_repo_file(ref):
                    self.warn(
                        "report-artifacts",
                        f"{name} references test file {ref!r} which does not exist (claimed evidence missing?)",
                    )
            for ref in sorted(set(DOC_FILE_REF_RE.findall(text))):
                candidates = self.expand_braces(ref)
                if not all(self.resolve_repo_file(c) for c in candidates):
                    self.warn(
                        "report-artifacts",
                        f"{name} references artifact {ref!r} which does not exist on disk",
                    )

    def check_tracked_env_secrets(self) -> None:
        ls = self.git("ls-files")
        if ls.returncode != 0:
            return
        env_files = [
            f for f in ls.stdout.splitlines()
            if os.path.basename(f) == ".env" or ".env." in os.path.basename(f)
        ]
        if not env_files:
            self.info("env-secrets", "no tracked .env files")
            return
        self.info("env-secrets", f"tracked env file(s) scanned: {env_files}")
        for rel in env_files:
            text = self.read(rel) or ""
            for lineno, line in enumerate(text.splitlines(), 1):
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                val = val.strip().strip('"').strip("'")
                if SECRETS_KEY_RE.search(key) and val.lower() not in PLACEHOLDER_VALUES:
                    self.block(
                        "env-secrets",
                        f"possible secret tracked in git: {rel}:{lineno} (key {key.split('=')[0]!r}) — remove from tracking, rotate the key",
                    )

    def check_decisions_format(self) -> None:
        text = self.read("docs/DECISIONS.md")
        if text is None:
            return  # already flagged
        blocks = DECISION_HEADING_RE.split(text)[1:]
        headings = DECISION_HEADING_RE.findall(text)
        if not headings:
            self.warn("decisions-format", "DECISIONS.md contains no D-xxx decision entries")
            return
        for heading, body in zip(headings, blocks):
            did = heading.split()[-1]
            low = body.lower()
            if not re.search(r"\*\*status\b", low):
                self.warn("decisions-format", f"{did} missing a **Status** line")
            if not re.search(r"\*\*source\b", low):
                self.warn("decisions-format", f"{did} missing a **Source** line (evidence pointer)")
        self.info("decisions-format", f"{len(headings)} decision entries checked")

    def check_readme_orientation(self) -> None:
        text = self.read("README.md") or ""
        if ORIENTATION_MARKER not in text:
            self.warn(
                "readme-orientation",
                "README.md lacks the repository-orientation marker — outer README still describes only konkoor_synth",
            )
        else:
            self.info("readme-orientation", "README orientation marker present")

    # -- driver --------------------------------------------------------------
    def run(self, all_reports: bool = False) -> None:
        if self.check_git_available():
            self.check_repo_clean()
            self.check_state_freshness()
            self.check_report_artifacts(all_reports)
            self.check_tracked_env_secrets()
        self.check_required_files()
        self.check_decisions_format()
        self.check_readme_orientation()

    def summary(self) -> str:
        counts = {s: sum(1 for f in self.findings if f["severity"] == s) for s in ("BLOCK", "WARN", "INFO")}
        return f"Summary: {counts['BLOCK']} BLOCK, {counts['WARN']} WARN, {counts['INFO']} INFO"

    def exit_code(self) -> int:
        blocks = any(f["severity"] == "BLOCK" for f in self.findings)
        warns = any(f["severity"] == "WARN" for f in self.findings)
        return 1 if (blocks or (self.strict and warns)) else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="documentocr project drift audit")
    p.add_argument("--root", default=".", help="repository root (default: cwd)")
    p.add_argument("--strict", action="store_true", help="treat WARN findings as failures")
    p.add_argument("--all-reports", action="store_true", help="scan all reports, not only the newest")
    p.add_argument("--json", action="store_true", help="emit findings as JSON")
    args = p.parse_args(argv)

    audit = Audit(args.root, strict=args.strict)
    audit.run(all_reports=args.all_reports)

    if args.json:
        print(json.dumps({"root": audit.root, "findings": audit.findings,
                          "summary": audit.summary(), "exit": audit.exit_code()},
                         ensure_ascii=False, indent=2))
    else:
        print(f"DRIFT AUDIT — {audit.root}")
        for f in audit.findings:
            print(f"[{f['severity']}] {f['check']}: {f['message']}")
        print(audit.summary())
    return audit.exit_code()


if __name__ == "__main__":
    sys.exit(main())
