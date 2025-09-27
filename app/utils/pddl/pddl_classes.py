import json
from numpy import integer
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum


class TaskStatus(str, Enum):
    # Initial states
    PENDING = "pending"
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    READY = "ready"
    
    # Active states
    IN_PROGRESS = "in_progress"
    RUNNING = "running"
    PROCESSING = "processing"
    EXECUTING = "executing"
    
    # Waiting states
    BLOCKED = "blocked"
    WAITING = "waiting"
    PAUSED = "paused"
    SUSPENDED = "suspended"
    ON_HOLD = "on_hold"
    
    # Completion states
    COMPLETED = "completed"
    SUCCESS = "success"
    FINISHED = "finished"
    
    # Failure states
    FAILED = "failed"
    ERROR = "error"
    TIMEOUT = "timeout"
    ABORTED = "aborted"
    CANCELLED = "cancelled"
    
    # Review states
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    
    # Retry states
    RETRYING = "retrying"
    RETRY_PENDING = "retry_pending"


class ResourceType(str, Enum):
    # Human resources
    DEVELOPER = "developer"
    QA = "qa"
    DESIGNER = "designer"
    PRODUCT_MANAGER = "product_manager"
    DEVOPS_ENGINEER = "devops_engineer"
    DATA_SCIENTIST = "data_scientist"
    SECURITY_ANALYST = "security_analyst"
    BUSINESS_ANALYST = "business_analyst"
    
    # Infrastructure resources
    DATABASE = "database"
    CACHE = "cache"
    MESSAGE_QUEUE = "message_queue"
    LOAD_BALANCER = "load_balancer"
    CDN = "cdn"
    STORAGE = "storage"
    BACKUP = "backup"
    
    # Compute resources
    COMPUTE = "compute"
    CPU = "cpu"
    GPU = "gpu"
    MEMORY = "memory"
    CONTAINER = "container"
    VIRTUAL_MACHINE = "virtual_machine"
    SERVERLESS_FUNCTION = "serverless_function"
    
    # Network resources
    NETWORK = "network"
    BANDWIDTH = "bandwidth"
    VPN = "vpn"
    FIREWALL = "firewall"
    DNS = "dns"
    
    # Application resources
    API_ENDPOINT = "api_endpoint"
    MICROSERVICE = "microservice"
    WEB_SERVER = "web_server"
    APPLICATION_SERVER = "application_server"
    
    # File and data resources
    FILE_SYSTEM = "file_system"
    OBJECT_STORAGE = "object_storage"
    DATA_WAREHOUSE = "data_warehouse"
    DATA_LAKE = "data_lake"
    
    # External resources
    THIRD_PARTY_API = "third_party_api"
    EXTERNAL_SERVICE = "external_service"
    PAYMENT_GATEWAY = "payment_gateway"
    
    # Security resources
    SSL_CERTIFICATE = "ssl_certificate"
    SECRET_MANAGER = "secret_manager"
    AUTHENTICATION_SERVICE = "authentication_service"
    
    # Monitoring resources
    MONITORING_SYSTEM = "monitoring_system"
    LOGGING_SERVICE = "logging_service"
    ALERTING_SYSTEM = "alerting_system"


class DataType(str, Enum):
    # Primitive types
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    NULL = "null"
    
    # Date and time types
    DATE = "date"
    TIME = "time"
    DATE_TIME = "datetime"
    TIMESTAMP = "timestamp"
    TIMEZONE = "timezone"
    DURATION = "duration"
    
    # Structured data types
    JSON = "json"
    XML = "xml"
    YAML = "yaml"
    CSV = "csv"
    ARRAY = "array"
    LIST = "list"
    DICTIONARY = "dictionary"
    OBJECT = "object"
    
    # File types
    FILE = "file"
    BINARY = "binary"
    TEXT_FILE = "text_file"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    
    # Document formats
    PDF = "pdf"
    WORD_DOC = "word_doc"
    EXCEL = "excel"
    POWERPOINT = "powerpoint"
    HTML = "html"
    MARKDOWN = "markdown"
    
    # Network and web types
    URL = "url"
    EMAIL = "email"
    IP_ADDRESS = "ip_address"
    MAC_ADDRESS = "mac_address"
    UUID = "uuid"
    
    # Database types
    DATABASE_RECORD = "database_record"
    PRIMARY_KEY = "primary_key"
    FOREIGN_KEY = "foreign_key"
    BLOB = "blob"
    CLOB = "clob"
    
    # Geographic and location types
    COORDINATE = "coordinate"
    LATITUDE = "latitude"
    LONGITUDE = "longitude"
    ADDRESS = "address"
    POSTAL_CODE = "postal_code"
    
    # Financial types
    CURRENCY = "currency"
    PRICE = "price"
    PERCENTAGE = "percentage"
    
    # Security types
    PASSWORD = "password"
    TOKEN = "token"
    API_KEY = "api_key"
    ENCRYPTED_DATA = "encrypted_data"
    HASH = "hash"
    
    # Communication types
    PHONE_NUMBER = "phone_number"
    MESSAGE = "message"
    NOTIFICATION = "notification"
    
    # Measurement types
    METRIC = "metric"
    UNIT_OF_MEASURE = "unit_of_measure"
    QUANTITY = "quantity"
    
    # Custom types
    REGEX_PATTERN = "regex_pattern"
    COLOR_CODE = "color_code"
    VERSION_NUMBER = "version_number"
    STATUS_CODE = "status_code"

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
    
    
    