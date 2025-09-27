from .pddl_classes import Task, ExecutionContext
from .pddl_client import ModelClient
from .main import ContractValidator, ResourceManager
from pathlib import Path
import json
from typing import Dict, Any
import re
import uuid
from .task_repository import TaskRepository


class TaskExecutionManager:
    """Manages execution of tasks and workflows."""
    
    def __init__(self, model_client=None):
        """Initialize with optional model client."""
        if model_client is None:
            self.model_client = ModelClient("codestral:latest")
        else:
            self.model_client = model_client
            
        self.contract_validator = ContractValidator()
        self.resource_manager = ResourceManager()
        
    def prepare_execution_context(self, task: Task, inputs: Dict[str, Any] = None) -> ExecutionContext:
        """Prepare execution context for a task."""
        if inputs is None:
            inputs = {}
            
        context = ExecutionContext(
            task_id=task.id,
            inputs=inputs,
            outputs={},
            errors=[],
            execution_trace=[]
        )
        
        # Validate inputs
        errors = self.contract_validator.validate_task_inputs(task, inputs)
        if errors:
            context.errors.extend(errors)
            
        return context
        
    def execute_task(self, task: Task, context: ExecutionContext) -> Dict[str, Any]:
        """Execute a single task."""
        # Check if context has errors
        if context.errors:
            return {"success": False, "errors": context.errors}
            
        try:
            # Generate code if not already generated
            if task.generated_code is None:
                task.generated_code = self.model_client.generate_code_with_contract(task)
                
            # Create execution sandbox
            result = self._execute_code_in_sandbox(task.generated_code, context.inputs)
            
            # Update context with results
            context.outputs = result.get("outputs", {})
            if "trace" in result:
                context.execution_trace.extend(result["trace"])
            if "errors" in result:
                context.errors.extend(result["errors"])
                
            # Validate outputs
            output_errors = self.contract_validator.validate_task_outputs(task, context.outputs)
            if output_errors:
                context.errors.extend(output_errors)
                
            return {
                "success": not context.errors,
                "outputs": context.outputs,
                "errors": context.errors,
                "trace": context.execution_trace
            }
            
        except Exception as e:
            return {
                "success": False,
                "errors": [f"Execution error: {str(e)}"]}