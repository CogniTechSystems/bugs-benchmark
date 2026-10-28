"""Running a challenge's hidden test suite against an isolated copy of its source."""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from app.services.challenges import Challenge

_RESULT_LINE = re.compile(r"^(PASSED|FAILED|ERROR|XPASS|XFAIL)\s+(\S+)")


@dataclass(frozen=True)
class TestRunResult:
    passed: frozenset[str] = field(default_factory=frozenset)
    failed: frozenset[str] = field(default_factory=frozenset)
    output: str = ""

    @property
    def all_tests(self) -> frozenset[str]:
        return self.passed | self.failed


class TestRunner:
    """Copies a challenge into a temporary directory, applies overrides and runs pytest."""

    __test__ = False

    def __init__(self, timeout_seconds: int) -> None:
        self._timeout_seconds = timeout_seconds

    def run(self, challenge: Challenge, overrides: dict[str, str] | None = None) -> TestRunResult:
        with tempfile.TemporaryDirectory(prefix="bhb-score-") as temp_dir:
            workspace = Path(temp_dir)
            shutil.copytree(challenge.source_dir, workspace / "src")
            shutil.copytree(challenge.tests_dir, workspace / "tests")
            for relative_path, content in (overrides or {}).items():
                (workspace / "src" / relative_path).write_text(content, encoding="utf-8")
            return self._run_pytest(workspace)

    def _run_pytest(self, workspace: Path) -> TestRunResult:
        command = [
            sys.executable,
            "-m",
            "pytest",
            "tests",
            "-q",
            "-rA",
            "--tb=line",
            "--color=no",
            "-p",
            "no:cacheprovider",
        ]
        environment = {
            **os.environ,
            "PYTHONPATH": str(workspace / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
        }
        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return TestRunResult(output=f"Test run exceeded {self._timeout_seconds} seconds.")
        return parse_pytest_summary(completed.stdout + completed.stderr)


def parse_pytest_summary(output: str) -> TestRunResult:
    passed: set[str] = set()
    failed: set[str] = set()
    for line in output.splitlines():
        match = _RESULT_LINE.match(line)
        if not match:
            continue
        outcome, node_id = match.groups()
        node_id = node_id.replace("\\", "/")
        if outcome in {"PASSED", "XFAIL"}:
            passed.add(node_id)
        else:
            failed.add(node_id)
    return TestRunResult(frozenset(passed), frozenset(failed - passed), output)


def expand_test_ids(selectors: tuple[str, ...], available: frozenset[str]) -> set[str]:
    """Resolve manifest test selectors, including all parametrised variants of a test."""
    return {
        test_id
        for selector in selectors
        for test_id in available
        if test_id == selector or test_id.startswith(f"{selector}[")
    }
