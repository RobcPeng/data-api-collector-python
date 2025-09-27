import json
from numpy import integer
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    FAILED = "failed"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    
class ResourceType(str, Enum):
    DEVELOPER = "developer"
    DATABASE = "database"
    API_ENDPOINT = "api_endpoint"
    FILE_SYSTEM = "file_system"
    COMPUTE = "compute"
    NETWORK = "network"

class DataType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    JSON = "json"
    FILE = "file"
    URL = "url"
    DATABASE_RECORD = "database_record"

class InputContract(BaseModel):
    """Defines required inputs for a task"""
    name: str
    data_type: DataType
    required: bool = True
    validation_rules: List[str] = Field(default_factory=list)
    example_value: Optional[str] = None
    description: str = ""

class OutputContract(BaseModel):
    """Defines expected outputs from a task"""
    name: str
    data_type: DataType
    validation_rules: List[str] = Field(default_factory=list)
    example_value: Optional[str] = None
    description: str = ""
    
class TaskContract(BaseModel):
    """Complete input/output contract for a task"""
    task_id: str
    inputs: List[InputContract] = Field(default_factory=list)
    outputs: List[OutputContract] = Field(default_factory=list)
    preconditions: List[str] = Field(default_factory=list)
    postconditions: List[str] = Field(default_factory=list)
    side_effects: List[str] = Field(default_factory=list)

class Task(BaseModel):
    id: str
    name: str
    description: str
    duration_hours: int = Field(gt=0)
    dependencies: List[str] = Field(default_factory=list)
    required_resources: List[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    contract: TaskContract
    generated_code: Optional[str] = None
    execution_environment: str = "python"

class Resource(BaseModel):
    id: str
    name: str
    resource_type: ResourceType
    available: bool = True
    capacity: int = Field(default=1, gt=0)
    properties: Dict[str, Any] = Field(default_factory=dict)

class ExecutionContext(BaseModel):
    """Runtime context for task execution"""
    task_id: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    execution_trace: List[str] = Field(default_factory=list)
    resource_state: Dict[str, Any] = Field(default_factory=dict)

class PlanningState(BaseModel):
    tasks: Dict[str, Task]
    resources: Dict[str, Resource]
    completed_tasks: List[str] = Field(default_factory=list)
    failed_tasks: List[str] = Field(default_factory=list)
    current_time: int = Field(default=0, ge=0)
    available_resources: Optional[List[str]] = None
    execution_contexts: Dict[str, ExecutionContext] = Field(default_factory=dict)
    global_state: Dict[str, Any] = Field(default_factory=dict)
    
    def model_post_init(self, __context: Any) -> None:
        if self.available_resources is None:
            self.available_resources = [r.id for r in self.resources.values() if r.available]

class ValidationResult(BaseModel):
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    execution_trace: List[str] = Field(default_factory=list)
    val_output: str = ""
    contract_violations: List[str] = Field(default_factory=list)    
    