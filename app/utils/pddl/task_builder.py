from .pddl_classes import Task, TaskContract, InputContract, OutputContract, DataType, TaskStatus
from .pddl_client import ModelClient
from .main import ContractValidator, get_data_type_validation_rules
from pathlib import Path
import json
from typing import Dict
import re
import uuid

class TaskBuilder:
    """Interactive task builder that helps users create and modify tasks."""
    
    def __init__(self, model_client=None):
        """Initialize task builder with optional model client for suggestions."""
        if model_client is None:
            self.model_client = ModelClient("codestral:latest")
        else:
            self.model_client = model_client
        self.contract_validator = ContractValidator()
        self.task_templates = self._load_task_templates()
    
    def _load_task_templates(self) -> Dict[str, Task]:
        """Load predefined task templates."""
        # Default templates for common tasks
        templates = {
            "data_processing": Task(
                id="data_processing_template",
                name="Process Data",
                description="Generic data processing task",
                duration_hours=1,
                contract=TaskContract(
                    task_id="data_processing_template",
                    inputs=[
                        InputContract(
                            name="input_data",
                            data_type=DataType.JSON,
                            required=True,
                            validation_rules=["not empty"],
                            description="Data to process"
                        )
                    ],
                    outputs=[
                        OutputContract(
                            name="processed_data",
                            data_type=DataType.JSON,
                            description="Processed data result"
                        )
                    ],
                    preconditions=["Input data must be valid JSON"],
                    postconditions=["Output contains processed data"]
                ),
                status=TaskStatus.PENDING,
                execution_environment="python"
            ),
            "api_call": Task(
                id="api_call_template",
                name="Call External API",
                description="Make a request to an external API",
                duration_hours=1,
                contract=TaskContract(
                    task_id="api_call_template",
                    inputs=[
                        InputContract(
                            name="url",
                            data_type=DataType.URL,
                            required=True,
                            validation_rules=["not empty", "starts with http"],
                            description="API endpoint URL"
                        ),
                        InputContract(
                            name="method",
                            data_type=DataType.STRING,
                            required=True,
                            validation_rules=["in GET,POST,PUT,DELETE"],
                            description="HTTP method"
                        ),
                        InputContract(
                            name="headers",
                            data_type=DataType.JSON,
                            required=False,
                            description="HTTP headers"
                        ),
                        InputContract(
                            name="body",
                            data_type=DataType.JSON,
                            required=False,
                            description="Request body"
                        )
                    ],
                    outputs=[
                        OutputContract(
                            name="response",
                            data_type=DataType.JSON,
                            description="API response"
                        ),
                        OutputContract(
                            name="status_code",
                            data_type=DataType.INTEGER,
                            description="HTTP status code"
                        )
                    ],
                    preconditions=["URL must be accessible"],
                    postconditions=["Response contains API result"]
                ),
                status=TaskStatus.PENDING,
                execution_environment="python"
            )
            # Add more templates here
        }
        # Try to load any saved templates
        try:
            custom_templates_path = Path("task_templates.json")
            if custom_templates_path.exists():
                custom_templates = json.loads(custom_templates_path.read_text())
                for template_id, template_data in custom_templates.items():
                    templates[template_id] = Task(**template_data)
        except Exception as e:
            print(f"Error loading custom templates: {e}")
        
        return templates
        
    def create_task_from_description(self, description: str) -> Task:
        """Create a new task from a natural language description."""
        system_prompt = """Create a well-defined task with appropriate contract from this description.
        Return a single valid JSON object representing the Task with all required fields:
        - id: a unique identifier (string)
        - name: short descriptive name
        - description: longer explanation
        - duration_hours: estimated time to complete (integer)
        - contract: with inputs, outputs, preconditions, postconditions
        
        The contract should have this structure:
        "contract": {
            "task_id": "same as the task id",
            "inputs": [
                {
                    "name": "input_name",
                    "data_type": "string",  // Use standard data types like string, integer, json, etc.
                    "required": true,
                    "validation_rules": ["not empty"],
                    "description": "Description of this input"
                }
            ],
            "outputs": [
                {
                    "name": "output_name",
                    "data_type": "string",
                    "validation_rules": ["not empty"],
                    "description": "Description of this output"
                }
            ],
            "preconditions": ["Condition that must be true before"],
            "postconditions": ["Condition that must be true after"]
        }
        """
        result = self.model_client.generate(description, system_prompt)
        
        try:
            # Extract JSON if embedded in markdown or other text
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                result = json_match.group()
            
            # Parse the JSON response
            task_data = json.loads(result)
            
            # Ensure the contract structure is correct
            if "contract" in task_data:
                contract = task_data["contract"]
                
                # Ensure task_id is set properly
                if "task_id" not in contract or not contract["task_id"]:
                    contract["task_id"] = task_data.get("id", f"task_{uuid.uuid4().hex[:8]}")
                
                # Ensure inputs and outputs are lists
                if "inputs" in contract and not isinstance(contract["inputs"], list):
                    if isinstance(contract["inputs"], dict):
                        # Convert dict to list of input contracts
                        inputs_list = []
                        for name, input_details in contract["inputs"].items():
                            input_contract = {
                                "name": name,
                                "data_type": input_details.get("type", "string"),
                                "required": input_details.get("required", True),
                                "validation_rules": input_details.get("validation_rules", []),
                                "description": input_details.get("description", "")
                            }
                            inputs_list.append(input_contract)
                        contract["inputs"] = inputs_list
                    else:
                        contract["inputs"] = []
                
                # Ensure outputs are lists
                if "outputs" in contract and not isinstance(contract["outputs"], list):
                    if isinstance(contract["outputs"], dict):
                        # Convert dict to list of output contracts
                        outputs_list = []
                        for name, output_details in contract["outputs"].items():
                            output_contract = {
                                "name": name,
                                "data_type": output_details.get("type", "string"),
                                "validation_rules": output_details.get("validation_rules", []),
                                "description": output_details.get("description", "")
                            }
                            outputs_list.append(output_contract)
                        contract["outputs"] = outputs_list
                    else:
                        contract["outputs"] = []
                
                # Ensure preconditions and postconditions are lists
                if "preconditions" not in contract or not isinstance(contract["preconditions"], list):
                    contract["preconditions"] = []
                if "postconditions" not in contract or not isinstance(contract["postconditions"], list):
                    contract["postconditions"] = []
                    
                task_data["contract"] = contract
            else:
                # Create a minimal contract if none exists
                task_id = task_data.get("id", f"task_{uuid.uuid4().hex[:8]}")
                task_data["contract"] = {
                    "task_id": task_id,
                    "inputs": [],
                    "outputs": [],
                    "preconditions": [],
                    "postconditions": []
                }
            
            # Ensure we have a valid ID
            if "id" not in task_data or not task_data["id"]:
                task_data["id"] = f"task_{uuid.uuid4().hex[:8]}"
                
            # Create the task from the validated data
            task = Task(**task_data)
            return task
        except Exception as e:
            raise ValueError(f"Failed to create task from description: {e}")
    
    
    def create_task_interactive(self) -> Task:
        """Guide the user through creating a task interactively."""
        print("=== Create New Task ===")
        
        # Basic task properties
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        name = input("Task name: ")
        description = input("Task description: ")
        
        try:
            duration = int(input("Estimated duration in hours: "))
        except ValueError:
            duration = 1
            print("Invalid duration, defaulting to 1 hour")
        
        # Choose execution environment
        print("\nExecution environments: python, javascript, bash, other")
        execution_environment = input("Select execution environment (default: python): ").lower() or "python"
        
        # Create empty contract
        contract = TaskContract(
            task_id=task_id,
            inputs=[],
            outputs=[],
            preconditions=[],
            postconditions=[]
        )
        
        # Build inputs
        print("\n=== Define Input Parameters ===")
        while True:
            input_name = input("\nInput name (leave empty to finish): ")
            if not input_name:
                break
                
            print("Available data types:", ", ".join([dt.value for dt in DataType]))
            data_type_str = input("Data type (default: string): ") or "string"
            try:
                data_type = DataType(data_type_str.lower())
            except ValueError:
                print(f"Invalid data type. Using string instead.")
                data_type = DataType.STRING
                
            required = input("Required? (y/n, default: y): ").lower() != 'n'
            description = input("Description: ")
            
            # Get validation rules with suggestions
            print("Suggested validation rules for this data type:")
            suggested_rules = get_data_type_validation_rules(data_type)
            for i, rule in enumerate(suggested_rules):
                print(f"  {i+1}. {rule}")
                
            validation_rules = []
            while True:
                rule = input("Add validation rule (leave empty to finish): ")
                if not rule:
                    break
                validation_rules.append(rule)
                
            contract.inputs.append(InputContract(
                name=input_name,
                data_type=data_type,
                required=required,
                validation_rules=validation_rules,
                description=description
            ))
        
        # Build outputs
        print("\n=== Define Output Parameters ===")
        while True:
            output_name = input("\nOutput name (leave empty to finish): ")
            if not output_name:
                break
                
            print("Available data types:", ", ".join([dt.value for dt in DataType]))
            data_type_str = input("Data type (default: string): ") or "string"
            try:
                data_type = DataType(data_type_str.lower())
            except ValueError:
                print(f"Invalid data type. Using string instead.")
                data_type = DataType.STRING
                
            description = input("Description: ")
            
            # Get validation rules with suggestions
            print("Suggested validation rules for this data type:")
            suggested_rules = get_data_type_validation_rules(data_type)
            for i, rule in enumerate(suggested_rules):
                print(f"  {i+1}. {rule}")
                
            validation_rules = []
            while True:
                rule = input("Add validation rule (leave empty to finish): ")
                if not rule:
                    break
                validation_rules.append(rule)
                
            contract.outputs.append(OutputContract(
                name=output_name,
                data_type=data_type,
                validation_rules=validation_rules,
                description=description
            ))
        
        # Preconditions and postconditions
        print("\n=== Define Conditions ===")
        
        while True:
            precondition = input("Add precondition (leave empty to finish): ")
            if not precondition:
                break
            contract.preconditions.append(precondition)
            
        while True:
            postcondition = input("Add postcondition (leave empty to finish): ")
            if not postcondition:
                break
            contract.postconditions.append(postcondition)
            
        # Create and return the task
        task = Task(
            id=task_id,
            name=name,
            description=description,
            duration_hours=duration,
            dependencies=[],
            required_resources=[],
            contract=contract,
            status=TaskStatus.PENDING,
            execution_environment=execution_environment
        )
        
        print("\nTask created successfully!")
        return task
    
    def create_task_from_template(self, template_id: str) -> Task:
        """Create a new task based on a template."""
        if template_id not in self.task_templates:
            raise ValueError(f"Template '{template_id}' not found")
            
        template = self.task_templates[template_id]
        
        # Create a deep copy with a new ID
        new_task_data = template.model_dump()
        new_task_data['id'] = f"{template_id}_{uuid.uuid4().hex[:8]}"
        new_task_data['contract']['task_id'] = new_task_data['id']
        
        return Task(**new_task_data)
    
    def modify_task(self, task: Task) -> Task:
        """Modify an existing task interactively."""
        print(f"=== Modifying Task: {task.name} ===")
        
        # Show current properties and allow modifications
        print("\nCurrent properties:")
        print(f"ID: {task.id}")
        print(f"Name: {task.name}")
        print(f"Description: {task.description}")
        print(f"Duration: {task.duration_hours} hours")
        print(f"Status: {task.status.value}")
        print(f"Execution environment: {task.execution_environment}")
        
        # Allow modifications to basic properties
        name = input("\nNew name (leave empty to keep current): ")
        if name:
            task.name = name
            
        description = input("New description (leave empty to keep current): ")
        if description:
            task.description = description
            
        duration_str = input("New duration in hours (leave empty to keep current): ")
        if duration_str:
            try:
                task.duration_hours = int(duration_str)
            except ValueError:
                print("Invalid duration, keeping current value")
                
        env = input("New execution environment (leave empty to keep current): ")
        if env:
            task.execution_environment = env
            
        # Modify contract
        print("\nWould you like to modify the contract? (y/n): ")
        if input().lower() == 'y':
            self._modify_contract(task.contract)
            
        # Dependencies
        print("\nCurrent dependencies:", task.dependencies)
        print("Would you like to modify dependencies? (y/n): ")
        if input().lower() == 'y':
            task.dependencies = []
            while True:
                dep = input("Add dependency ID (leave empty to finish): ")
                if not dep:
                    break
                task.dependencies.append(dep)
                
        # Resources
        print("\nCurrent required resources:", task.required_resources)
        print("Would you like to modify required resources? (y/n): ")
        if input().lower() == 'y':
            task.required_resources = []
            while True:
                res = input("Add resource ID (leave empty to finish): ")
                if not res:
                    break
                task.required_resources.append(res)
                
        print("\nTask modified successfully!")
        return task
    
    def _modify_contract(self, contract: TaskContract) -> None:
        """Helper method to modify a task's contract."""
        # Modify inputs
        print("\n=== Current Inputs ===")
        for i, inp in enumerate(contract.inputs):
            print(f"{i+1}. {inp.name} ({inp.data_type.value}): {inp.description}")
        
        print("\nWould you like to modify inputs? (y/n): ")
        if input().lower() == 'y':
            # Options to add, modify or remove inputs
            print("1. Add new input")
            print("2. Modify existing input")
            print("3. Remove input")
            choice = input("Select option: ")
            
            if choice == "1":
                # Add new input (reuse code from create_task_interactive)
                print("\n=== Add New Input ===")
                input_name = input("Input name: ")
                print("Available data types:", ", ".join([dt.value for dt in DataType]))
                data_type_str = input("Data type (default: string): ") or "string"
                try:
                    data_type = DataType(data_type_str.lower())
                except ValueError:
                    print(f"Invalid data type. Using string instead.")
                    data_type = DataType.STRING
                    
                required = input("Required? (y/n, default: y): ").lower() != 'n'
                description = input("Description: ")
                
                validation_rules = []
                while True:
                    rule = input("Add validation rule (leave empty to finish): ")
                    if not rule:
                        break
                    validation_rules.append(rule)
                    
                contract.inputs.append(InputContract(
                    name=input_name,
                    data_type=data_type,
                    required=required,
                    validation_rules=validation_rules,
                    description=description
                ))
                
            elif choice == "2":
                # Modify existing input
                try:
                    idx = int(input("Enter input number to modify: ")) - 1
                    if 0 <= idx < len(contract.inputs):
                        inp = contract.inputs[idx]
                        
                        name = input(f"New name (current: {inp.name}): ")
                        if name:
                            inp.name = name
                            
                        data_type_str = input(f"New data type (current: {inp.data_type.value}): ")
                        if data_type_str:
                            try:
                                inp.data_type = DataType(data_type_str.lower())
                            except ValueError:
                                print("Invalid data type. Keeping current.")
                                
                        required_str = input(f"Required? (y/n, current: {'y' if inp.required else 'n'}): ")
                        if required_str.lower() in ('y', 'n'):
                            inp.required = required_str.lower() == 'y'
                            
                        description = input(f"New description (current: {inp.description}): ")
                        if description:
                            inp.description = description
                            
                        print("Current validation rules:", inp.validation_rules)
                        print("Would you like to modify validation rules? (y/n): ")
                        if input().lower() == 'y':
                            inp.validation_rules = []
                            while True:
                                rule = input("Add validation rule (leave empty to finish): ")
                                if not rule:
                                    break
                                inp.validation_rules.append(rule)
                    else:
                        print("Invalid input index")
                except ValueError:
                    print("Invalid input")
                    
            elif choice == "3":
                # Remove input
                try:
                    idx = int(input("Enter input number to remove: ")) - 1
                    if 0 <= idx < len(contract.inputs):
                        removed = contract.inputs.pop(idx)
                        print(f"Removed input: {removed.name}")
                    else:
                        print("Invalid input index")
                except ValueError:
                    print("Invalid input")
                    
        # Similar structure for outputs
        print("\n=== Current Outputs ===")
        for i, out in enumerate(contract.outputs):
            print(f"{i+1}. {out.name} ({out.data_type.value}): {out.description}")
        
        print("\nWould you like to modify outputs? (y/n): ")
        if input().lower() == 'y':
            # Options to add, modify or remove outputs
            print("1. Add new output")
            print("2. Modify existing output")
            print("3. Remove output")
            choice = input("Select option: ")
            
            if choice == "1":
                # Add new output
                print("\n=== Add New Output ===")
                output_name = input("Output name: ")
                print("Available data types:", ", ".join([dt.value for dt in DataType]))
                data_type_str = input("Data type (default: string): ") or "string"
                try:
                    data_type = DataType(data_type_str.lower())
                except ValueError:
                    print(f"Invalid data type. Using string instead.")
                    data_type = DataType.STRING
                    
                description = input("Description: ")
                
                validation_rules = []
                while True:
                    rule = input("Add validation rule (leave empty to finish): ")
                    if not rule:
                        break
                    validation_rules.append(rule)
                    
                contract.outputs.append(OutputContract(
                    name=output_name,
                    data_type=data_type,
                    validation_rules=validation_rules,
                    description=description
                ))
                
            elif choice == "2":
                # Modify existing output (similar to inputs)
                try:
                    idx = int(input("Enter output number to modify: ")) - 1
                    if 0 <= idx < len(contract.outputs):
                        out = contract.outputs[idx]
                        
                        name = input(f"New name (current: {out.name}): ")
                        if name:
                            out.name = name
                            
                        data_type_str = input(f"New data type (current: {out.data_type.value}): ")
                        if data_type_str:
                            try:
                                out.data_type = DataType(data_type_str.lower())
                            except ValueError:
                                print("Invalid data type. Keeping current.")
                                
                        description = input(f"New description (current: {out.description}): ")
                        if description:
                            out.description = description
                            
                        print("Current validation rules:", out.validation_rules)
                        print("Would you like to modify validation rules? (y/n): ")
                        if input().lower() == 'y':
                            out.validation_rules = []
                            while True:
                                rule = input("Add validation rule (leave empty to finish): ")
                                if not rule:
                                    break
                                out.validation_rules.append(rule)
                    else:
                        print("Invalid output index")
                except ValueError:
                    print("Invalid input")
                    
            elif choice == "3":
                # Remove output
                try:
                    idx = int(input("Enter output number to remove: ")) - 1
                    if 0 <= idx < len(contract.outputs):
                        removed = contract.outputs.pop(idx)
                        print(f"Removed output: {removed.name}")
                    else:
                        print("Invalid output index")
                except ValueError:
                    print("Invalid input")
                    
        # Modify preconditions and postconditions
        print("\nCurrent preconditions:", contract.preconditions)
        print("Would you like to modify preconditions? (y/n): ")
        if input().lower() == 'y':
            contract.preconditions = []
            while True:
                precondition = input("Add precondition (leave empty to finish): ")
                if not precondition:
                    break
                contract.preconditions.append(precondition)
                
        print("\nCurrent postconditions:", contract.postconditions)
        print("Would you like to modify postconditions? (y/n): ")
        if input().lower() == 'y':
            contract.postconditions = []
            while True:
                postcondition = input("Add postcondition (leave empty to finish): ")
                if not postcondition:
                    break
                contract.postconditions.append(postcondition)