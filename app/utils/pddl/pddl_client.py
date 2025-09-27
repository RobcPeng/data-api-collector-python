from app.utils.ollama.ollama_config import client
from app.utils.ollama.ollama_functions import call_model
from .pddl_classes import Task
import re

class ModelClient:
    """Wrapper for your existing call_model function with contract-aware code generation"""
    
    def __init__(self, model: str = "codestral:latest"):
        self.model = model
    
    def generate(self, prompt: str, system_prompt: str = None) -> str:
        """Generate text using your call_model function"""
        try: 
            response = call_model(prompt, role="user", model=self.model, system_prompt = system_prompt)
            
            # Extract content from response (adjust based on your response format)
            if hasattr(response, 'choices') and response.choices:
                return response.choices[0].message.content.strip()
            elif hasattr(response, 'content'):
                return response.content.strip()
            else:
                return str(response).strip()
                
        except Exception as e:
            return f"Error: {e}"
    
    def generate_code_with_contract(self, task: Task) -> str:
        """Generate code that enforces the task contract"""
        
        # Build input validation
        input_validation = []
        for inp in task.contract.inputs:
            validation_code = f"# Validate {inp.name}: {inp.data_type.value}"
            if inp.required:
                validation_code += f"\nassert '{inp.name}' in inputs, 'Required input {inp.name} missing'"
            for rule in inp.validation_rules:
                validation_code += f"\n# Rule: {rule}"
            input_validation.append(validation_code)
        
        # Build output specification
        output_spec = []
        for out in task.contract.outputs:
            output_spec.append(f"'{out.name}': {out.data_type.value}  # {out.description}")
        
        system_prompt = f"""You are a code generation AI that MUST follow strict contracts.

Generate {task.execution_environment} code for this task:
- Task: {task.name}
- Description: {task.description}

CONTRACT REQUIREMENTS (MANDATORY):
Input Contract:
{chr(10).join(f"- {inp.name} ({inp.data_type.value}): {inp.description}" for inp in task.contract.inputs)}

Output Contract:
{chr(10).join(f"- {out.name} ({out.data_type.value}): {out.description}" for out in task.contract.outputs)}

Preconditions:
{chr(10).join(f"- {pre}" for pre in task.contract.preconditions)}

Postconditions:
{chr(10).join(f"- {post}" for post in task.contract.postconditions)}

CRITICAL RULES:
1. Function MUST accept inputs dict and return outputs dict
2. Validate ALL required inputs exist and have correct types
3. Generate ALL specified outputs with correct types
4. Raise clear exceptions if preconditions not met
5. Ensure postconditions are satisfied before returning
6. Add comprehensive error handling
7. Include type hints and docstrings
8. Make the function completely self-contained (black box)

Generate ONLY the function code, nothing else."""

        prompt = f"Generate the {task.execution_environment} function for: {task.name}"
        
        code = self.generate(prompt, system_prompt)
        return self._clean_generated_code(code)
    
    def _clean_generated_code(self, code: str) -> str:
        """Clean and format generated code"""
        # Remove markdown code blocks if present
        code = re.sub(r'```\w*\n', '', code)
        code = re.sub(r'```', '', code)
        return code.strip()
    
    def close(self):
        """No cleanup needed for your client"""
        pass

