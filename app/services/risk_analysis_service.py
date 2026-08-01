"""
Day 9 — Risk Analysis.

Rule-based flags, not ML — same explainability-first reasoning used
throughout this project (Day 7's round-robin, Day 8's greedy workload
assignment): a mentor needs to know *why* a team is flagged, and a short
list of threshold rules is far easier to justify than a black-box
classifier, especially with no labeled "this team actually had a conflict"
data to train one on.
"""
from app import models
from app.services.matching_service import team_diversity

# Thresholds — deliberately simple, named constants so they're easy to find
# and tune without touching the rule logic itself.
SKILL_OVERLAP_DIVERSITY_THRESHOLD = 0.55   # team_diversity below this = skills overlap heavily (0.5 = identical sets)
SKILL_OVERLAP_HIGH_SEVERITY_THRESHOLD = 0.5
LOW_ATTENDANCE_THRESHOLD = 75.0            # any member below this attendance_pct
LOW_ATTENDANCE_HIGH_SEVERITY_THRESHOLD = 50.0
LEADERSHIP_GAP_THRESHOLD = 6.0             # no member at/above this leadership_score = no strong candidate leader
HIGH_CONFLICT_COMPATIBILITY_THRESHOLD = 50.0   # team compatibility_score below this = elevated conflict risk
HIGH_CONFLICT_HIGH_SEVERITY_THRESHOLD = 35.0


def _skill_overlap_risk(diversity_score: float) -> dict | None:
    if diversity_score >= SKILL_OVERLAP_DIVERSITY_THRESHOLD:
        return None
    severity = "high" if diversity_score < SKILL_OVERLAP_HIGH_SEVERITY_THRESHOLD else "medium"
    return {
        "type": "skill_overlap",
        "severity": severity,
        "message": (
            f"Team skill diversity is low ({diversity_score:.2f}) — members' skill sets "
            f"overlap heavily instead of complementing each other."
        ),
    }


def _low_attendance_risk(members: list[models.Intern]) -> dict | None:
    flagged = [m for m in members if (m.attendance_pct or 0.0) < LOW_ATTENDANCE_THRESHOLD]
    if not flagged:
        return None
    severity = "high" if any((m.attendance_pct or 0.0) < LOW_ATTENDANCE_HIGH_SEVERITY_THRESHOLD for m in flagged) else "medium"
    names = ", ".join(m.full_name for m in flagged)
    return {
        "type": "low_attendance",
        "severity": severity,
        "message": f"Below-threshold attendance ({LOW_ATTENDANCE_THRESHOLD:.0f}%): {names}.",
    }


def _leadership_gap_risk(members: list[models.Intern]) -> dict | None:
    if any((m.leadership_score or 0.0) >= LEADERSHIP_GAP_THRESHOLD for m in members):
        return None
    return {
        "type": "leadership_gap",
        "severity": "medium",
        "message": (
            f"No member scores {LEADERSHIP_GAP_THRESHOLD:.0f}+ on leadership — "
            f"team may lack a strong natural leader."
        ),
    }


def _high_conflict_likelihood_risk(compatibility_score: float | None) -> dict | None:
    # None (or the model's own "not yet calculated" default of 0.0) means
    # no signal, not "a score of zero" — absence of data isn't evidence of
    # high conflict risk, same reasoning as the neutral defaults elsewhere.
    if not compatibility_score or compatibility_score >= HIGH_CONFLICT_COMPATIBILITY_THRESHOLD:
        return None
    severity = "high" if compatibility_score < HIGH_CONFLICT_HIGH_SEVERITY_THRESHOLD else "medium"
    return {
        "type": "high_conflict_likelihood",
        "severity": severity,
        "message": f"Compatibility score is low ({compatibility_score:.1f}/100) — elevated risk of friction within the team.",
    }


def assess_risks(
    members: list[models.Intern],
    compatibility_score: float | None = None,
    diversity_score: float | None = None,
) -> list[dict]:
    """Every applicable risk flag for a team, rule-based and independently
    explainable. Returns [] for a team with no flags."""
    if diversity_score is None:
        diversity_score = team_diversity(members)

    checks = [
        _skill_overlap_risk(diversity_score),
        _low_attendance_risk(members),
        _leadership_gap_risk(members),
        _high_conflict_likelihood_risk(compatibility_score),
    ]
    return [risk for risk in checks if risk is not None]
