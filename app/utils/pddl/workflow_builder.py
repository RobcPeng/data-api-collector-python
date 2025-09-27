from typing import Dict, Any
import uuid
from .task_repository import TaskRepository


class WorkflowBuilder:
    """Build workflows by connecting multiple tasks."""
    
    def __init__(self, task_repository: TaskRepository):
        """Initialize with a task repository."""
        self.task_repository = task_repository
        
    def create_workflow(self, name: str, description: str) -> Dict[str, Any]:
        """Create a new workflow with connected tasks."""
        print(f"=== Creating Workflow: {name} ===")
        print(description)
        
        workflow = {
            "id": f"workflow_{uuid.uuid4().hex[:8]}",
            "name": name,
            "description": description,
            "tasks": {},
            "connections": []
        }
        
        # Show available tasks
        available_tasks = self.task_repository.list_tasks()
        print("\nAvailable tasks:")
        for i, task in enumerate(available_tasks):
            print(f"{i+1}. {task.name} ({task.id})")
            
        # Add tasks to workflow
        workflow_tasks = {}
        while True:
            task_choice = input("\nAdd task to workflow (number or ID, leave empty to finish): ")
            if not task_choice:
                break
                
            try:
                # Handle both number (index) or direct ID input
                if task_choice.isdigit() and int(task_choice) <= len(available_tasks):
                    task = available_tasks[int(task_choice) - 1]
                else:
                    task = self.task_repository.get_task(task_choice)
                    
                if task:
                    # Allow custom task ID in the workflow context
                    workflow_task_id = input(f"Workflow-specific task ID (default: {task.id}): ") or task.id
                    workflow_tasks[workflow_task_id] = task
                    print(f"Added {task.name} as {workflow_task_id}")
                else:
                    print("Task not found")
            except (ValueError, IndexError):
                print("Invalid selection")
                
        # No tasks added
        if not workflow_tasks:
            print("No tasks added to workflow.")
            return workflow
            
        # Create connections between tasks
        print("\n=== Define Task Connections ===")
        print("Available tasks in workflow:")
        for task_id in workflow_tasks:
            print(f"- {task_id}")
            
        while True:
            print("\nAdd connection (format: source_task_id->target_task_id, leave empty to finish):")
            connection = input()
            if not connection:
                break
                
            if "->" in connection:
                source, target = connection.split("->")
                source = source.strip()
                target = target.strip()
                
                if source in workflow_tasks and target in workflow_tasks:
                    workflow["connections"].append({"from": source, "to": target})
                    # Auto-update dependency
                    task_obj = workflow_tasks[target]
                    if source not in task_obj.dependencies:
                        task_obj.dependencies.append(source)
                        self.task_repository.update_task(task_obj)
                    print(f"Connection added: {source} -> {target}")
                else:
                    print("Invalid task IDs")
            else:
                print("Invalid format. Use source->target")
                
        # Store tasks in workflow
        workflow["tasks"] = {tid: task.model_dump() for tid, task in workflow_tasks.items()}
        
        print("\nWorkflow created successfully!")
        return workflow
        
    def visualize_workflow(self, workflow: Dict[str, Any]) -> None:
        """Visualize workflow as ASCII diagram."""
        if not workflow["tasks"]:
            print("Empty workflow")
            return
            
        print(f"\n=== Workflow: {workflow['name']} ===")
        print(workflow["description"])
        print("\nTasks:")
        for task_id, task_data in workflow["tasks"].items():
            print(f"- {task_id}: {task_data['name']}")
            
        print("\nConnections:")
        for conn in workflow["connections"]:
            print(f"  {conn['from']} -> {conn['to']}")
            
        # Basic ASCII visualization
        print("\nWorkflow diagram:")
        print("-" * 40)
        
        # Find roots (tasks with no incoming connections)
        incoming = {task_id: 0 for task_id in workflow["tasks"]}
        for conn in workflow["connections"]:
            incoming[conn["to"]] += 1
            
        roots = [task_id for task_id, count in incoming.items() if count == 0]
        
        # BFS to visualize workflow levels
        visited = set()
        current_level = roots
        level = 0
        
        while current_level:
            print(f"Level {level}:", " | ".join(current_level))
            visited.update(current_level)
            
            next_level = []
            for task_id in current_level:
                # Find outgoing connections
                for conn in workflow["connections"]:
                    if conn["from"] == task_id and conn["to"] not in visited and conn["to"] not in next_level:
                        next_level.append(conn["to"])
                        
            current_level = next_level
            level += 1
            
        # Check for disconnected tasks
        disconnected = set(workflow["tasks"].keys()) - visited
        if disconnected:
            print("Disconnected tasks:", ", ".join(disconnected))
            
        print("-" * 40)