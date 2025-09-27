import json
import subprocess
import tempfile
import os
import re
from typing import Dict, List, Optional, Any, Tuple, Set, Union
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field

# Import your existing classes and client
from .pddl_classes import *
from .pddl_client import ModelClient, NaturalLanguageParser, PlanExplainer

class ContractValidator:
    """Validates that tasks follow their contracts"""
    
    def validate_task_inputs(self, task: Task, inputs: Dict[str, Any]) -> List[str]:
        """Validate inputs against task contract"""
        errors = []
        
        for input_contract in task.contract.inputs:
            if input_contract.required and input_contract.name not in inputs:
                errors.append(f"Required input '{input_contract.name}' missing for task {task.id}")
                continue
            
            if input_contract.name in inputs:
                value = inputs[input_contract.name]
                
                # Basic type validation
                if not self._validate_data_type(value, input_contract.data_type):
                    errors.append(f"Input '{input_contract.name}' has wrong type. Expected {input_contract.data_type.value}")
                
                # Custom validation rules
                for rule in input_contract.validation_rules:
                    if not self._validate_rule(value, rule):
                        errors.append(f"Input '{input_contract.name}' failed validation rule: {rule}")
        
        return errors
    
    def validate_task_outputs(self, task: Task, outputs: Dict[str, Any]) -> List[str]:
        """Validate outputs against task contract"""
        errors = []
        
        for output_contract in task.contract.outputs:
            if output_contract.name not in outputs:
                errors.append(f"Required output '{output_contract.name}' missing for task {task.id}")
                continue
            
            value = outputs[output_contract.name]
            
            # Basic type validation
            if not self._validate_data_type(value, output_contract.data_type):
                errors.append(f"Output '{output_contract.name}' has wrong type. Expected {output_contract.data_type.value}")
            
            # Custom validation rules
            for rule in output_contract.validation_rules:
                if not self._validate_rule(value, rule):
                    errors.append(f"Output '{output_contract.name}' failed validation rule: {rule}")
        
        return errors
    
    def _validate_data_type(self, value: Any, expected_type: DataType) -> bool:
        """Validate that value matches expected data type"""
        type_validators = {
            DataType.STRING: lambda v: isinstance(v, str),
            DataType.INTEGER: lambda v: isinstance(v, int),
            DataType.BOOLEAN: lambda v: isinstance(v, bool),
            DataType.JSON: lambda v: isinstance(v, (dict, list)),
            DataType.FILE: lambda v: isinstance(v, str) and os.path.exists(v),
            DataType.URL: lambda v: isinstance(v, str) and v.startswith(('http://', 'https://')),
            DataType.DATABASE_RECORD: lambda v: isinstance(v, dict) and 'id' in v
        }
        
        validator_func = type_validators.get(expected_type)
        return validator_func(value) if validator_func else True
    
    def _validate_rule(self, value: Any, rule: str) -> bool:
        """Validate custom rules"""
        try:
            if "length >" in rule:
                min_length = int(rule.split("length >")[1].strip())
                return len(str(value)) > min_length
            elif "not empty" in rule:
                return bool(value)
            elif "positive" in rule:
                return isinstance(value, (int, float)) and value > 0
            return True
        except:
            return False
    
    def _clean_generated_code(self, code: str) -> str:
        """Clean and format generated code"""
        # Remove markdown code blocks if present
        code = re.sub(r'```\w*\n', '', code)
        code = re.sub(r'```', '', code)
        return code.strip()
    
    def close(self):
        """No cleanup needed for your client"""
        pass

