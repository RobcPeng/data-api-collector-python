from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class Position(BaseModel):
    x: float = Field(..., description="X coordinate")
    y: float = Field(..., description="Y coordinate")


class Arrows(BaseModel):
    to: dict = Field(default_factory=lambda: {"enabled": True})


class Node(BaseModel):
    id: str = Field(..., description="Unique node identifier")
    label: str = Field(..., description="Node label/name")
    group: Literal["task", "start_event", "end_event", "gateway", "data_object"] = Field(
        ..., description="Node type category"
    )
    x: Optional[float] = Field(None, description="X position")
    y: Optional[float] = Field(None, description="Y position")
    elementType: Optional[str] = Field(None, description="Specific element type")
    complexity: Optional[Literal["low", "medium", "high"]] = Field(
        None, description="Complexity level"
    )
    effort: Optional[float] = Field(None, description="Effort estimation")
    lane: Optional[str] = Field(None, description="Swimming lane assignment")
    description: str = Field(..., description="Node description")


class Edge(BaseModel):
    id: str = Field(..., description="Unique edge identifier")
    from_node: str = Field(..., alias="from", description="Source node ID")
    to_node: str = Field(..., alias="to", description="Target node ID")
    label: Optional[str] = Field(None, description="Edge label")
    flowType: Optional[str] = Field(None, description="Type of flow")
    condition: Optional[str] = Field(None, description="Condition for flow")
    arrows: Optional[Arrows] = Field(default_factory=Arrows, description="Arrow configuration")


class Element(BaseModel):
    id: str = Field(..., description="Unique element identifier")
    nodeId: Optional[str] = Field(None, description="Corresponding node ID")
    type: str = Field(..., description="Element type")
    label: str = Field(..., description="Element label")
    position: Position = Field(..., description="Element position")
    lane: Optional[str] = Field(None, description="Lane assignment")
    complexity: Optional[str] = Field(None, description="Complexity level")
    effort: Optional[float] = Field(None, description="Effort estimation")
    stakeholders: List[str] = Field(default_factory=list, description="Involved stakeholders")
    dependencies: List[str] = Field(default_factory=list, description="Dependencies")
    businessValue: Optional[str] = Field(None, description="Business value provided")


class Flow(BaseModel):
    id: str = Field(..., description="Unique flow identifier")
    edgeId: Optional[str] = Field(None, description="Corresponding edge ID")
    from_node: str = Field(..., alias="from", description="Source node")
    to_node: str = Field(..., alias="to", description="Target node")
    label: Optional[str] = Field(None, description="Flow label")
    type: Optional[str] = Field(None, description="Flow type")
    condition: Optional[str] = Field(None, description="Flow condition")
    dataNeeds: List[str] = Field(default_factory=list, description="Data requirements")
    integrations: List[str] = Field(default_factory=list, description="Required integrations")


class Lane(BaseModel):
    id: str = Field(..., description="Unique lane identifier")
    name: str = Field(..., description="Lane name")
    role: Optional[str] = Field(None, description="Role responsible for lane")
    skills: List[str] = Field(default_factory=list, description="Required skills")
    systems: List[str] = Field(default_factory=list, description="Systems used")


class Metadata(BaseModel):
    processName: Optional[str] = Field(None, description="Process name")
    processType: Optional[str] = Field(None, description="Process type")
    totalEffort: Optional[float] = Field(None, description="Total effort estimation")
    stakeholders: List[str] = Field(default_factory=list, description="All stakeholders")
    objectives: List[str] = Field(default_factory=list, description="Process objectives")
    risks: List[str] = Field(default_factory=list, description="Identified risks")


class ProcessData(BaseModel):
    nodes: List[Node] = Field(..., description="All process nodes")
    edges: List[Edge] = Field(..., description="All process edges")
    elements: List[Element] = Field(..., description="All process elements")
    flows: List[Flow] = Field(..., description="All process flows")
    lanes: List[Lane] = Field(default_factory=list, description="Process lanes")
    metadata: Optional[Metadata] = Field(None, description="Process metadata")

