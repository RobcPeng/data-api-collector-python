from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class IntegrationNeed(BaseModel):
    system: str = Field(..., description="System to integrate with")
    type: Literal["api", "database", "file-transfer", "messaging", "other"] = Field(
        ..., description="Type of integration"
    )
    description: str = Field(..., description="Description of integration requirement")
    data_flow: Optional[Literal["inbound", "outbound", "bidirectional"]] = Field(
        None, description="Direction of data flow"
    )
    critical: Optional[bool] = Field(
        None, description="Is this integration critical"
    )
    complexity: Optional[Literal["high", "medium", "low"]] = Field(
        None, description="Complexity level (for epics)"
    )
    data_elements: Optional[List[str]] = Field(
        default_factory=list, 
        description="Specific data fields or objects to be exchanged (for user stories)"
    )


class DevelopmentConsideration(BaseModel):
    category: Literal[
        "technical", "architectural", "security", 
        "performance", "scalability", "maintainability", "testing"
    ] = Field(..., description="Category of development consideration")
    consideration: str = Field(..., description="The specific consideration")
    impact: Literal["high", "medium", "low"] = Field(..., description="Impact level")
    mitigation: Optional[str] = Field(None, description="Mitigation strategy")
    effort_impact: Optional[str] = Field(
        None, description="How this affects development effort (for epics)"
    )
    implementation_notes: Optional[str] = Field(
        None, description="Specific implementation guidance (for user stories)"
    )


class OpenQuestion(BaseModel):
    question: str = Field(..., description="The question that needs to be answered")
    category: Literal[
        "business", "technical", "user-experience", 
        "integration", "compliance", "other"
    ] = Field(..., description="Category of the question")
    priority: Literal["blocking", "high", "medium", "low"] = Field(
        ..., description="Priority level of the question"
    )
    stakeholder: Optional[str] = Field(
        None, description="Who should answer this question"
    )
    context: Optional[str] = Field(
        None, description="Additional context about the question"
    )
    blocks_development: Optional[bool] = Field(
        None, description="Whether this question must be resolved before development starts (for epics)"
    )
    affects_acceptance_criteria: Optional[bool] = Field(
        None, description="Whether answering this question will change acceptance criteria (for user stories)"
    )


class Epic(BaseModel):
    id: Optional[str] = Field(None, description="Unique identifier for referencing")
    title: str = Field(..., description="Epic title")
    description: str = Field(..., description="Epic description")
    business_value: str = Field(..., description="Business value delivered by this epic")
    priority: Optional[Literal["high", "medium", "low"]] = Field(
        None, description="Epic priority"
    )
    estimated_effort: Optional[str] = Field(None, description="Effort estimation")
    dependencies: List[str] = Field(
        default_factory=list, description="Dependencies on other epics or components"
    )
    integration_needs: List[IntegrationNeed] = Field(
        default_factory=list, 
        description="Integration requirements specific to this epic"
    )
    dev_considerations: List[DevelopmentConsideration] = Field(
        default_factory=list,
        description="Development considerations specific to this epic"
    )
    open_questions: List[OpenQuestion] = Field(
        default_factory=list,
        description="Questions specific to this epic"
    )


class UserStory(BaseModel):
    id: Optional[str] = Field(None, description="Story ID if mentioned")
    title: str = Field(..., description="Title of the user story")
    user_type: str = Field(..., description="The user persona (As a...)")
    goal: str = Field(..., description="What the user wants (I want...)")
    benefit: str = Field(..., description="Why they want it (So that...)")
    priority: Optional[Literal["high", "medium", "low"]] = Field(
        None, description="Story priority"
    )
    story_points: Optional[int] = Field(None, description="Story point estimation")
    epic_id: Optional[str] = Field(None, description="ID of the epic this belongs to")
    epic_title: Optional[str] = Field(
        None, description="Title of the epic this belongs to"
    )
    acceptance_criteria: List[str] = Field(
        default_factory=list, description="Specific testable criteria"
    )
    integration_needs: List[IntegrationNeed] = Field(
        default_factory=list, 
        description="Integration requirements specific to this user story"
    )
    dev_considerations: List[DevelopmentConsideration] = Field(
        default_factory=list,
        description="Development considerations specific to this user story"
    )
    open_questions: List[OpenQuestion] = Field(
        default_factory=list,
        description="Questions specific to this user story"
    )


class EpicsAndUserStoriesResponse(BaseModel):
    epics: List[Epic] = Field(..., description="List of generated epics")
    user_stories: List[UserStory] = Field(
        default_factory=list, description="List of generated user stories"
    )
