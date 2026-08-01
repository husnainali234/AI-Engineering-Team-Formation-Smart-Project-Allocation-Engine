"""
Day 16 — Bonus Feature (Engineer B): Team Chemistry Prediction.

Deliberately distinct from Day 6's Compatibility Score and Day 9's Success
Probability, not a rehash of either:

- Compatibility (Day 6) averages six *pairwise* signals across every
  member pair — it can't see team-level structural effects like "this
  team has two equally strong leaders", because two similarly-scoring
  leaders actually score *well* on compatibility's pairwise leadership
  component (it rewards similarity, not difference-from-ideal).
- Success Probability (Day 9) predicts project outcome from
  attendance/feedback/skill-balance — a performance forecast, not an
  interpersonal-friction one.

Chemistry instead looks at four *team-level* signals none of the earlier
engines use for this purpose: how many strong leaders the team has (ideal
is exactly one), how much members' project_interests actually overlap
(that field exists on Intern since Day 1 but until now was only ever
folded into the Day 4 embedding text, never read as a discrete signal),
how spread out communication styles are across the whole team (not
pairwise-averaged), and whether mentors have already written down
interpersonal friction in MentorFeedback.comments (free text that no
engine reads today — score is used by Day 9, comments never are).

Same weighted-components-with-breakdown shape as compatibility_service
and leadership_service, so it's explainable the same way, plus a short
list of plain-English flags a mentor can act on directly.
"""
from itertools import combinations
from statistics import pstdev

from app import models

# Weights must sum to 1.0.
CHEMISTRY_WEIGHTS: dict[str, float] = {
    "leadership_balance": 0.30,
    "shared_interests": 0.20,
    "communication_spread": 0.25,
    "feedback_sentiment": 0.25,
}

# leadership_score (0-10) at or above this counts as a "strong leader" for
# the leadership-balance signal. Same rough tier compatibility_service's
# soft-skill components treat as "solid" (score/10 well above the 0.5
# midpoint).
STRONG_LEADER_THRESHOLD = 7.0

# Rule-based sentiment scan over MentorFeedback.comments — deliberately a
# small, transparent keyword list rather than a trained sentiment model:
# there's no labeled "this comment indicates team friction" dataset in
# this system to train one on (same honest constraint Day 9's
# success_probability_model docstring calls out for outcome data), and a
# short, auditable word list is easier for a mentor to trust or dispute
# than an opaque score. Comments simply mentioning neither list are
# neutral, not penalized.
_POSITIVE_FEEDBACK_KEYWORDS = [
    "great teamwork", "collaborative", "supportive", "team player",
    "works well with", "positive attitude", "reliable", "proactive",
]
_NEGATIVE_FEEDBACK_KEYWORDS = [
    "conflict", "clash", "difficult to work with", "disruptive",
    "dismissive", "uncooperative", "tension", "friction",
]


def _leadership_balance_component(members: list[models.Intern]) -> tuple[float, int]:
    """1.0 at exactly one strong leader (the ideal — clear ownership, no
    rivalry). Zero strong leaders is a mild risk (0.4 — rudderless, but
    plenty of teams succeed with a quieter, collaborative dynamic instead
    of one dominant leader, so this isn't scored as harshly as the
    multi-leader case). Each additional strong leader past the first is a
    steeper, concrete "competing ownership" risk."""
    strong_leaders = sum(1 for m in members if (m.leadership_score or 0.0) >= STRONG_LEADER_THRESHOLD)
    if strong_leaders == 1:
        return 1.0, strong_leaders
    if strong_leaders == 0:
        return 0.4, strong_leaders
    return max(0.0, 1.0 - 0.25 * (strong_leaders - 1)), strong_leaders


def _interest_set(member: models.Intern) -> set[str]:
    if not member.project_interests:
        return set()
    return {i.strip().lower() for i in member.project_interests.split(",") if i.strip()}


