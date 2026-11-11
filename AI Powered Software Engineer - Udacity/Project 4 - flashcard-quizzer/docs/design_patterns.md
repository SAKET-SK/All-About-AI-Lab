# Design Patterns Guide

> **Note:** The examples below use a simple task list to illustrate each pattern. In the Flashcard Quizzer you apply the same ideas to your own domain. For example, use the Strategy pattern for the quiz modes (`SequentialMode`, `RandomMode`, `AdaptiveMode`) and a Factory to pick the mode from the `--mode` flag.

This guide provides examples of common design patterns that you can implement in your AI-assisted development project. Use these patterns to improve code organization, maintainability, and demonstrate software engineering best practices.

## 1. Strategy Pattern

The Strategy pattern allows you to select algorithms at runtime. It's useful when you have multiple ways to perform a task.

### Example: Task Sorting Strategies

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class SortingStrategy(ABC):
    """Abstract base class for sorting strategies."""
    
    @abstractmethod
    def sort(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        pass

class PrioritySortingStrategy(SortingStrategy):
    """Sort tasks by priority."""
    
    def sort(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        priority_order = {"high": 3, "medium": 2, "low": 1}
        return sorted(tasks, key=lambda x: priority_order.get(x["priority"], 0), reverse=True)

class DateSortingStrategy(SortingStrategy):
    """Sort tasks by creation date."""
    
    def sort(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(tasks, key=lambda x: x["created_at"])

class TaskSorter:
    """Context class that uses sorting strategies."""
    
    def __init__(self, strategy: SortingStrategy):
        self._strategy = strategy
    
    def set_strategy(self, strategy: SortingStrategy):
        self._strategy = strategy
    
    def sort_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self._strategy.sort(tasks)

# Usage example
tasks = [
    {"id": 1, "priority": "low", "created_at": "2024-01-01"},
    {"id": 2, "priority": "high", "created_at": "2024-01-02"},
]

sorter = TaskSorter(PrioritySortingStrategy())
sorted_tasks = sorter.sort_tasks(tasks)
```

### When to Use Strategy Pattern
- Multiple algorithms for the same task
- Need to switch algorithms at runtime
- Want to avoid conditional statements for algorithm selection

## 2. Factory Pattern

The Factory pattern creates objects without specifying their exact classes. It's useful for creating objects based on certain conditions.

### Example: Data Export Factory

```python
from abc import ABC, abstractmethod
import json
import csv
from typing import Dict, Any, List

class DataExporter(ABC):
    """Abstract base class for data exporters."""
    
    @abstractmethod
    def export(self, data: List[Dict[str, Any]], filename: str) -> None:
        pass

class JSONExporter(DataExporter):
    """Export data to JSON format."""
    
    def export(self, data: List[Dict[str, Any]], filename: str) -> None:
        with open(filename, 'w') as file:
            json.dump(data, file, indent=2)

class CSVExporter(DataExporter):
    """Export data to CSV format."""
    
    def export(self, data: List[Dict[str, Any]], filename: str) -> None:
        if not data:
            return
        
        with open(filename, 'w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)

class ExporterFactory:
    """Factory class for creating data exporters."""
    
    @staticmethod
    def create_exporter(format_type: str) -> DataExporter:
        exporters = {
            'json': JSONExporter,
            'csv': CSVExporter,
        }
        
        exporter_class = exporters.get(format_type.lower())
        if not exporter_class:
            raise ValueError(f"Unsupported format: {format_type}")
        
        return exporter_class()

# Usage example
factory = ExporterFactory()
exporter = factory.create_exporter('json')
exporter.export(tasks, 'tasks.json')
```

### When to Use Factory Pattern
- Creating objects based on user input or configuration
- Need to encapsulate object creation logic
- Want to make object creation more flexible

## 3. Observer Pattern

The Observer pattern allows objects to notify other objects about changes in their state. It's useful for implementing event-driven architectures.

### Example: Task Status Notifications

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class Observer(ABC):
    """Abstract observer interface."""
    
    @abstractmethod
    def update(self, subject: 'Subject', event: str, data: Dict[str, Any]) -> None:
        pass

class Subject(ABC):
    """Abstract subject interface."""
    
    def __init__(self):
        self._observers: List[Observer] = []
    
    def attach(self, observer: Observer) -> None:
        self._observers.append(observer)
    
    def detach(self, observer: Observer) -> None:
        self._observers.remove(observer)
    
    def notify(self, event: str, data: Dict[str, Any]) -> None:
        for observer in self._observers:
            observer.update(self, event, data)

class TaskNotifier(Observer):
    """Observer that handles task notifications."""
    
    def update(self, subject: Subject, event: str, data: Dict[str, Any]) -> None:
        if event == "task_completed":
            print(f"Task '{data['description']}' has been completed!")
        elif event == "task_added":
            print(f"New task added: '{data['description']}'")

class TaskLogger(Observer):
    """Observer that logs task events."""
    
    def update(self, subject: Subject, event: str, data: Dict[str, Any]) -> None:
        with open('task_log.txt', 'a') as file:
            file.write(f"{event}: {data}\\n")

class ObservableTaskManager(Subject):
    """Task manager that notifies observers of changes."""
    
    def __init__(self):
        super().__init__()
        self._tasks: List[Dict[str, Any]] = []
        self._next_id = 1
    
    def add_task(self, description: str) -> int:
        task = {
            "id": self._next_id,
            "description": description,
            "completed": False
        }
        self._tasks.append(task)
        self._next_id += 1
        
        self.notify("task_added", task)
        return task["id"]
    
    def complete_task(self, task_id: int) -> None:
        for task in self._tasks:
            if task["id"] == task_id:
                task["completed"] = True
                self.notify("task_completed", task)
                break

# Usage example
task_manager = ObservableTaskManager()
notifier = TaskNotifier()
logger = TaskLogger()

task_manager.attach(notifier)
task_manager.attach(logger)

task_id = task_manager.add_task("Learn design patterns")
task_manager.complete_task(task_id)
```

### When to Use Observer Pattern
- Need to notify multiple objects about state changes
- Want to decouple objects that depend on each other
- Building event-driven systems

## 4. Singleton Pattern

The Singleton pattern ensures that a class has only one instance and provides global access to it.

### Example: Configuration Manager

```python
import threading
from typing import Dict, Any

class ConfigManager:
    """Singleton configuration manager."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the configuration."""
        self._config: Dict[str, Any] = {
            "app_name": "AI-Assisted Development Project",
            "version": "1.0.0",
            "debug": False,
            "data_directory": "data"
        }
    
    def get(self, key: str) -> Any:
        """Get a configuration value."""
        return self._config.get(key)
    
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        self._config[key] = value
    
    def update(self, config: Dict[str, Any]) -> None:
        """Update multiple configuration values."""
        self._config.update(config)

# Usage example
config1 = ConfigManager()
config2 = ConfigManager()

print(config1 is config2)  # True - same instance

config1.set("debug", True)
print(config2.get("debug"))  # True - shared state
```

### When to Use Singleton Pattern
- Need exactly one instance of a class
- Global access to a shared resource
- Configuration management
- Logging systems

**Note:** Use Singleton sparingly as it can make testing difficult and create tight coupling.

## 5. Command Pattern

The Command pattern encapsulates requests as objects, allowing you to parameterize clients with different requests, queue operations, and support undo functionality.

### Example: Task Commands with Undo

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class Command(ABC):
    """Abstract command interface."""
    
    @abstractmethod
    def execute(self) -> None:
        pass
    
    @abstractmethod
    def undo(self) -> None:
        pass

class AddTaskCommand(Command):
    """Command to add a task."""
    
    def __init__(self, task_manager: 'TaskManager', description: str):
        self.task_manager = task_manager
        self.description = description
        self.task_id = None
    
    def execute(self) -> None:
        self.task_id = self.task_manager.add_task(self.description)
    
    def undo(self) -> None:
        if self.task_id is not None:
            self.task_manager.delete_task(self.task_id)

class CompleteTaskCommand(Command):
    """Command to complete a task."""
    
    def __init__(self, task_manager: 'TaskManager', task_id: int):
        self.task_manager = task_manager
        self.task_id = task_id
        self.was_completed = False
    
    def execute(self) -> None:
        task = self.task_manager.get_task(self.task_id)
        self.was_completed = task["completed"]
        self.task_manager.complete_task(self.task_id)
    
    def undo(self) -> None:
        task = self.task_manager.get_task(self.task_id)
        task["completed"] = self.was_completed

class TaskInvoker:
    """Invoker class that executes commands and maintains history."""
    
    def __init__(self):
        self.command_history: List[Command] = []
    
    def execute_command(self, command: Command) -> None:
        command.execute()
        self.command_history.append(command)
    
    def undo_last_command(self) -> None:
        if self.command_history:
            last_command = self.command_history.pop()
            last_command.undo()

# Usage example
# task_manager = TaskManager()  # Assume this exists
# invoker = TaskInvoker()

# add_cmd = AddTaskCommand(task_manager, "Learn command pattern")
# invoker.execute_command(add_cmd)

# invoker.undo_last_command()  # Undoes the add task
```

### When to Use Command Pattern
- Need to parameterize objects with operations
- Want to queue, log, or undo operations
- Need to support macro recording
- Want to decouple request sender from receiver

## Implementation Tips

### 1. Start Simple
Begin with basic implementations and add complexity as needed. Don't over-engineer from the start.

### 2. Use AI Assistance Effectively
When working with AI to implement patterns:
- Ask for explanations of when to use each pattern
- Request code reviews for pattern implementations
- Ask for help refactoring existing code to use patterns

### 3. Test Your Patterns
Write unit tests for your pattern implementations:
```python
def test_strategy_pattern():
    tasks = [{"priority": "low"}, {"priority": "high"}]
    sorter = TaskSorter(PrioritySortingStrategy())
    sorted_tasks = sorter.sort_tasks(tasks)
    assert sorted_tasks[0]["priority"] == "high"
```

### 4. Document Your Decisions
In your AI edit log, document:
- Why you chose a particular pattern
- How the pattern improved your code
- Any challenges you faced implementing it

## Anti-Patterns to Avoid

### 1. Overusing Patterns
Don't force patterns where they're not needed. Simple code is often better than complex patterns.

### 2. Pattern Soup
Don't use multiple patterns in the same class unless there's a clear benefit.

### 3. Ignoring SOLID Principles
Patterns should support SOLID principles, not violate them.

## Practice Exercises

1. **Implement a Factory Pattern** for creating different types of data validators
2. **Use the Observer Pattern** to create a notification system for your application
3. **Apply the Strategy Pattern** to implement different sorting or filtering algorithms
4. **Create a Command Pattern** implementation for user actions with undo functionality

## Further Reading

- "Design Patterns: Elements of Reusable Object-Oriented Software" by Gang of Four
- "Head First Design Patterns" by Eric Freeman
- Python-specific design pattern resources and examples

Remember: The goal is to write maintainable, readable code. Use patterns to achieve this, not to show off your knowledge of patterns!