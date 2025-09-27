#!/usr/bin/env python
# cli.py - Command Line Interface for PDDL Task Builder

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Dict, Any, List, Optional

# Import components
from .pddl_classes import Task, TaskStatus, DataType
from .task_builder import TaskBuilder
from .task_repository import TaskRepository
from .workflow_builder import WorkflowBuilder
from .task_execution_manager import TaskExecutionManager
from .main import PlanRequest, SecureContractPlanningAPI


class PDDLTaskCLI:
    """Command Line Interface for PDDL Task Builder."""
    
    def __init__(self):
        """Initialize the CLI with required components."""
        self.api = SecureContractPlanningAPI()
        self.task_builder = TaskBuilder()
        self.task_repository = TaskRepository()
        self.workflow_builder = WorkflowBuilder(self.task_repository)
        self.task_execution_manager = TaskExecutionManager()
        
        # Ensure data directory exists
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)

    def run(self, args=None):
        """Run the CLI with the given arguments."""
        parser = self._create_parser()
        args = parser.parse_args(args)
        
        if hasattr(args, 'func'):
            try:
                args.func(args)
            except Exception as e:
                print(f"Error: {e}")
                return 1
            return 0
        else:
            parser.print_help()
            return 0
            
    def _create_parser(self):
        """Create the argument parser."""
        parser = argparse.ArgumentParser(
            description="PDDL Task Builder CLI",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  python -m app.utils.pddl.cli task list
  python -m app.utils.pddl.cli task create-interactive
  python -m app.utils.pddl.cli task create-from-description "Process CSV data and generate a report"
  python -m app.utils.pddl.cli workflow create "Data Pipeline" "Process and analyze data"
  python -m app.utils.pddl.cli plan "Build a web application with user authentication"
"""
        )
        subparsers = parser.add_subparsers(title="commands", dest="command")
        
        # Task management commands
        task_parser = subparsers.add_parser("task", help="Task management")
        task_subparsers = task_parser.add_subparsers(title="task commands")
        
        # Task list
        task_list_parser = task_subparsers.add_parser("list", help="List tasks")
        task_list_parser.add_argument("--status", help="Filter by status")
        task_list_parser.add_argument("--query", help="Search by name or description")
        task_list_parser.set_defaults(func=self._handle_task_list)
        
        # Task create interactive
        task_create_parser = task_subparsers.add_parser("create-interactive", help="Create task interactively")
        task_create_parser.set_defaults(func=self._handle_task_create_interactive)
        
        # Task create from description
        task_desc_parser = task_subparsers.add_parser("create-from-description", help="Create task from description")
        task_desc_parser.add_argument("description", help="Task description")
        task_desc_parser.set_defaults(func=self._handle_task_create_from_description)
        
        # Task create from template
        task_template_parser = task_subparsers.add_parser("create-from-template", help="Create task from template")
        task_template_parser.add_argument("template_id", help="Template ID")
        task_template_parser.set_defaults(func=self._handle_task_create_from_template)
        
        # Task view
        task_view_parser = task_subparsers.add_parser("view", help="View task details")
        task_view_parser.add_argument("task_id", help="Task ID")
        task_view_parser.set_defaults(func=self._handle_task_view)
        
        # Task modify
        task_modify_parser = task_subparsers.add_parser("modify", help="Modify task")
        task_modify_parser.add_argument("task_id", help="Task ID")
        task_modify_parser.set_defaults(func=self._handle_task_modify)
        
        # Task delete
        task_delete_parser = task_subparsers.add_parser("delete", help="Delete task")
        task_delete_parser.add_argument("task_id", help="Task ID")
        task_delete_parser.add_argument("--force", action="store_true", help="Force deletion without confirmation")
        task_delete_parser.set_defaults(func=self._handle_task_delete)

        # Task execute
        task_execute_parser = task_subparsers.add_parser("execute", help="Execute a task")
        task_execute_parser.add_argument("task_id", help="Task ID")
        task_execute_parser.add_argument("--inputs", help="JSON string of inputs or path to JSON file")
        task_execute_parser.set_defaults(func=self._handle_task_execute)
        
        # Workflow management commands
        workflow_parser = subparsers.add_parser("workflow", help="Workflow management")
        workflow_subparsers = workflow_parser.add_subparsers(title="workflow commands")
        
        # Workflow create
        workflow_create_parser = workflow_subparsers.add_parser("create", help="Create workflow")
        workflow_create_parser.add_argument("name", help="Workflow name")
        workflow_create_parser.add_argument("description", help="Workflow description")
        workflow_create_parser.set_defaults(func=self._handle_workflow_create)
        
        # Workflow list
        workflow_list_parser = workflow_subparsers.add_parser("list", help="List workflows")
        workflow_list_parser.set_defaults(func=self._handle_workflow_list)
        
        # Workflow view
        workflow_view_parser = workflow_subparsers.add_parser("view", help="View workflow")
        workflow_view_parser.add_argument("workflow_id", help="Workflow ID")
        workflow_view_parser.set_defaults(func=self._handle_workflow_view)
        
        # Workflow execute
        workflow_execute_parser = workflow_subparsers.add_parser("execute", help="Execute workflow")
        workflow_execute_parser.add_argument("workflow_id", help="Workflow ID")
        workflow_execute_parser.set_defaults(func=self._handle_workflow_execute)
        
        # Planning commands
        plan_parser = subparsers.add_parser("plan", help="Generate plan from description")
        plan_parser.add_argument("description", help="Planning description")
        plan_parser.add_argument("--use-solver", action="store_true", help="Use PDDL solver")
        plan_parser.set_defaults(func=self._handle_plan)
        
        # Template management commands
        template_parser = subparsers.add_parser("template", help="Template management")
        template_subparsers = template_parser.add_subparsers(title="template commands")
        
        # Template list
        template_list_parser = template_subparsers.add_parser("list", help="List templates")
        template_list_parser.set_defaults(func=self._handle_template_list)
        
        # Template view
        template_view_parser = template_subparsers.add_parser("view", help="View template")
        template_view_parser.add_argument("template_id", help="Template ID")
        template_view_parser.set_defaults(func=self._handle_template_view)
        
        # Utility commands
        utils_parser = subparsers.add_parser("utils", help="Utility functions")
        utils_subparsers = utils_parser.add_subparsers(title="utility commands")
        
        # List data types
        datatypes_parser = utils_subparsers.add_parser("datatypes", help="List data types")
        datatypes_parser.set_defaults(func=self._handle_list_datatypes)
        
        # List task statuses
        statuses_parser = utils_subparsers.add_parser("statuses", help="List task statuses")
        statuses_parser.set_defaults(func=self._handle_list_statuses)
        
        return parser
    
    # Task handlers
    def _handle_task_list(self, args):
        """Handle task list command."""
        tasks = self.task_repository.list_tasks()
        
        if args.status:
            try:
                status = TaskStatus(args.status)
                tasks = [t for t in tasks if t.status == status]
            except ValueError:
                print(f"Invalid status: {args.status}")
                return
                
        if args.query:
            tasks = [t for t in tasks if args.query.lower() in t.name.lower() or 
                     args.query.lower() in t.description.lower()]
        
        if not tasks:
            print("No tasks found.")
            return
            
        print(f"\nFound {len(tasks)} tasks:\n")
        print(f"{'ID':<15} {'Name':<25} {'Status':<15} {'Duration':<10}")
        print("-" * 65)
        
        for task in tasks:
            print(f"{task.id:<15} {task.name[:24]:<25} {task.status.value:<15} {task.duration_hours}h")
    
    def _handle_task_create_interactive(self, args):
        """Handle task create interactive command."""
        task = self.task_builder.create_task_interactive()
        self.task_repository.add_task(task)
        print(f"Task '{task.name}' created with ID: {task.id}")
    
    def _handle_task_create_from_description(self, args):
        """Handle task create from description command."""
        try:
            task = self.task_builder.create_task_from_description(args.description)
            self.task_repository.add_task(task)
            print(f"Task '{task.name}' created with ID: {task.id}")
        except ValueError as e:
            print(f"Error creating task: {e}")
    
    def _handle_task_create_from_template(self, args):
        """Handle task create from template command."""
        try:
            task = self.task_builder.create_task_from_template(args.template_id)
            self.task_repository.add_task(task)
            print(f"Task '{task.name}' created with ID: {task.id}")
        except ValueError as e:
            print(f"Error creating task: {e}")
    
    def _handle_task_view(self, args):
        """Handle task view command."""
        task = self.task_repository.get_task(args.task_id)
        if not task:
            print(f"Task with ID '{args.task_id}' not found.")
            return
            
        print(f"\n=== Task: {task.name} ===")
        print(f"ID: {task.id}")
        print(f"Description: {task.description}")
        print(f"Status: {task.status.value}")
        print(f"Duration: {task.duration_hours} hours")
        print(f"Dependencies: {', '.join(task.dependencies) if task.dependencies else 'None'}")
        print(f"Required Resources: {', '.join(task.required_resources) if task.required_resources else 'None'}")
        print(f"Execution Environment: {task.execution_environment}")
        
        print("\nContract:")
        print("  Inputs:")
        for inp in task.contract.inputs:
            required = "required" if inp.required else "optional"
            print(f"    - {inp.name} ({inp.data_type.value}, {required}): {inp.description}")
            if inp.validation_rules:
                print(f"      Validation: {', '.join(inp.validation_rules)}")
                
        print("  Outputs:")
        for out in task.contract.outputs:
            print(f"    - {out.name} ({out.data_type.value}): {out.description}")
            if out.validation_rules:
                print(f"      Validation: {', '.join(out.validation_rules)}")
                
        print("  Preconditions:", ', '.join(task.contract.preconditions) if task.contract.preconditions else "None")
        print("  Postconditions:", ', '.join(task.contract.postconditions) if task.contract.postconditions else "None")
        
        if task.generated_code:
            print("\nGenerated Code:")
            print("```")
            print(task.generated_code)
            print("```")
    
    def _handle_task_modify(self, args):
        """Handle task modify command."""
        task = self.task_repository.get_task(args.task_id)
        if not task:
            print(f"Task with ID '{args.task_id}' not found.")
            return
            
        modified_task = self.task_builder.modify_task(task)
        self.task_repository.update_task(modified_task)
        print(f"Task '{modified_task.name}' updated.")
    
    def _handle_task_delete(self, args):
        """Handle task delete command."""
        task = self.task_repository.get_task(args.task_id)
        if not task:
            print(f"Task with ID '{args.task_id}' not found.")
            return
            
        if not args.force:
            confirm = input(f"Are you sure you want to delete task '{task.name}' (y/n)? ")
            if confirm.lower() != 'y':
                print("Operation cancelled.")
                return
                
        success = self.task_repository.delete_task(args.task_id)
        if success:
            print(f"Task '{task.name}' deleted.")
        else:
            print(f"Failed to delete task '{task.name}'.")
    
    def _handle_task_execute(self, args):
        """Handle task execute command."""
        task = self.task_repository.get_task(args.task_id)
        if not task:
            print(f"Task with ID '{args.task_id}' not found.")
            return
            
        # Parse inputs
        inputs = {}
        if args.inputs:
            try:
                # Check if input is a file path
                if os.path.exists(args.inputs):
                    with open(args.inputs, 'r') as f:
                        inputs = json.load(f)
                else:
                    # Try parsing as a JSON string
                    inputs = json.loads(args.inputs)
            except json.JSONDecodeError:
                print("Error: Invalid JSON input.")
                return
            except Exception as e:
                print(f"Error loading inputs: {e}")
                return
        
        # Execute task
        print(f"Executing task '{task.name}'...")
        context = self.task_execution_manager.prepare_execution_context(task, inputs)
        result = self.task_execution_manager.execute_task(task, context)
        
        if result["success"]:
            print("\n✓ Task executed successfully!")
            print("\nOutputs:")
            for key, value in result["outputs"].items():
                print(f"  {key}: {value}")
        else:
            print("\n✗ Task execution failed.")
            print("\nErrors:")
            for error in result["errors"]:
                print(f"  - {error}")
            
        if "trace" in result:
            print("\nExecution trace:")
            for line in result["trace"]:
                print(f"  {line}")
    
    # Workflow handlers
    def _handle_workflow_create(self, args):
        """Handle workflow create command."""
        workflow = self.workflow_builder.create_workflow(args.name, args.description)
        
        # Save workflow to file
        workflow_path = Path("data/workflows.json")
        
        workflows = {}
        if workflow_path.exists():
            try:
                workflows = json.loads(workflow_path.read_text())
            except json.JSONDecodeError:
                pass
                
        workflows[workflow["id"]] = workflow
        workflow_path.write_text(json.dumps(workflows, indent=2))
        
        print(f"Workflow '{workflow['name']}' created with ID: {workflow['id']}")
    
    def _handle_workflow_list(self, args):
        """Handle workflow list command."""
        workflow_path = Path("data/workflows.json")
        
        if not workflow_path.exists():
            print("No workflows found.")
            return
            
        try:
            workflows = json.loads(workflow_path.read_text())
        except json.JSONDecodeError:
            print("Error loading workflows.")
            return
            
        if not workflows:
            print("No workflows found.")
            return
            
        print(f"\nFound {len(workflows)} workflows:\n")
        print(f"{'ID':<20} {'Name':<30} {'Tasks':<10}")
        print("-" * 60)
        
        for wf_id, workflow in workflows.items():
            task_count = len(workflow["tasks"])
            print(f"{wf_id:<20} {workflow['name'][:29]:<30} {task_count:<10}")
    
    def _handle_workflow_view(self, args):
        """Handle workflow view command."""
        workflow_path = Path("data/workflows.json")
        
        if not workflow_path.exists():
            print("No workflows found.")
            return
            
        try:
            workflows = json.loads(workflow_path.read_text())
        except json.JSONDecodeError:
            print("Error loading workflows.")
            return
            
        if args.workflow_id not in workflows:
            print(f"Workflow with ID '{args.workflow_id}' not found.")
            return
            
        workflow = workflows[args.workflow_id]
        self.workflow_builder.visualize_workflow(workflow)
    
    def _handle_workflow_execute(self, args):
        """Handle workflow execute command."""
        workflow_path = Path("data/workflows.json")
        
        if not workflow_path.exists():
            print("No workflows found.")
            return
            
        try:
            workflows = json.loads(workflow_path.read_text())
        except json.JSONDecodeError:
            print("Error loading workflows.")
            return
            
        if args.workflow_id not in workflows:
            print(f"Workflow with ID '{args.workflow_id}' not found.")
            return
            
        workflow = workflows[args.workflow_id]
        print(f"Executing workflow: {workflow['name']}")
        
        # TODO: Implement workflow execution
        print("Workflow execution not yet implemented.")
        
    # Planning handlers
    def _handle_plan(self, args):
        """Handle plan command."""
        request = PlanRequest(
            description=args.description,
            use_real_pddl_solver=args.use_solver
        )
        
        print(f"Planning: {args.description}")
        print(f"Using solver: {args.use_solver}")
        
        try:
            response = self.api.create_plan(request)
            
            print(f"\n✓ Plan generated!")
            print(f"✓ Execution Ready: {response.execution_ready}")
            print(f"✓ Solver Used: {response.solver_used}")
            
            print("\nPlan:")
            for i, step in enumerate(response.plan):
                print(f"  {i+1}. {step}")
            
            # Option to save tasks to repository
            save_tasks = input("\nDo you want to save the generated tasks to your repository? (y/n) ")
            if save_tasks.lower() == 'y':
                for task_id, contract in response.contracts.items():
                    # Find corresponding task in the plan
                    task_steps = [step for step in response.plan if 
                                  step.get("task_id") == task_id]
                    
                    # Try to get task details from the step
                    if task_steps:
                        step = task_steps[0]
                        task_name = step.get("task_name", f"Task {task_id}")
                        duration = step.get("duration", 1)
                    else:
                        task_name = f"Task {task_id}"
                        duration = 1
                        
                    # Create a new task with the contract
                    task = Task(
                        id=task_id,
                        name=task_name,
                        description=f"Auto-generated from plan: {args.description}",
                        duration_hours=duration,
                        dependencies=[],
                        required_resources=response.resource_allocation.get(task_id, []),
                        contract=contract,
                        status=TaskStatus.PENDING,
                        execution_environment="python",
                        generated_code=response.generated_code.get(task_id)
                    )
                    
                    self.task_repository.add_task(task)
                    print(f"  Added task: {task.name} ({task.id})")
                
        except Exception as e:
            print(f"Error generating plan: {e}")
    
    # Template handlers
    def _handle_template_list(self, args):
        """Handle template list command."""
        templates = self.task_builder.task_templates
        
        if not templates:
            print("No templates found.")
            return
            
        print(f"\nFound {len(templates)} templates:\n")
        print(f"{'ID':<25} {'Name':<30} {'Environment':<15}")
        print("-" * 70)
        
        for template_id, template in templates.items():
            print(f"{template_id:<25} {template.name:<30} {template.execution_environment:<15}")
    
    def _handle_template_view(self, args):
        """Handle template view command."""
        templates = self.task_builder.task_templates
        
        if args.template_id not in templates:
            print(f"Template with ID '{args.template_id}' not found.")
            return
            
        template = templates[args.template_id]
        
        print(f"\n=== Template: {template.name} ===")
        print(f"ID: {template.id}")
        print(f"Description: {template.description}")
        print(f"Duration: {template.duration_hours} hours")
        print(f"Execution Environment: {template.execution_environment}")
        
        print("\nContract:")
        print("  Inputs:")
        for inp in template.contract.inputs:
            required = "required" if inp.required else "optional"
            print(f"    - {inp.name} ({inp.data_type.value}, {required}): {inp.description}")
            if inp.validation_rules:
                print(f"      Validation: {', '.join(inp.validation_rules)}")
                
        print("  Outputs:")
        for out in template.contract.outputs:
            print(f"    - {out.name} ({out.data_type.value}): {out.description}")
            if out.validation_rules:
                print(f"      Validation: {', '.join(out.validation_rules)}")
                
        print("  Preconditions:", ', '.join(template.contract.preconditions))
        print("  Postconditions:", ', '.join(template.contract.postconditions))
    
    # Utility handlers
    def _handle_list_datatypes(self, args):
        """Handle list datatypes command."""
        print("\nAvailable Data Types:")
        
        # Group data types by category
        categories = {
            "Primitive Types": [dt for dt in DataType if dt.value in 
                              ["string", "integer", "float", "decimal", "boolean", "null"]],
            "Date & Time": [dt for dt in DataType if dt.value in 
                          ["date", "time", "datetime", "timestamp", "timezone", "duration"]],
            "Structured Data": [dt for dt in DataType if dt.value in 
                              ["json", "xml", "yaml", "csv", "array", "list", "dictionary", "object"]],
            "Files": [dt for dt in DataType if dt.value in 
                    ["file", "binary", "text_file", "image", "video", "audio", "document"]],
            "Documents": [dt for dt in DataType if dt.value in 
                        ["pdf", "word_doc", "excel", "powerpoint", "html", "markdown"]],
            "Network": [dt for dt in DataType if dt.value in 
                      ["url", "email", "ip_address", "mac_address", "uuid"]],
            "Database": [dt for dt in DataType if dt.value in 
                       ["database_record", "primary_key", "foreign_key", "blob", "clob"]],
            "Geographic": [dt for dt in DataType if dt.value in 
                         ["coordinate", "latitude", "longitude", "address", "postal_code"]],
            "Financial": [dt for dt in DataType if dt.value in 
                        ["currency", "price", "percentage"]],
            "Security": [dt for dt in DataType if dt.value in 
                       ["password", "token", "api_key", "encrypted_data", "hash"]],
            "Communication": [dt for dt in DataType if dt.value in 
                            ["phone_number", "message", "notification"]],
            "Measurement": [dt for dt in DataType if dt.value in 
                          ["metric", "unit_of_measure", "quantity"]],
            "Other": [dt for dt in DataType if dt.value in 
                    ["regex_pattern", "color_code", "version_number", "status_code"]],
        }
        
        # Print by category
        for category, datatypes in categories.items():
            print(f"\n{category}:")
            for dt in datatypes:
                print(f"  - {dt.value}")
    
    def _handle_list_statuses(self, args):
        """Handle list statuses command."""
        print("\nAvailable Task Statuses:")
        
        # Group statuses by category
        categories = {
            "Initial States": [s for s in TaskStatus if s.value in 
                             ["pending", "queued", "scheduled", "ready"]],
            "Active States": [s for s in TaskStatus if s.value in 
                            ["in_progress", "running", "processing", "executing"]],
            "Waiting States": [s for s in TaskStatus if s.value in 
                             ["blocked", "waiting", "paused", "suspended", "on_hold"]],
            "Completion States": [s for s in TaskStatus if s.value in 
                                ["completed", "success", "finished"]],
            "Failure States": [s for s in TaskStatus if s.value in 
                             ["failed", "error", "timeout", "aborted", "cancelled"]],
            "Review States": [s for s in TaskStatus if s.value in 
                            ["under_review", "approved", "rejected"]],
            "Retry States": [s for s in TaskStatus if s.value in 
                           ["retrying", "retry_pending"]]
        }
        
        # Print by category
        for category, statuses in categories.items():
            print(f"\n{category}:")
            for status in statuses:
                print(f"  - {status.value}")


def main():
    """Main entry point for the CLI."""
    cli = PDDLTaskCLI()
    return cli.run()


if __name__ == "__main__":
    sys.exit(main())