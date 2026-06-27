from __future__ import annotations
"""
Win11-OmniAgent Task Scheduler Package

Advanced intelligent scheduler with:
- Natural language to cron parsing
- SQLite-backed job registry
- DAG-based dependency-aware execution
- Hybrid Windows Task Scheduler bridge
- Smart rescheduling based on system state
"""

from .scheduler import TaskScheduler, Job, JobStatus, ScheduleType
from .cron_parser import CronParser, NaturalLanguageParser
from .job_store import JobStore
from .dag_executor import DAGExecutor, TaskNode, TaskEdge
from .windows_bridge import WindowsTaskBridge

__all__ = [
    "TaskScheduler",
    "Job",
    "JobStatus",
    "ScheduleType",
    "CronParser",
    "NaturalLanguageParser",
    "JobStore",
    "DAGExecutor",
    "TaskNode",
    "TaskEdge",
    "WindowsTaskBridge",
]
