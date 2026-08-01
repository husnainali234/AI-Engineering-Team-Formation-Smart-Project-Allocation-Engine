"""
Day 3 — Pydantic schemas (request/response contracts) for the CRUD + /import endpoints.

Naming convention used throughout:
    <Entity>Base    -> shared fields
    <Entity>Create  -> what the client sends to create one
    <Entity>Update  -> what the client sends to patch one (all fields optional)
    <Entity>Out     -> what the API returns (adds id + server-generated fields)

Kept intentionally flat/MVP (no nested skill objects on Intern yet) — that gets
layered on Day 4 once the Skill Matrix / embeddings logic needs it.
"""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ---------------------------------------------------------------------------
# Intern
# ---------------------------------------------------------------------------

class InternBase(BaseModel):
    full_name: str
    email: EmailStr
    technology_stack: Optional[str] = None
    github_url: Optional[str] = None
    github_contributions: int = 0
    case_study_performance: float = 0.0
    engineering_credits: int = 0
    attendance_pct: float = 100.0
    leadership_score: float = 0.0
    communication_score: float = 0.0
    is_available: bool = True
    project_interests: Optional[str] = None


class InternCreate(InternBase):
    pass


class InternUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    technology_stack: Optional[str] = None
    github_url: Optional[str] = None
    github_contributions: Optional[int] = None
    case_study_performance: Optional[float] = None
    engineering_credits: Optional[int] = None
    attendance_pct: Optional[float] = None
    leadership_score: Optional[float] = None
    communication_score: Optional[float] = None
    is_available: Optional[bool] = None
    project_interests: Optional[str] = None