class NaturalLanguageParser:
    """Uses LLM to parse natural language into structured planning data"""
    
    def __init__(self, model_client: ModelClient):
        self.model_client = model_client
    
    def parse_requirements_to_tasks(self, user_request: str) -> dict:
        """Parse natural language request into structured task data"""
        
        system_prompt = """You are a project planning assistant. Parse the user's request into a structured JSON format for task planning.

Use ONLY these data types: "string", "integer", "boolean", "json", "file", "url", "database_record", "datatime"
resource_type must be exactly one of: "developer", "database", "api_endpoint", "file_system", "compute", "network", "qa"


Extract:
1. Tasks (with names, descriptions, estimated hours, dependencies)
2. Resources needed (people, equipment, etc.)
3. Contracts for each task (inputs, outputs, validation rules)

Return ONLY valid JSON in this format:
{
  "tasks": [
    {
      "id": "task_1",
      "name": "Task Name",
      "description": "Description",
      "duration_hours": 4,
      "dependencies": ["task_id_if_any"],
      "required_resources": ["resource_id"],
      "contract": {
        "task_id": "task_1",
        "inputs": [
          {
            "name": "input_name",
            "data_type": "string",
            "required": true,
            "validation_rules": ["not empty"],
            "description": "Input description"
          }
        ],
        "outputs": [
          {
            "name": "output_name", 
            "data_type": "json",
            "validation_rules": ["valid format"],
            "description": "Output description"
          }
        ],
        "preconditions": ["Condition that must be true before"],
        "postconditions": ["Condition that must be true after"],
        "side_effects": ["What changes in the system"]
      }
    }
  ],
  "resources": [
    {
      "id": "resource_1",
      "name": "Resource Name", 
      "resource_type": "developer",
      "available": true,
      "capacity": 1,
      "properties": {}
    }
  ]
}

Be specific and realistic with time estimates. Create logical task dependencies and comprehensive contracts."""

        prompt = f"Parse this project request: {user_request}"
        
        response = self.model_client.generate(prompt, system_prompt)
        
        try:
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                response = json_match.group()
            
            import json
            parsed_data = json.loads(response)
            return parsed_data
        except json.JSONDecodeError as e:
            print(f"Error parsing LLM response as JSON: {e}")
            return self._create_fallback_structure(user_request)
    
    def _create_fallback_structure(self, user_request: str) -> dict:
        """Create a simple fallback structure if LLM parsing fails"""
        return {
            "tasks": [
                {
                    "id": "task_1",
                    "name": "Main Task",
                    "description": user_request,
                    "duration_hours": 8,
                    "dependencies": [],
                    "required_resources": ["person_1"],
                    "contract": {
                        "task_id": "task_1",
                        "inputs": [
                            {
                                "name": "requirements",
                                "data_type": "string",
                                "required": True,
                                "validation_rules": ["not empty"],
                                "description": "Task requirements"
                            }
                        ],
                        "outputs": [
                            {
                                "name": "result",
                                "data_type": "string", 
                                "validation_rules": ["not empty"],
                                "description": "Task result"
                            }
                        ],
                        "preconditions": ["Requirements available"],
                        "postconditions": ["Task completed"],
                        "side_effects": ["System updated"]
                    }
                }
            ],
            "resources": [
                {
                    "id": "person_1",
                    "name": "Team Member",
                    "resource_type": "developer",
                    "available": True,
                    "capacity": 1,
                    "properties": {}
                }
            ]
        }

class PlanExplainer:
    """Uses LLM to explain plans in natural language"""
    
    def __init__(self, model_client: ModelClient):
        self.model_client = model_client
    
    def explain_plan_with_validation(self, plan: list, validation_result, original_request: str) -> str:
        """Enhanced explanation that includes validation results"""
        
        system_prompt = """You are a project manager explaining a project plan to a team member. 

The plan has been validated using formal PDDL validation. Include:
1. Plan summary and timeline
2. Validation status (valid/invalid)
3. Any issues or warnings found
4. Confidence level in the plan
5. Recommendations

Be clear about the validation results and what they mean for plan reliability."""

        plan_summary = f"Original request: {original_request}\n\n"
        plan_summary += f"Plan validation: {'✅ VALID' if validation_result.is_valid else '❌ INVALID'}\n\n"
        
        if validation_result.errors:
            plan_summary += f"Validation errors:\n"
            for error in validation_result.errors:
                plan_summary += f"- {error}\n"
            plan_summary += "\n"
        
        if validation_result.warnings:
            plan_summary += f"Validation warnings:\n"
            for warning in validation_result.warnings:
                plan_summary += f"- {warning}\n"
            plan_summary += "\n"
        
        plan_summary += "Generated plan:\n"
        for step in plan:
            if step.get("action") == "execute_task":
                plan_summary += f"- {step['task_name']}: {step['duration']} hours (Time {step['start_time']}-{step['end_time']})\n"
            elif step.get("action") == "error":
                plan_summary += f"- Issue: {step['message']}\n"
        
        prompt = f"Explain this validated project plan:\n\n{plan_summary}"
        
        return self.model_client.generate(prompt, system_prompt)