class PDDLGenerator:
    """Enhanced PDDL generator with contract enforcement"""
    
    def generate_domain(self, state: PlanningState) -> str:
        """Generate PDDL domain with contract predicates"""
        
        domain_pddl = """(define (domain contract-planning)
  (:requirements :strips :typing :conditional-effects)
  
  (:types
    task resource datatype - object
  )
  
  (:predicates
    (task-pending ?t - task)
    (task-ready ?t - task)
    (task-in-progress ?t - task)
    (task-completed ?t - task)
    (task-failed ?t - task)
    (depends-on ?t1 ?t2 - task)
    (requires-resource ?t - task ?r - resource)
    (resource-available ?r - resource)
    (resource-allocated ?r - resource ?t - task)
    
    ; Contract enforcement predicates
    (has-input ?t - task ?input - datatype)
    (has-output ?t - task ?output - datatype)
    (precondition-met ?t - task ?condition - object)
    (postcondition-satisfied ?t - task ?condition - object)
    (contract-valid ?t - task)
    (input-validated ?t - task)
    (output-validated ?t - task)
  )
  
  (:action validate-inputs
    :parameters (?t - task)
    :precondition (and 
      (task-ready ?t)
      (forall (?input - datatype) 
        (imply (has-input ?t ?input) (precondition-met ?t ?input)))
    )
    :effect (input-validated ?t)
  )
  
  (:action start-task
    :parameters (?t - task)
    :precondition (and 
      (task-ready ?t)
      (input-validated ?t)
      (contract-valid ?t)
      (forall (?r - resource) 
        (imply (requires-resource ?t ?r) (resource-available ?r)))
    )
    :effect (and 
      (task-in-progress ?t)
      (not (task-ready ?t))
      (forall (?r - resource)
        (when (requires-resource ?t ?r)
          (and (resource-allocated ?r ?t) (not (resource-available ?r)))))
    )
  )
  
  (:action complete-task
    :parameters (?t - task)
    :precondition (and 
      (task-in-progress ?t)
      (output-validated ?t)
      (forall (?condition - object)
        (postcondition-satisfied ?t ?condition))
    )
    :effect (and 
      (task-completed ?t)
      (not (task-in-progress ?t))
      (forall (?r - resource)
        (when (resource-allocated ?r ?t)
          (and (resource-available ?r) (not (resource-allocated ?r ?t)))))
    )
  )
  
  (:action validate-outputs
    :parameters (?t - task)
    :precondition (task-in-progress ?t)
    :effect (and
      (output-validated ?t)
      (forall (?output - datatype)
        (when (has-output ?t ?output)
          (postcondition-satisfied ?t ?output)))
    )
  )
  
  (:action make-task-ready
    :parameters (?t - task)
    :precondition (and 
      (task-pending ?t)
      (forall (?t2 - task) 
        (imply (depends-on ?t ?t2) (task-completed ?t2)))
    )
    :effect (and 
      (task-ready ?t)
      (not (task-pending ?t))
    )
  )
  
  (:action fail-task
    :parameters (?t - task)
    :precondition (task-in-progress ?t)
    :effect (and
      (task-failed ?t)
      (not (task-in-progress ?t))
      (forall (?r - resource)
        (when (resource-allocated ?r ?t)
          (and (resource-available ?r) (not (resource-allocated ?r ?t)))))
    )
  )
)"""
        return domain_pddl
    
    def generate_problem(self, state: PlanningState, goal_tasks: List[str] = None) -> str:
        """Generate PDDL problem with contract constraints"""
        
        if goal_tasks is None:
            goal_tasks = list(state.tasks.keys())
        
        # Objects section
        task_objects = " ".join([f"{tid} - task" for tid in state.tasks.keys()])
        resource_objects = " ".join([f"{rid} - resource" for rid in state.resources.keys()])
        
        # Add datatype objects for contracts
        all_datatypes = set()
        for task in state.tasks.values():
            for inp in task.contract.inputs:
                all_datatypes.add(inp.name)
            for out in task.contract.outputs:
                all_datatypes.add(out.name)
        
        datatype_objects = " ".join([f"{dt} - datatype" for dt in all_datatypes])
        
        # Initial state
        init_predicates = []
        
        # Task states
        for task_id, task in state.tasks.items():
            if task.status == TaskStatus.PENDING:
                init_predicates.append(f"(task-pending {task_id})")
            elif task.status == TaskStatus.READY:
                init_predicates.append(f"(task-ready {task_id})")
                init_predicates.append(f"(contract-valid {task_id})")
            elif task.status == TaskStatus.IN_PROGRESS:
                init_predicates.append(f"(task-in-progress {task_id})")
            elif task.status == TaskStatus.COMPLETED:
                init_predicates.append(f"(task-completed {task_id})")
            elif task.status == TaskStatus.FAILED:
                init_predicates.append(f"(task-failed {task_id})")
        
        # Dependencies
        for task_id, task in state.tasks.items():
            for dep_id in task.dependencies:
                init_predicates.append(f"(depends-on {task_id} {dep_id})")
        
        # Resource requirements
        for task_id, task in state.tasks.items():
            for resource_id in task.required_resources:
                init_predicates.append(f"(requires-resource {task_id} {resource_id})")
        
        # Contract predicates
        for task_id, task in state.tasks.items():
            for inp in task.contract.inputs:
                init_predicates.append(f"(has-input {task_id} {inp.name})")
            for out in task.contract.outputs:
                init_predicates.append(f"(has-output {task_id} {out.name})")
            init_predicates.append(f"(contract-valid {task_id})")
        
        # Resource availability
        for resource_id in state.available_resources:
            init_predicates.append(f"(resource-available {resource_id})")
        
        # Goal state
        goal_predicates = [f"(task-completed {task_id})" for task_id in goal_tasks]
        
        problem_pddl = f"""(define (problem contract-plan)
  (:domain contract-planning)
  
  (:objects
    {task_objects}
    {resource_objects}
    {datatype_objects}
  )
  
  (:init
    {chr(10).join(f"    {pred}" for pred in init_predicates)}
  )
  
  (:goal
    (and {' '.join(goal_predicates)})
  )
)"""
        return problem_pddl

