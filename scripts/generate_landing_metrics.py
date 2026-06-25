from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / ".github" / "landing-metrics.json"
PYPROJECT_PATH = ROOT / "pyproject.toml"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_project_version() -> str | None:
    raw = PYPROJECT_PATH.read_text(encoding="utf-8")
    in_project = False
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped == "[project]":
            in_project = True
            continue
        if in_project and stripped.startswith("["):
            break
        if in_project and stripped.startswith("version"):
            _, value = stripped.split("=", 1)
            return value.strip().strip('"').strip("'")
    return None


def load_pytest_summary(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    if root.tag == "testsuites":
        total = int(root.attrib.get("tests", "0"))
        failures = int(root.attrib.get("failures", "0"))
        errors = int(root.attrib.get("errors", "0"))
        skipped = int(root.attrib.get("skipped", "0"))
    else:
        total = int(root.attrib.get("tests", "0"))
        failures = int(root.attrib.get("failures", "0"))
        errors = int(root.attrib.get("errors", "0"))
        skipped = int(root.attrib.get("skipped", "0"))
    passed = max(total - failures - errors - skipped, 0)
    return {
        "total": total,
        "passed": passed,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
    }


def load_coverage_percent(path: Path) -> str | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    total = data.get("totals", {})
    covered = total.get("percent_covered")
    if covered is None:
        return None
    rounded = round(float(covered))
    return f"{rounded}%"


def env_or(
    existing: dict[str, Any], env_key: str, existing_key: str, fallback: Any = None
) -> Any:
    value = os.getenv(env_key)
    if value not in (None, ""):
        return value
    return existing.get(existing_key, fallback)


def main() -> None:
    existing = load_json(OUTPUT_PATH)
    existing_stats = existing.get("stats", {})
    pytest_summary = load_pytest_summary(ROOT / ".tmp-pytest.xml")
    coverage = load_coverage_percent(ROOT / ".tmp-coverage.json")
    project_version = load_project_version()

    stats = {
        "testsPassing": env_or(
            existing_stats,
            "LANDING_TESTS_PASSING",
            "testsPassing",
            str(pytest_summary.get("passed", pytest_summary.get("total", 0))),
        ),
        "testCoverage": env_or(
            existing_stats, "LANDING_TEST_COVERAGE", "testCoverage", coverage or "0%"
        ),
        "mypyStrictErrors": env_or(
            existing_stats, "LANDING_MYPY_ERRORS", "mypyStrictErrors", "0"
        ),
        "varianceOnRerun": env_or(
            existing_stats, "LANDING_VARIANCE", "varianceOnRerun", "<2%"
        ),
        "currentRelease": env_or(
            existing_stats,
            "LANDING_CURRENT_RELEASE",
            "currentRelease",
            project_version or existing_stats.get("currentRelease") or "dev",
        ),
        "pillarsUnified": env_or(
            existing_stats, "LANDING_PILLARS_UNIFIED", "pillarsUnified", "5"
        ),
        "auditDuration": env_or(
            existing_stats, "LANDING_AUDIT_DURATION", "auditDuration", "~4min"
        ),
        "ssrfGuard": env_or(existing_stats, "LANDING_SSRF_GUARD", "ssrfGuard", "SSRF"),
    }

    payload = {
        "stats": stats,
        "roadmap": existing.get("roadmap", {}),
        "milestones": existing.get("milestones", []),
    }

    OUTPUT_PATH.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