class InternOut(InternBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

class ProjectBase(BaseModel):
    title: str
    description: Optional[str] = None
    required_tech_stack: Optional[str] = None
    difficulty_level: Literal["Easy", "Medium", "Hard"] = "Medium"


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    required_tech_stack: Optional[str] = None
    difficulty_level: Optional[Literal["Easy", "Medium", "Hard"]] = None


class ProjectOut(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


# ---------------------------------------------------------------------------
# Team + TeamMember
# ---------------------------------------------------------------------------

class TeamMemberBase(BaseModel):
    intern_id: int
    role: str = "Member"
    suggested_responsibility: Optional[str] = None


class TeamMemberCreate(TeamMemberBase):
    pass


class TeamMemberOut(TeamMemberBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int


class TeamBase(BaseModel):
    name: str
    project_id: Optional[int] = None
    compatibility_score: float = 0.0
    success_probability: float = 0.0
    risk_notes: Optional[str] = None


class TeamCreate(TeamBase):
    member_ids: list[int] = []   # convenience: create a team + members in one call


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    project_id: Optional[int] = None
    compatibility_score: Optional[float] = None
    success_probability: Optional[float] = None
    risk_notes: Optional[str] = None


class TeamOut(TeamBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    members: list[TeamMemberOut] = []


# ---------------------------------------------------------------------------
# /import
# ---------------------------------------------------------------------------

class ImportSummary(BaseModel):
    """Returned by POST /import — mirrors what a real portal-sync job would report."""
    source_format: Literal["csv", "json"]
    rows_received: int
    interns_created: int
    interns_updated: int
    rows_skipped: int
    errors: list[str] = []
    embedding_summary: Optional["EmbeddingBatchSummary"] = None


# ---------------------------------------------------------------------------
# Day 4 — Embeddings
# ---------------------------------------------------------------------------

class EmbeddingOut(BaseModel):
    """A single intern's embedding + the metadata needed to tell whether
    it's stale (embedding_updated_at / embedding_source_hash)."""
    intern_id: int
    dimensions: int
    embedding: list[float]
    embedding_updated_at: Optional[datetime] = None


class EmbeddingStatusOut(BaseModel):
    """Lighter-weight than EmbeddingOut — for listing embedding freshness
    across many interns without shipping 384 floats per row."""
    intern_id: int
    full_name: str
    has_embedding: bool
    embedding_updated_at: Optional[datetime] = None


class EmbeddingBatchSummary(BaseModel):
    total: int
    generated: int
    skipped_cached: int
    errors: list[str] = []


# ---------------------------------------------------------------------------
# Day 4 — Skill Matrix
# ---------------------------------------------------------------------------

class SkillHolderOut(BaseModel):
    intern_id: int
    full_name: str
    proficiency: Optional[int] = None   # None when only known via technology_stack text


class SkillMatrixRowOut(BaseModel):
    skill_name: str
    intern_count: int
    avg_proficiency: Optional[float] = None
    min_proficiency: Optional[int] = None
    max_proficiency: Optional[int] = None
    rated_intern_count: Optional[int] = None
    interns: list[SkillHolderOut] = []


class TeamSkillMatrixOut(BaseModel):
    team_id: int
    team_name: str
    member_count: int
    skills: list[SkillMatrixRowOut]


class TechnologyFrequencyOut(BaseModel):
    scope: str                    # "global" | "team:<id>"
    intern_count: int
    frequency: dict[str, int]


class ProficiencyAggregationOut(BaseModel):
    scope: str
    aggregation: dict[str, dict[str, float]]


# ---------------------------------------------------------------------------
# Day 6 — Matching
# ---------------------------------------------------------------------------

class MatchCandidateOut(BaseModel):
    intern_id: int
    full_name: str
    similarity_score: float
    diversity_score: float


class TeamDiversityOut(BaseModel):
    team_id: int
    team_name: str
    member_count: int
    diversity_score: float


# ---------------------------------------------------------------------------
# Day 6 — Compatibility
# ---------------------------------------------------------------------------

class CompatibilityComponentOut(BaseModel):
    raw_score: float
    weight: float
    contribution: float


class PairwiseCompatibilityOut(BaseModel):
    intern_a_id: int
    intern_b_id: int
    total_score: float
    components: dict[str, CompatibilityComponentOut]


class TeamCompatibilityOut(BaseModel):
    team_id: int
    team_name: str
    member_count: int
    average_score: float
    pairs: list[PairwiseCompatibilityOut]


# ---------------------------------------------------------------------------
# Day 6 — Recommendations (Matching + Compatibility combined)
# ---------------------------------------------------------------------------

class RecommendationOut(BaseModel):
    intern_id: int
    full_name: str
    similarity_score: float
    diversity_score: float
    compatibility_score: float
    blended_rank_score: float


# ---------------------------------------------------------------------------
# Day 7 — Leadership Detection
# ---------------------------------------------------------------------------

class LeadershipComponentOut(BaseModel):
    raw_score: float
    weight: float
    contribution: float


class LeadershipScoreOut(BaseModel):
    intern_id: int
    full_name: str
    total_score: float
    components: dict[str, LeadershipComponentOut]


class LeadershipRankingEntryOut(BaseModel):
    intern_id: int
    full_name: str
    total_score: float
    components: dict[str, LeadershipComponentOut]


class TeamLeadershipSuggestionOut(BaseModel):
    team_id: int
    team_name: str
    suggested_leader_intern_id: int
    suggested_leader_name: str
    ranking: list[LeadershipRankingEntryOut]


# ---------------------------------------------------------------------------
# Day 7 — Team Formation
# ---------------------------------------------------------------------------

class TeamFormationRequest(BaseModel):
    intern_ids: list[int] = Field(
        default=[],
        description="Candidate intern IDs to form teams from. Omit or leave empty to use the "
                    "default pool: available, unassigned interns that already have an embedding.",
    )
    team_size: int = Field(default=4, ge=1, description="Target number of members per team.")
    algorithm: Literal["kmeans", "agglomerative"] = Field(
        default="kmeans", description="Clustering algorithm used to find skill archetypes."
    )


class FormedTeamMemberOut(BaseModel):
    intern_id: int
    full_name: str
    role: Literal["Lead", "Member"]
    skill_archetype: int


class FormedTeamOut(BaseModel):
    id: Optional[int] = None            # set once /commit has persisted it
    name: Optional[str] = None
    team_index: Optional[int] = None
    members: list[FormedTeamMemberOut]
    suggested_leader_intern_id: int
    suggested_leader_name: str
    diversity_score: float


class TeamFormationResultOut(BaseModel):
    algorithm: Literal["kmeans", "agglomerative"]
    archetype_count: int
    teams: list[FormedTeamOut]
    unassigned_intern_ids: list[int]


# ---------------------------------------------------------------------------
# Day 8 — Project Recommendation
# ---------------------------------------------------------------------------

class ProjectFitOut(BaseModel):
    project_id: int
    title: str
    difficulty_level: Literal["Easy", "Medium", "Hard"]
    coverage_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    extra_skills: list[str]
    required_skill_count: int


class ProjectRecommendationsOut(BaseModel):
    team_id: int
    team_name: str
    team_skill_count: int
    recommendations: list[ProjectFitOut]


# ---------------------------------------------------------------------------
# Day 8 — Workload Distribution
# ---------------------------------------------------------------------------

class WorkloadAssignmentOut(BaseModel):
    intern_id: int
    full_name: str
    role: str   # mirrors TeamMember.role — "Lead"/"Member" in practice, but the
                # general CRUD /teams/{id}/members endpoint allows a freeform
                # label, so this stays untyped rather than a Literal.
    assigned_skills: list[str]
    suggested_responsibility: str


class WorkloadOut(BaseModel):
    team_id: int
    team_name: str
    project_id: int
    project_title: str
    assignments: list[WorkloadAssignmentOut]


# ---------------------------------------------------------------------------
# Day 9 — Success Probability
# ---------------------------------------------------------------------------

class SuccessFactorOut(BaseModel):
    feature: str
    value: float
    shap_value: float
    direction: Literal["increased", "decreased", "neutral"]


class ExplanationOut(BaseModel):
    """Day 11 — Explainable AI Layer. SHAP-derived breakdown of the
    success-probability prediction, plus mentor-readable text generated
    from it. base_value/shap_value are in the model's log-odds space (see
    app/services/explainability_service.py); reasons/summary are the
    plain-English translation of that, which is what dashboards render."""
    base_value: float
    factors: list[SuccessFactorOut]
    summary: str
    reasons: list[str]


class SuccessProbabilityOut(BaseModel):
    team_id: int
    team_name: str
    success_probability: float   # 0-100 (%)
    features: dict[str, float]   # team_balance, avg_attendance_pct, avg_feedback_score
    explanation: ExplanationOut


# ---------------------------------------------------------------------------
# Day 9 — Risk Analysis
# ---------------------------------------------------------------------------

class RiskOut(BaseModel):
    type: str
    severity: Literal["low", "medium", "high"]
    message: str


class RiskAnalysisOut(BaseModel):
    team_id: int
    team_name: str
    risks: list[RiskOut]


# ---------------------------------------------------------------------------
# Day 10 — Checkpoint 2: /recommend-teams (all engines wired together)
# ---------------------------------------------------------------------------

class RecommendedTeamOut(BaseModel):
    id: int
    name: str
    members: list[FormedTeamMemberOut]
    suggested_leader_intern_id: int
    suggested_leader_name: str
    diversity_score: float
    skill_matrix: list[SkillMatrixRowOut]
    compatibility_score: float
    project: Optional[ProjectFitOut] = None
    workload: list[WorkloadAssignmentOut] = []
    success_probability: float
    risks: list[RiskOut]
    overall_score: float
    explanation: ExplanationOut


class RecommendTeamsResultOut(BaseModel):
    algorithm: Literal["kmeans", "agglomerative"]
    archetype_count: int
    teams: list[RecommendedTeamOut]
    unassigned_intern_ids: list[int]


# ---------------------------------------------------------------------------
# Day 13 — Admin Analytics
# ---------------------------------------------------------------------------

class TeamAnalyticsSummaryOut(BaseModel):
    team_id: int
    team_name: str
    member_count: int
    compatibility_score: float
    success_probability: float
    project_title: Optional[str] = None
    risk_assessed: bool
    flagged_at_risk: bool


class CrossTeamAnalyticsOut(BaseModel):
    team_count: int
    avg_team_size: float
    size_distribution: dict[str, int]
    avg_compatibility_score: Optional[float] = None
    avg_success_probability: Optional[float] = None
    teams_with_project: int
    teams_without_project: int
    teams_assessed_for_risk: int
    teams_flagged_at_risk: int
    teams: list[TeamAnalyticsSummaryOut]


class ProjectSuccessRateOut(BaseModel):
    project_id: int
    title: str
    difficulty_level: Literal["Easy", "Medium", "Hard"]
    team_count: int
    avg_success_probability: Optional[float] = None
    avg_compatibility_score: Optional[float] = None


class ProjectSuccessRatesOut(BaseModel):
    project_count: int
    projects_without_teams: int
    projects: list[ProjectSuccessRateOut]


class ResourceUtilizationOut(BaseModel):
    total_interns: int
    assigned_count: int
    unassigned_count: int
    assigned_pct: float
    available_count: int
    unavailable_count: int
    available_and_unassigned_count: int
    with_embedding_count: int
    avg_attendance_pct: float
    avg_case_study_performance: float
    avg_engineering_credits: float


# ---------------------------------------------------------------------------
# Day 14 — Student Dashboard
# ---------------------------------------------------------------------------

class StudentSkillHighlightOut(BaseModel):
    skill_name: str
    proficiency: int


class StudentTeamOut(BaseModel):
    team_id: int
    team_name: str
    role: str
    compatibility_score: float
    success_probability: float
    project_title: Optional[str] = None
    suggested_responsibility: Optional[str] = None
    teammates: list[str] = []


class StudentDashboardOut(BaseModel):
    intern_id: int
    full_name: str
    is_available: bool
    strengths: list[str] = []
    top_skills: list[StudentSkillHighlightOut] = []
    team: Optional[StudentTeamOut] = None


# ---------------------------------------------------------------------------
# Day 16 — Bonus Features
# ---------------------------------------------------------------------------

class ChemistryComponentOut(BaseModel):
    raw_score: float
    weight: float
    contribution: float


class TeamChemistryOut(BaseModel):
    team_id: int
    team_name: str
    member_count: int
    chemistry_score: float
    label: Literal["Strong", "Workable", "Fragile"]
    components: dict[str, ChemistryComponentOut]
    flags: list[str] = []


class UnavailableMemberOut(BaseModel):
    intern_id: int
    full_name: str


class RebalanceNeededEntryOut(BaseModel):
    team_id: int
    team_name: str
    unavailable_members: list[UnavailableMemberOut]


class RebalanceNeededListOut(BaseModel):
    teams: list[RebalanceNeededEntryOut]


class RebalanceSwapOut(BaseModel):
    departing_intern_id: int
    departing_intern_name: str
    replacement_intern_id: Optional[int] = None
    replacement_intern_name: Optional[str] = None
    similarity_score: Optional[float] = None
    reason: str


class RebalancedTeamMemberOut(BaseModel):
    intern_id: int
    full_name: str
    role: str


class TeamRebalanceOut(BaseModel):
    team_id: int
    team_name: str
    swaps: list[RebalanceSwapOut]
    members: list[RebalancedTeamMemberOut]
    compatibility_score: float
    project: Optional[ProjectFitOut] = None
    success_probability: float
    risks: list[RiskOut]
    workload: list[WorkloadAssignmentOut] = []


# ---------------------------------------------------------------------------
# Gap-fix (post-Day-20) — Engineering Knowledge Graph
# ---------------------------------------------------------------------------

class KnowledgeGraphSummaryOut(BaseModel):
    node_count: int
    edge_count: int
    nodes_by_type: dict[str, int]
    edges_by_relation: dict[str, int]


class SkillGraphInternOut(BaseModel):
    intern_id: int
    proficiency: int


class PastCollaborationOut(BaseModel):
    past_team_name: Optional[str] = None
    outcome_rating: Optional[float] = None


class RecommendedCollaboratorOut(BaseModel):
    intern_id: int
    shared_skills: list[str]
    shared_skill_count: int
    past_collaboration: Optional[PastCollaborationOut] = None
    score: float


class KnowledgeGraphPathHopOut(BaseModel):
    node: str
    type: str
    name: str


class KnowledgeGraphPathOut(BaseModel):
    found: bool
    length: Optional[int] = None
    path: list[KnowledgeGraphPathHopOut] = []
