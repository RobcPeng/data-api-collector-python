from typing import List, Optional, Literal, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


# Enums for better type safety
class RequirementType(str, Enum):
    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non_functional"
    BUSINESS_RULE = "business_rule"
    DATA_REQUIREMENT = "data_requirement"
    INTEGRATION = "integration"
    COMPLIANCE = "compliance"
    USER_INTERFACE = "user_interface"


class RequirementStatus(str, Enum):
    IDENTIFIED = "identified"
    ANALYZED = "analyzed" 
    APPROVED = "approved"
    IMPLEMENTED = "implemented"
    TESTED = "tested"
    DEPLOYED = "deployed"


class CodeMigrationStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_ANALYSIS = "in_analysis"
    MAPPED = "mapped"
    MIGRATED = "migrated"
    TESTED = "tested"
    DEPLOYED = "deployed"


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Complexity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


# Core Models
class BusinessLogicRule(BaseModel):
    id: str = Field(..., description="Unique identifier for the business rule")
    name: str = Field(..., description="Business rule name")
    description: str = Field(..., description="Detailed description of the rule")
    category: str = Field(..., description="Business domain category")
    conditions: List[str] = Field(default_factory=list, description="When conditions apply")
    actions: List[str] = Field(default_factory=list, description="What actions are taken")
    exceptions: List[str] = Field(default_factory=list, description="Exception cases")
    priority: Priority = Field(default=Priority.MEDIUM, description="Business priority")
    complexity: Complexity = Field(default=Complexity.MEDIUM, description="Implementation complexity")
    stakeholders: List[str] = Field(default_factory=list, description="Business stakeholders")
    source_system: Optional[str] = Field(None, description="Originating system")
    compliance_requirements: List[str] = Field(default_factory=list, description="Regulatory compliance needs")
    data_dependencies: List[str] = Field(default_factory=list, description="Required data elements")


class LegacyCodeComponent(BaseModel):
    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Component name")
    file_path: str = Field(..., description="File path in legacy system")
    language: str = Field(..., description="Programming language")
    lines_of_code: Optional[int] = Field(None, description="Estimated lines of code")
    functions: List[str] = Field(default_factory=list, description="Key functions/methods")
    dependencies: List[str] = Field(default_factory=list, description="Dependencies on other components")
    business_logic_rules: List[str] = Field(default_factory=list, description="Business rule IDs this implements")
    migration_status: CodeMigrationStatus = Field(default=CodeMigrationStatus.NOT_STARTED)
    migration_complexity: Complexity = Field(default=Complexity.MEDIUM)
    migration_effort_days: Optional[float] = Field(None, description="Estimated migration effort in days")
    technical_debt_level: Literal["low", "medium", "high", "critical"] = Field(
        default="medium", description="Level of technical debt"
    )
    last_modified: Optional[datetime] = Field(None, description="Last modification date")
    maintainer: Optional[str] = Field(None, description="Current maintainer")


class Requirement(BaseModel):
    id: str = Field(..., description="Unique requirement identifier")
    title: str = Field(..., description="Requirement title")
    description: str = Field(..., description="Detailed requirement description")
    type: RequirementType = Field(..., description="Type of requirement")
    status: RequirementStatus = Field(default=RequirementStatus.IDENTIFIED)
    priority: Priority = Field(default=Priority.MEDIUM)
    complexity: Complexity = Field(default=Complexity.MEDIUM)
    business_value: str = Field(..., description="Business value this requirement provides")
    acceptance_criteria: List[str] = Field(default_factory=list, description="Acceptance criteria")
    business_logic_rules: List[str] = Field(default_factory=list, description="Related business rule IDs")
    legacy_components: List[str] = Field(default_factory=list, description="Legacy component IDs")
    stakeholders: List[str] = Field(default_factory=list, description="Requirement stakeholders")
    source: str = Field(..., description="Source of the requirement (interview, documentation, etc.)")
    rationale: Optional[str] = Field(None, description="Why this requirement exists")
    assumptions: List[str] = Field(default_factory=list, description="Assumptions made")
    constraints: List[str] = Field(default_factory=list, description="Constraints or limitations")
    risks: List[str] = Field(default_factory=list, description="Associated risks")