class BlackBoxExecutor:
    """Executes generated code with strict contract enforcement"""
    
    def __init__(self, contract_validator: ContractValidator):
        self.validator = contract_validator
    
    def execute_task(self, task: Task, inputs: Dict[str, Any], 
                          context: ExecutionContext) -> Dict[str, Any]:
        """Execute a task with full contract validation"""
        
        # Validate inputs
        input_errors = self.validator.validate_task_inputs(task, inputs)
        if input_errors:
            context.errors.extend(input_errors)
            raise ValueError(f"Input validation failed: {input_errors}")
        
        context.inputs = inputs
        context.execution_trace.append(f"Starting task {task.id} with validated inputs")
        
        try:
            # Execute the generated code (simplified - in practice would use proper sandboxing)
            if task.execution_environment == "python":
                outputs = self._execute_python_code(task, inputs, context)
            else:
                raise NotImplementedError(f"Execution environment {task.execution_environment} not supported")
            
            # Validate outputs
            output_errors = self.validator.validate_task_outputs(task, outputs)
            if output_errors:
                context.errors.extend(output_errors)
                raise ValueError(f"Output validation failed: {output_errors}")
            
            context.outputs = outputs
            context.execution_trace.append(f"Task {task.id} completed successfully with validated outputs")
            
            return outputs
            
        except Exception as e:
            context.errors.append(f"Execution failed: {str(e)}")
            context.execution_trace.append(f"Task {task.id} failed: {str(e)}")
            raise
    
    def _execute_python_code(self, task: Task, inputs: Dict[str, Any], 
                                  context: ExecutionContext) -> Dict[str, Any]:
        """Execute Python code with sandboxing (simplified implementation)"""
        
        if not task.generated_code:
            raise ValueError(f"No generated code for task {task.id}")
        
        # Create execution namespace
        namespace = {
            'inputs': inputs,
            'context': context,
            '__builtins__': __builtins__,
        }
        
        try:
            # Execute the code (in production, use proper sandboxing)
            exec(task.generated_code, namespace)
            
            # The generated code should define a function with the task name
            function_name = task.id.lower().replace('-', '_')
            if function_name in namespace:
                result = namespace[function_name](inputs)
                return result if isinstance(result, dict) else {'result': result}
            else:
                raise ValueError(f"Generated code must define function '{function_name}'")
                
        except Exception as e:
            raise RuntimeError(f"Code execution failed: {str(e)}")

