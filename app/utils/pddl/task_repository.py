from .pddl_classes import Task, TaskStatus
from pathlib import Path
import json
from typing import Dict, List, Optional



class TaskRepository:
    """Storage and management for user-defined tasks."""
    
    def __init__(self, storage_path: str = "user_tasks.json"):
        """Initialize the repository with a storage file path."""
        self.storage_path = Path(storage_path)
        self.tasks: Dict[str, Task] = {}
        self._load_tasks()
        
    def _load_tasks(self) -> None:
        """Load tasks from storage."""
        if not self.storage_path.exists():
            return
            
        try:
            tasks_data = json.loads(self.storage_path.read_text())
            for task_id, task_data in tasks_data.items():
                self.tasks[task_id] = Task(**task_data)
        except Exception as e:
            print(f"Error loading tasks: {e}")
            
    def save_tasks(self) -> None:
        """Save tasks to storage."""
        try:
            tasks_data = {task_id: task.model_dump() for task_id, task in self.tasks.items()}
            self.storage_path.write_text(json.dumps(tasks_data, indent=2))
        except Exception as e:
            print(f"Error saving tasks: {e}")
            
    def add_task(self, task: Task) -> None:
        """Add a task to the repository."""
        self.tasks[task.id] = task
        self.save_tasks()
        
    def update_task(self, task: Task) -> None:
        """Update an existing task."""
        self.tasks[task.id] = task
        self.save_tasks()
        
    def delete_task(self, task_id: str) -> bool:
        """Delete a task from the repository."""
        if task_id in self.tasks:
            del self.tasks[task_id]
            self.save_tasks()
            return True
        return False
        
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self.tasks.get(task_id)
        
    def list_tasks(self) -> List[Task]:
        """List all tasks."""
        return list(self.tasks.values())
        
    def search_tasks(self, query: str) -> List[Task]:
        """Search tasks by name or description."""
        query = query.lower()
        return [
            task for task in self.tasks.values()
            if query in task.name.lower() or query in task.description.lower()
        ]
        
    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """Get tasks by status."""
        return [task for task in self.tasks.values() if task.status == status]