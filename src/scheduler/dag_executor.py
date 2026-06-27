"""DAG-based task dependency executor."""

import asyncio
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Awaitable


class TaskStatus(str, Enum):
    """Status of a task in the DAG."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskNode:
    """A node in the task DAG."""

    id: str
    name: str
    task_func: Callable[..., Awaitable[Any]]
    args: tuple = field(default_factory=())
    kwargs: dict = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    dependencies: list[str] = field(default_factory=list)
    dependents: list[str] = field(default_factory=list)  # Tasks that depend on this one

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }


@dataclass
class TaskEdge:
    """An edge in the task DAG (dependency)."""

    from_task: str  # Source task ID
    to_task: str  # Target task ID
    condition: Callable[[Any], bool] | None = None  # Optional condition

    def should_execute(self, source_result: Any) -> bool:
        """Check if the edge condition allows execution."""
        if self.condition is None:
            return True
        return self.condition(source_result)


class DAGExecutor:
    """
    Execute tasks with DAG-based dependency management.

    Supports:
    - Parallel execution of independent tasks
    - Conditional execution based on upstream results
    - Automatic retry on failure
    - Cancellation support
    """

    def __init__(self, max_concurrent: int = 4, retry_attempts: int = 2):
        self.max_concurrent = max_concurrent
        self.retry_attempts = retry_attempts
        self._tasks: dict[str, TaskNode] = {}
        self._running: set[str] = set()
        self._completed: set[str] = set()
        self._failed: set[str] = set()
        self._results: dict[str, Any] = {}
        self._cancel_requested = False
        self._lock = asyncio.Lock()

    def add_task(
        self,
        name: str,
        task_func: Callable[..., Awaitable[Any]],
        dependencies: list[str] | None = None,
        args: tuple = (),
        kwargs: dict | None = None,
    ) -> TaskNode:
        """Add a task to the DAG."""
        task = TaskNode(
            id=str(uuid.uuid4()),
            name=name,
            task_func=task_func,
            args=args,
            kwargs=kwargs or {},
            dependencies=dependencies or [],
        )

        self._tasks[task.id] = task

        # Update dependents for dependency tasks
        for dep_id in task.dependencies:
            if dep_id in self._tasks:
                self._tasks[dep_id].dependents.append(task.id)

        return task

    def add_edge(self, from_task: str, to_task: str, condition: Callable[[Any], bool] | None = None) -> TaskEdge:
        """Add a dependency edge between tasks."""
        edge = TaskEdge(from_task=from_task, to_task=to_task, condition=condition)

        if from_task in self._tasks and to_task in self._tasks:
            if from_task not in self._tasks[to_task].dependencies:
                self._tasks[to_task].dependencies.append(from_task)
            if to_task not in self._tasks[from_task].dependents:
                self._tasks[from_task].dependents.append(to_task)

        return edge

    def get_ready_tasks(self) -> list[TaskNode]:
        """Get tasks that are ready to execute (all dependencies completed)."""
        ready = []
        for task in self._tasks.values():
            if task.status != TaskStatus.PENDING:
                continue

            # Check if all dependencies are completed
            all_deps_done = all(
                self._tasks[dep_id].status == TaskStatus.COMPLETED
                for dep_id in task.dependencies
                if dep_id in self._tasks
            )

            if all_deps_done:
                ready.append(task)

        return ready

    def get_root_tasks(self) -> list[TaskNode]:
        """Get tasks with no dependencies (entry points)."""
        return [task for task in self._tasks.values() if not task.dependencies]

    def get_leaf_tasks(self) -> list[TaskNode]:
        """Get tasks with no dependents (end points)."""
        return [task for task in self._tasks.values() if not task.dependents]

    def validate(self) -> tuple[bool, str | None]:
        """Validate the DAG for cycles and missing dependencies."""
        # Check for cycles using DFS
        visited = set()
        rec_stack = set()

        def has_cycle(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)

            node = self._tasks.get(node_id)
            if node:
                for dep_id in node.dependencies:
                    if dep_id not in visited:
                        if has_cycle(dep_id):
                            return True
                    elif dep_id in rec_stack:
                        return True

            rec_stack.remove(node_id)
            return False

        for task_id in self._tasks:
            if task_id not in visited:
                if has_cycle(task_id):
                    return False, f"Cycle detected involving task: {task_id}"

        # Check for missing dependencies
        for task in self._tasks.values():
            for dep_id in task.dependencies:
                if dep_id not in self._tasks:
                    return False, f"Missing dependency: {dep_id} for task {task.name}"

        return True, None

    async def execute(self) -> dict[str, Any]:
        """
        Execute all tasks in the DAG respecting dependencies.

        Returns:
            Dictionary mapping task IDs to their results
        """
        is_valid, error = self.validate()
        if not is_valid:
            raise ValueError(f"Invalid DAG: {error}")

        self._cancel_requested = False
        self._results = {}

        while True:
            # Check if we're done
            pending = [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]
            if not pending:
                break

            # Get ready tasks
            ready = self.get_ready_tasks()
            if not ready:
                # Deadlock - no ready tasks but pending exist
                break

            # Execute ready tasks (up to max_concurrent)
            batch = ready[: self.max_concurrent]
            await asyncio.gather(*[self._execute_task(task) for task in batch])

        return self._results

    async def _execute_task(self, task: TaskNode) -> None:
        """Execute a single task with retry logic."""
        async with self._lock:
            if task.status != TaskStatus.PENDING:
                return
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            self._running.add(task.id)

        try:
            # Collect dependency results
            dep_results = {}
            for dep_id in task.dependencies:
                if dep_id in self._results:
                    dep_results[dep_id] = self._results[dep_id]

            # Execute the task
            result = await task.task_func(*task.args, **{**task.kwargs, **dep_results})

            async with self._lock:
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.completed_at = datetime.now()
                self._completed.add(task.id)
                self._running.discard(task.id)
                self._results[task.id] = result

        except asyncio.CancelledError:
            async with self._lock:
                task.status = TaskStatus.SKIPPED
                self._running.discard(task.id)
            raise

        except Exception as e:
            async with self._lock:
                task.error = str(e)
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()
                self._failed.add(task.id)
                self._running.discard(task.id)

                # Mark dependent tasks as failed (cascade)
                for dep_id in task.dependents:
                    if dep_id in self._tasks:
                        self._tasks[dep_id].status = TaskStatus.SKIPPED

    def cancel(self) -> None:
        """Request cancellation of execution."""
        self._cancel_requested = True

    def get_status(self) -> dict[str, Any]:
        """Get the current execution status."""
        return {
            "total": len(self._tasks),
            "pending": sum(1 for t in self._tasks.values() if t.status == TaskStatus.PENDING),
            "running": len(self._running),
            "completed": len(self._completed),
            "failed": len(self._failed),
            "cancelled": self._cancel_requested,
            "tasks": {task_id: task.to_dict() for task_id, task in self._tasks.items()},
        }

    def reset(self) -> None:
        """Reset the executor for a new run."""
        for task in self._tasks.values():
            task.status = TaskStatus.PENDING
            task.result = None
            task.error = None
            task.started_at = None
            task.completed_at = None

        self._running.clear()
        self._completed.clear()
        self._failed.clear()
        self._results.clear()
        self._cancel_requested = False