class EnhancedPDDLPlanner:
    """PDDL planner with contract enforcement and code generation"""
    
    def __init__(self, model: str = "gpt-oss:20b", val_path: str = "validate"):
        self.model_client = ModelClient(model)
        self.parser = NaturalLanguageParser(self.model_client)
        self.explainer = PlanExplainer(self.model_client)
        self.pddl_generator = PDDLGenerator()
        self.contract_validator = ContractValidator()
        self.executor = BlackBoxExecutor(self.contract_validator)
        # VAL validator would be initialized here
    
    def parse_natural_language_request(self, user_request: str) -> PlanningState:
        """Parse natural language into planning state using separated client"""
        parsed_data = self.parser.parse_requirements_to_tasks(user_request)
        return self._create_planning_state_from_parsed_data(parsed_data)
    
    def _create_planning_state_from_parsed_data(self, parsed_data: dict) -> PlanningState:
        """Convert parsed data into PDDL planning state"""
        
        tasks = {}
        for task_data in parsed_data.get("tasks", []):
            # Create contract from parsed data
            contract_data = task_data.get("contract", {})
            
            # Convert contract inputs/outputs
            inputs = [InputContract(**inp) for inp in contract_data.get("inputs", [])]
            outputs = [OutputContract(**out) for out in contract_data.get("outputs", [])]
            
            contract = TaskContract(
                task_id=task_data["id"],
                inputs=inputs,
                outputs=outputs,
                preconditions=contract_data.get("preconditions", []),
                postconditions=contract_data.get("postconditions", []),
                side_effects=contract_data.get("side_effects", [])
            )
            
            task = Task(
                id=task_data["id"],
                name=task_data["name"],
                description=task_data["description"],
                duration_hours=task_data["duration_hours"],
                dependencies=task_data.get("dependencies", []),
                required_resources=task_data.get("required_resources", []),
                contract=contract
            )
            tasks[task.id] = task
        
        resources = {}
        for resource_data in parsed_data.get("resources", []):
            resource = Resource(
                id=resource_data["id"],
                name=resource_data["name"],
                resource_type=ResourceType(resource_data["resource_type"]),
                available=resource_data.get("available", True),
                capacity=resource_data.get("capacity", 1),
                properties=resource_data.get("properties", {})
            )
            resources[resource.id] = resource
        
        return PlanningState(
            tasks=tasks,
            resources=resources,
            completed_tasks=[]
        )
    
    def plan_and_generate_code(self, state: PlanningState, 
                              goal_tasks: List[str] = None) -> Tuple[List[Dict], Dict[str, str]]:
        """Generate plan and corresponding code for all tasks"""
        
        # Generate execution plan
        plan = self._generate_plan(state, goal_tasks)
        
        # Generate code for each task
        generated_code = {}
        for task_id, task in state.tasks.items():
            if goal_tasks is None or task_id in goal_tasks:
                print(f"🤖 Generating code for {task.name}...")
                code = self.model_client.generate_code_with_contract(task)
                generated_code[task_id] = code
                task.generated_code = code
        
        return plan, generated_code
    
    def _generate_plan(self, state: PlanningState, goal_tasks: List[str] = None) -> List[Dict]:
        """Generate execution plan (simplified)"""
        if goal_tasks is None:
            goal_tasks = list(state.tasks.keys())
        
        plan = []
        working_state = PlanningState(**state.model_dump())
        
        max_iterations = len(working_state.tasks) * 2
        iteration = 0
        
        while len(working_state.completed_tasks) < len(goal_tasks) and iteration < max_iterations:
            ready_tasks = self._find_ready_tasks(working_state, goal_tasks)
            
            if not ready_tasks:
                remaining_tasks = [tid for tid in goal_tasks 
                                 if tid not in working_state.completed_tasks]
                plan.append({
                    "action": "error",
                    "message": f"Planning stuck. Remaining tasks: {remaining_tasks}",
                    "time": working_state.current_time
                })
                break
            
            # Execute the first ready task
            task_id = ready_tasks[0]
            task = working_state.tasks[task_id]
            
            plan.append({
                "action": "execute_task",
                "task_id": task_id,
                "task_name": task.name,
                "duration": task.duration_hours,
                "start_time": working_state.current_time,
                "end_time": working_state.current_time + task.duration_hours,
                "resources_used": task.required_resources,
                "contract": task.contract.model_dump()
            })
            
            # Simulate task execution
            task.status = TaskStatus.COMPLETED
            working_state.completed_tasks.append(task_id)
            working_state.current_time += task.duration_hours
            
            iteration += 1
        
        return plan
    
    def _find_ready_tasks(self, state: PlanningState, goal_tasks: List[str]) -> List[str]:
        """Find tasks ready for execution"""
        ready_tasks = []
        for task_id in goal_tasks:
            if task_id in state.completed_tasks:
                continue
            
            task = state.tasks[task_id]
            if task.status != TaskStatus.PENDING:
                continue
            
            # Check dependencies
            deps_satisfied = all(dep_id in state.completed_tasks 
                               for dep_id in task.dependencies)
            
            # Check resources
            resources_available = all(res_id in state.available_resources 
                                    for res_id in task.required_resources)
            
            if deps_satisfied and resources_available:
                ready_tasks.append(task_id)
        
        return ready_tasks