class DataMapping(BaseModel):
    id: str = Field(..., description="Unique mapping identifier")
    source_system: str = Field(..., description="Source system name")
    source_field: str = Field(..., description="Source field/column name")
    source_type: str = Field(..., description="Source data type")
    target_system: str = Field(..., description="Target system name")
    target_field: str = Field(..., description="Target field/column name") 
    target_type: str = Field(..., description="Target data type")
    transformation_rules: List[str] = Field(default_factory=list, description="Data transformation rules")
    validation_rules: List[str] = Field(default_factory=list, description="Data validation rules")
    business_logic_rules: List[str] = Field(default_factory=list, description="Related business rule IDs")
    migration_complexity: Complexity = Field(default=Complexity.MEDIUM)
    data_volume: Optional[str] = Field(None, description="Expected data volume")
    quality_concerns: List[str] = Field(default_factory=list, description="Data quality issues")


class Traceability(BaseModel):
    id: str = Field(..., description="Traceability link identifier")
    from_type: Literal["requirement", "business_rule", "legacy_component", "user_story", "epic"] = Field(
        ..., description="Source artifact type"
    )
    from_id: str = Field(..., description="Source artifact ID")
    to_type: Literal["requirement", "business_rule", "legacy_component", "user_story", "epic"] = Field(
        ..., description="Target artifact type"
    )
    to_id: str = Field(..., description="Target artifact ID")
    relationship: Literal["implements", "depends_on", "derives_from", "tests", "replaces", "enhances"] = Field(
        ..., description="Type of relationship"
    )
    confidence: Literal["high", "medium", "low"] = Field(
        default="medium", description="Confidence in this relationship"
    )
    notes: Optional[str] = Field(None, description="Additional notes about the relationship")


class GapAnalysis(BaseModel):
    id: str = Field(..., description="Gap analysis identifier")
    title: str = Field(..., description="Gap analysis title")
    description: str = Field(..., description="Description of the gap")
    gap_type: Literal["functionality", "performance", "security", "compliance", "usability", "integration"] = Field(
        ..., description="Type of gap identified"
    )
    current_state: str = Field(..., description="Current state description")
    desired_state: str = Field(..., description="Desired future state")
    impact: Literal["critical", "high", "medium", "low"] = Field(
        default="medium", description="Impact of not addressing the gap"
    )
    effort_to_close: Complexity = Field(default=Complexity.MEDIUM, description="Effort to close the gap")
    affected_requirements: List[str] = Field(default_factory=list, description="Affected requirement IDs")
    affected_components: List[str] = Field(default_factory=list, description="Affected legacy component IDs")
    proposed_solutions: List[str] = Field(default_factory=list, description="Proposed solutions")
    risks_if_not_addressed: List[str] = Field(default_factory=list, description="Risks if gap not closed")


# Aggregation Models
class RequirementsPackage(BaseModel):
    id: str = Field(..., description="Package identifier")
    name: str = Field(..., description="Package name")
    description: str = Field(..., description="Package description")
    business_logic_rules: List[BusinessLogicRule] = Field(default_factory=list)
    legacy_components: List[LegacyCodeComponent] = Field(default_factory=list)
    requirements: List[Requirement] = Field(default_factory=list)
    data_mappings: List[DataMapping] = Field(default_factory=list)
    traceability_links: List[Traceability] = Field(default_factory=list)
    gap_analyses: List[GapAnalysis] = Field(default_factory=list)
    created_date: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)
    version: str = Field(default="1.0", description="Package version")
    stakeholders: List[str] = Field(default_factory=list)
    project_phase: Literal["discovery", "analysis", "design", "implementation", "testing", "deployment"] = Field(
        default="discovery", description="Current project phase"
    )


