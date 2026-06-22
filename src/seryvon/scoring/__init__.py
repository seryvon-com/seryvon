"""Deterministic scoring engine and rule catalog."""

# Importing the rules triggers their self-registration in RULES.
from seryvon.scoring import rules  # noqa: F401
from seryvon.scoring.comparison import (
    Comparability,
    ComparisonMode,
    ComparisonResult,
    IncomparableError,
    classify,
    compare_scorecards,
)
from seryvon.scoring.engine import (
    coverage_label,
    run_criteria,
    score_coverage,
    score_global,
    score_pillar,
)
from seryvon.scoring.issues import build_issues
from seryvon.scoring.readiness import compute_aso_readiness

__all__ = [
    "Comparability",
    "ComparisonMode",
    "ComparisonResult",
    "IncomparableError",
    "build_issues",
    "classify",
    "compare_scorecards",
    "compute_aso_readiness",
    "coverage_label",
    "run_criteria",
    "score_coverage",
    "score_global",
    "score_pillar",
]