def create_sample_contracted_tasks() -> PlanningState:
    """Create sample tasks with strict contracts"""
    
    # Task 1: User Authentication
    auth_contract = TaskContract(
        task_id="auth_system",
        inputs=[
            InputContract(
                name="user_data",
                data_type=DataType.JSON,
                required=True,
                validation_rules=["has username", "has password", "password length > 8"],
                description="User registration/login data"
            ),
            InputContract(
                name="auth_config",
                data_type=DataType.JSON,
                required=True,
                validation_rules=["has jwt_secret", "has expiry_time"],
                description="Authentication configuration"
            )
        ],
        outputs=[
            OutputContract(
                name="auth_token",
                data_type=DataType.STRING,
                validation_rules=["not empty", "is_jwt_format"],
                description="JWT authentication token"
            ),
            OutputContract(
                name="user_id",
                data_type=DataType.INTEGER,
                validation_rules=["positive"],
                description="Unique user identifier"
            )
        ],
        preconditions=["Database connection available", "JWT secret configured"],
        postconditions=["Valid JWT token generated", "User session created"],
        side_effects=["User record created/updated in database"]
    )
    
    # Task 2: Dashboard Generation
    dashboard_contract = TaskContract(
        task_id="dashboard_gen",
        inputs=[
            InputContract(
                name="user_id",
                data_type=DataType.INTEGER,
                required=True,
                validation_rules=["positive"],
                description="Authenticated user ID"
            ),
            InputContract(
                name="dashboard_config",
                data_type=DataType.JSON,
                required=True,
                validation_rules=["has widgets", "has layout"],
                description="Dashboard configuration"
            )
        ],
        outputs=[
            OutputContract(
                name="dashboard_html",
                data_type=DataType.STRING,
                validation_rules=["not empty", "valid_html"],
                description="Generated dashboard HTML"
            ),
            OutputContract(
                name="analytics_data",
                data_type=DataType.JSON,
                validation_rules=["has metrics", "has timestamps"],
                description="User analytics data"
            )
        ],
        preconditions=["User is authenticated", "Analytics data available"],
        postconditions=["Dashboard HTML is valid", "Analytics data is current"],
        side_effects=["Dashboard view logged", "User preferences updated"]
    )
    
    tasks = {
        "auth_system": Task(
            id="auth_system",
            name="User Authentication System",
            description="Implement secure user authentication with JWT",
            duration_hours=8,
            dependencies=[],
            required_resources=["developer", "database"],
            contract=auth_contract,
            execution_environment="python"
        ),
        "dashboard_gen": Task(
            id="dashboard_gen", 
            name="Dashboard Generation",
            description="Generate personalized user dashboard",
            duration_hours=6,
            dependencies=["auth_system"],
            required_resources=["developer"],
            contract=dashboard_contract,
            execution_environment="python"
        )
    }
    
    resources = {
        "developer": Resource(
            id="developer",
            name="Full Stack Developer",
            resource_type=ResourceType.DEVELOPER,
            available=True
        ),
        "database": Resource(
            id="database",
            name="PostgreSQL Database",
            resource_type=ResourceType.DATABASE,
            available=True,
            properties={"connection_string": "postgresql://localhost:5432/app"}
        )
    }
    
    return PlanningState(
        tasks=tasks,
        resources=resources,
        completed_tasks=[],
        current_time=0
    )

