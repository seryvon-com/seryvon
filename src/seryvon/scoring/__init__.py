"""Moteur de scoring déterministe et catalogue de règles."""

# Importer les règles déclenche leur auto-enregistrement dans RULES.
from seryvon.scoring import rules  # noqa: F401
from seryvon.scoring.engine import run_criteria, score_global, score_pillar

__all__ = ["run_criteria", "score_global", "score_pillar"]