# Epic and User Story Extensions for Traceability
class Epic(BaseModel):
    id: str = Field(..., description="Epic identifier")
    title: str = Field(..., description="Epic title")
    description: str = Field(..., description="Epic description")
    business_value: str = Field(..., description="Business value")
    priority: Priority = Field(default=Priority.MEDIUM)
    status: Literal["backlog", "in_progress", "done"] = Field(default="backlog")
    requirements: List[str] = Field(default_factory=list, description="Requirement IDs")
    business_logic_rules: List[str] = Field(default_factory=list, description="Business rule IDs")
    estimated_effort_days: Optional[float] = Field(None, description="Effort estimation")
    dependencies: List[str] = Field(default_factory=list, description="Dependent epic IDs")


class UserStory(BaseModel):
    id: str = Field(..., description="User story identifier")
    title: str = Field(..., description="User story title")
    description: str = Field(..., description="User story description")
    user_type: str = Field(..., description="User persona")
    goal: str = Field(..., description="What user wants")
    benefit: str = Field(..., description="Why they want it")
    epic_id: Optional[str] = Field(None, description="Parent epic ID")
    priority: Priority = Field(default=Priority.MEDIUM)
    story_points: Optional[int] = Field(None, description="Story point estimation")
    acceptance_criteria: List[str] = Field(default_factory=list)
    requirements: List[str] = Field(default_factory=list, description="Requirement IDs")
    business_logic_rules: List[str] = Field(default_factory=list, description="Business rule IDs")
    legacy_components: List[str] = Field(default_factory=list, description="Legacy component IDs")
    status: Literal["backlog", "in_progress", "testing", "done"] = Field(default="backlog")


# Analysis and Reporting Models
class RequirementCoverage(BaseModel):
    requirement_id: str
    covered_by_user_stories: List[str] = Field(default_factory=list)
    covered_by_epics: List[str] = Field(default_factory=list)
    coverage_percentage: float = Field(default=0.0, description="Percentage covered")
    gaps: List[str] = Field(default_factory=list, description="Coverage gaps")


class MigrationProgress(BaseModel):
    total_components: int
    components_by_status: Dict[CodeMigrationStatus, int] = Field(default_factory=dict)
    total_estimated_days: float = Field(default=0.0)
    completed_days: float = Field(default=0.0)
    progress_percentage: float = Field(default=0.0)
    at_risk_components: List[str] = Field(default_factory=list)
    blocked_components: List[str] = Field(default_factory=list)


# Utility Functions
def create_traceability_link(
    from_type: str, from_id: str, 
    to_type: str, to_id: str, 
    relationship: str,
    confidence: str = "medium",
    notes: Optional[str] = None
) -> Traceability:
    """Helper function to create traceability links."""
    return Traceability(
        id=f"{from_type}_{from_id}_to_{to_type}_{to_id}",
        from_type=from_type,
        from_id=from_id,
        to_type=to_type,
        to_id=to_id,
        relationship=relationship,
        confidence=confidence,
        notes=notes
    )


def calculate_requirement_coverage(
    requirements: List[Requirement],
    user_stories: List[UserStory],
    epics: List[Epic]
) -> List[RequirementCoverage]:
    """Calculate coverage of requirements by user stories and epics."""
    coverage_list = []
    
    for req in requirements:
        coverage = RequirementCoverage(requirement_id=req.id)
        
        # Find user stories covering this requirement
        for story in user_stories:
            if req.id in story.requirements:
                coverage.covered_by_user_stories.append(story.id)
        
        # Find epics covering this requirement  
        for epic in epics:
            if req.id in epic.requirements:
                coverage.covered_by_epics.append(epic.id)
        
        # Calculate coverage percentage (simple heuristic)
        total_coverage_items = len(coverage.covered_by_user_stories) + len(coverage.covered_by_epics)
        coverage.coverage_percentage = min(100.0, total_coverage_items * 25.0)  # Rough estimate
        
        if coverage.coverage_percentage < 100.0:
            coverage.gaps.append(f"Only {coverage.coverage_percentage}% covered")
        
        coverage_list.append(coverage)
    
    return coverage_list