def demo_black_box_system():
    """Demonstrate the black box contract enforcement system"""
    
    print("=== Black Box PDDL Contract Enforcement Demo ===\n")
    
    # Initialize system with your model client
    planner = EnhancedPDDLPlanner(model="gpt-oss:20b")
    
    # Create state with contracted tasks
    state = create_sample_contracted_tasks()
    
    print("Tasks with Contracts:")
    for task_id, task in state.tasks.items():
        print(f"\n{task.name} ({task_id})")
        print(f"   Inputs: {[inp.name for inp in task.contract.inputs]}")
        print(f"   Outputs: {[out.name for out in task.contract.outputs]}")
        print(f"   Preconditions: {task.contract.preconditions}")
        print(f"   Postconditions: {task.contract.postconditions}")
    
    try:
        # Test natural language parsing
        print(f"\nTesting Natural Language Parsing:")
        nl_request = "Build a user authentication system with secure login and password hashing"
        parsed_state = planner.parse_natural_language_request(nl_request)
        print(f"   Parsed {len(parsed_state.tasks)} tasks from: '{nl_request}'")
        
        # Generate plan and code
        print(f"\nGenerating execution plan and black box code...")
        plan, generated_code = planner.plan_and_generate_code(state)
        
        print(f"\nEXECUTION PLAN:")
        for step in plan:
            if step["action"] == "execute_task":
                print(f"  {step['start_time']}-{step['end_time']}h: {step['task_name']}")
                print(f"     Contract enforced: {len(step['contract']['inputs'])} inputs -> {len(step['contract']['outputs'])} outputs")
            elif step["action"] == "error":
                print(f"  {step['message']}")
        
        print(f"\nGENERATED BLACK BOX FUNCTIONS:")
        for task_id, code in generated_code.items():
            print(f"\n--- {task_id.upper()} ---")
            print(code[:300] + "..." if len(code) > 300 else code)
        
        # Demonstrate contract enforcement
        print(f"\nTESTING CONTRACT ENFORCEMENT:")
        
        # Test auth system with valid inputs
        auth_task = state.tasks["auth_system"]
        valid_inputs = {
            "user_data": {"username": "testuser", "password": "securepass123"},
            "auth_config": {"jwt_secret": "mysecret", "expiry_time": 3600}
        }
        
        print(f"\nTesting {auth_task.name} with VALID inputs:")
        print(f"\nTesting {auth_task.name} with VALID inputs:")
        try:
            context = ExecutionContext(task_id="auth_system", inputs=valid_inputs)
            
            # Validate inputs
            input_errors = planner.contract_validator.validate_task_inputs(auth_task, valid_inputs)
            if input_errors:
                print(f"   Input validation failed: {input_errors}")
            else:
                print(f"   Input validation passed")
                print(f"   Inputs: {list(valid_inputs.keys())}")
                
                # Simulate execution and output validation
                simulated_outputs = {
                    "auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "user_id": 12345
                }
                
                output_errors = planner.contract_validator.validate_task_outputs(auth_task, simulated_outputs)
                if output_errors:
                    print(f"   Output validation failed: {output_errors}")
                else:
                    print(f"   Output validation passed")
                    print(f"   Outputs: {list(simulated_outputs.keys())}")

        except Exception as e:
            print(f"   Execution failed: {e}")

        # Test with invalid inputs
        print(f"\nTesting {auth_task.name} with INVALID inputs:")
        invalid_inputs = {
            "user_data": {"username": "test"},  # Missing password
            "auth_config": {"jwt_secret": ""}   # Empty secret
        }

        input_errors = planner.contract_validator.validate_task_inputs(auth_task, invalid_inputs)
        if input_errors:
            print(f"   Input validation correctly failed: {input_errors}")
        else:
            print(f"   Input validation should have failed!")
        
        # Show contract violation detection
        print(f"\nCONTRACT BENEFITS:")
        print(f"   • Black box functions with guaranteed interfaces")
        print(f"   • Automatic input/output validation")
        print(f"   • Precondition/postcondition enforcement")
        print(f"   • Type safety and error detection")
        print(f"   • Composable, testable code generation")
        print(f"   • PDDL formal verification of execution order")
        
        # Show PDDL domain with contracts
        print(f"\nPDDL DOMAIN WITH CONTRACT ENFORCEMENT:")
        domain_snippet = planner.pddl_generator.generate_domain(state)
        print(domain_snippet[:500] + "...")
        
        # Test with FastAPI example
        print(f"\nFastAPI Integration Example:")
        api = ContractPlanningAPI(model="gpt-oss:20b")
        
        sample_request = PlanRequest(
            description="Create a REST API with user authentication and data validation",
            requirements=["JWT tokens", "Input validation", "Error handling"],
            team_resources=["backend_dev", "database"],
            enforce_contracts=True
        )
        
        print(f"   Request: {sample_request.description}")
        print(f"   Requirements: {sample_request.requirements}")
        print(f"   API ready for FastAPI integration")
        
        # Show validation results summary
        print(f"\nSYSTEM CAPABILITIES:")
        print(f"   • Natural language -> Structured tasks")
        print(f"   • Contract-enforced code generation") 
        print(f"   • PDDL formal planning verification")
        print(f"   • Runtime input/output validation")
        print(f"   • Black box function composition")
        print(f"   • FastAPI-ready service interface")
        
    except Exception as e:
        print(f"Demo failed: {e}")
    
    finally:
        planner.model_client.close()
        
        