def _shared_interests_component(members: list[models.Intern]) -> tuple[float, bool]:
    """Average pairwise Jaccard similarity of project_interests across
    every member pair. Neutral (0.5) when fewer than two members have any
    interests on record — absence of data isn't evidence of poor fit,
    same convention Day 6/9's neutral defaults use."""
    interest_sets = [s for s in (_interest_set(m) for m in members) if s]
    if len(interest_sets) < 2:
        return 0.5, False

    scores = []
    for a, b in combinations(interest_sets, 2):
        union = a | b
        scores.append(len(a & b) / len(union) if union else 0.0)
    return round(sum(scores) / len(scores), 4), True


def _communication_spread_component(members: list[models.Intern]) -> float:
    """1.0 = every member communicates at a similar level (low friction
    surface), degrading as the spread widens. Population stdev of a 0-10
    score maxes out around 5.0 (all-0s vs all-10s split down the middle),
    so that's the normalization ceiling."""
    scores = [m.communication_score or 0.0 for m in members]
    if len(scores) < 2:
        return 1.0
    spread = pstdev(scores)
    return max(0.0, 1.0 - spread / 5.0)


def _feedback_sentiment_component(feedback_entries: list[models.MentorFeedback]) -> tuple[float, bool]:
    comments = [f.comments.lower() for f in feedback_entries if f.comments]
    if not comments:
        return 0.5, False

    positive_hits = sum(1 for c in comments for kw in _POSITIVE_FEEDBACK_KEYWORDS if kw in c)
    negative_hits = sum(1 for c in comments for kw in _NEGATIVE_FEEDBACK_KEYWORDS if kw in c)
    raw = 0.5 + 0.1 * (positive_hits - negative_hits)
    return max(0.0, min(1.0, raw)), True


def _label(score: float) -> str:
    if score >= 75.0:
        return "Strong"
    if score >= 50.0:
        return "Workable"
    return "Fragile"


def predict_team_chemistry(
    members: list[models.Intern], feedback_entries: list[models.MentorFeedback]
) -> dict:
    """Returns {chemistry_score (0-100), label, components: {name:
    {raw_score, weight, contribution}}, flags: [str, ...]}. Team-level,
    not pairwise — needs at least one member to return a meaningful
    result (a single-member "team" is neutral-scored throughout, since
    there's no interpersonal dynamic to assess yet)."""
    if not members:
        return {"member_count": 0, "chemistry_score": 0.0, "label": "Fragile", "components": {}, "flags": []}

    leadership_raw, strong_leader_count = _leadership_balance_component(members)
    interests_raw, has_interest_data = _shared_interests_component(members)
    communication_raw = _communication_spread_component(members)
    feedback_raw, has_feedback_data = _feedback_sentiment_component(feedback_entries)

    raw_by_component = {
        "leadership_balance": leadership_raw,
        "shared_interests": interests_raw,
        "communication_spread": communication_raw,
        "feedback_sentiment": feedback_raw,
    }

    components = {}
    total = 0.0
    for name, raw in raw_by_component.items():
        weight = CHEMISTRY_WEIGHTS[name]
        contribution = raw * weight
        components[name] = {
            "raw_score": round(raw, 4),
            "weight": weight,
            "contribution": round(contribution, 4),
        }
        total += contribution

    chemistry_score = round(max(0.0, min(100.0, total * 100)), 2)

    flags = []
    if strong_leader_count >= 2:
        flags.append(
            f"{strong_leader_count} strong leaders on this team — assign explicit ownership "
            f"boundaries up front to avoid competing direction."
        )
    elif strong_leader_count == 0:
        flags.append("No clear strong leader on this team — consider designating one explicitly.")
    if has_interest_data and interests_raw < 0.15:
        flags.append("Little to no overlap in stated project interests among members.")
    if communication_raw < 0.4:
        flags.append(
            "Wide gap in communication-style scores across the team — pair the strongest and "
            "weakest communicators intentionally rather than leaving it to chance."
        )
    if has_feedback_data and feedback_raw < 0.4:
        flags.append("Prior mentor feedback flags interpersonal friction — review before finalizing.")

    return {
        "member_count": len(members),
        "chemistry_score": chemistry_score,
        "label": _label(chemistry_score),
        "components": components,
        "flags": flags,
    }