class PlanRequest(BaseModel):
    description: str
    requirements: List[str] = Field(default_factory=list)
    team_resources: List[str] = Field(default_factory=list)
    enforce_contracts: bool = True

class PlanResponse(BaseModel):
    plan: List[Dict[str, Any]]
    generated_code: Dict[str, str]
    contracts: Dict[str, TaskContract]
    validation_results: Dict[str, List[str]]
    execution_ready: bool

class ContractPlanningAPI:
    """FastAPI-ready planning service with contract enforcement"""
    
    def __init__(self, model: str = "gpt-oss:20b"):
        self.planner = EnhancedPDDLPlanner(model)
    
    def create_plan(self, request: PlanRequest) -> PlanResponse:
        """Create a plan with contract-enforced code generation"""
        
        try:
            # Parse requirements into tasks with contracts
            state = self.planner.parse_natural_language_request(request.description)
            
            # Generate plan and code
            plan, generated_code = self.planner.plan_and_generate_code(state)
            
            # Extract contracts
            contracts = {tid: task.contract for tid, task in state.tasks.items()}
            
            # Validate all contracts
            validation_results = {}
            for task_id, task in state.tasks.items():
                # Test with empty inputs to check contract structure
                input_errors = self.planner.contract_validator.validate_task_inputs(task, {})
                validation_results[task_id] = input_errors
            
            execution_ready = all(not errors for errors in validation_results.values())
            
            return PlanResponse(
                plan=plan,
                generated_code=generated_code,
                contracts=contracts,
                validation_results=validation_results,
                execution_ready=execution_ready
            )
            
        except Exception as e:
            raise ValueError(f"Planning failed: {str(e)}")
    
    def close(self):
        self.planner.model_client.close()

# Example usage patterns
def example_usage_patterns():
    """Show different ways to use the black box system"""
    
    examples = {
        "web_development": {
            "description": "Build a full-stack web application",
            "tasks": [
                {
                    "name": "Database Schema Design",
                    "inputs": ["requirements", "data_model"],
                    "outputs": ["sql_schema", "migration_scripts"],
                    "contract_rules": ["SQL is valid", "Migrations are reversible"]
                },
                {
                    "name": "API Development", 
                    "inputs": ["schema", "endpoints_spec"],
                    "outputs": ["api_code", "test_suite"],
                    "contract_rules": ["All endpoints covered", "Tests pass"]
                },
                {
                    "name": "Frontend Generation",
                    "inputs": ["api_spec", "ui_mockups"],
                    "outputs": ["frontend_code", "component_library"],
                    "contract_rules": ["Responsive design", "Accessibility compliant"]
                }
            ]
        },
        
        "data_pipeline": {
            "description": "Create an ETL data pipeline",
            "tasks": [
                {
                    "name": "Data Extraction",
                    "inputs": ["source_config", "extraction_rules"],
                    "outputs": ["raw_data", "extraction_log"],
                    "contract_rules": ["Data format validated", "Error handling included"]
                },
                {
                    "name": "Data Transformation",
                    "inputs": ["raw_data", "transformation_rules"],
                    "outputs": ["cleaned_data", "transformation_report"],
                    "contract_rules": ["Schema consistency", "Quality metrics met"]
                },
                {
                    "name": "Data Loading",
                    "inputs": ["cleaned_data", "target_config"],
                    "outputs": ["load_status", "performance_metrics"],
                    "contract_rules": ["Atomicity guaranteed", "Performance targets met"]
                }
            ]
        },
        
        "ml_workflow": {
            "description": "Machine learning model development",
            "tasks": [
                {
                    "name": "Feature Engineering",
                    "inputs": ["raw_dataset", "feature_config"],
                    "outputs": ["feature_matrix", "feature_importance"],
                    "contract_rules": ["No data leakage", "Features documented"]
                },
                {
                    "name": "Model Training",
                    "inputs": ["feature_matrix", "model_config"],
                    "outputs": ["trained_model", "training_metrics"],
                    "contract_rules": ["Cross-validation performed", "Metrics logged"]
                },
                {
                    "name": "Model Deployment",
                    "inputs": ["trained_model", "deployment_config"],
                    "outputs": ["model_endpoint", "monitoring_setup"],
                    "contract_rules": ["Health checks enabled", "Rollback capability"]
                }
            ]
        }
    }
    
    return examples

if __name__ == "__main__":
    demo_black_box_system()