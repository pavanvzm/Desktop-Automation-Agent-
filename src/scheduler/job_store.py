"""SQLite-backed job store for persistent job registry."""

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class JobStatus(str, Enum):
    """Status of a scheduled job."""

    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class ScheduleType(str, Enum):
    """Type of job schedule."""

    CRON = "cron"
    INTERVAL = "interval"
    ONE_TIME = "one_time"
    DAG = "dag"  # Dependency-based (DAG node)


@dataclass
class RetryPolicy:
    """Retry policy for failed jobs."""

    max_attempts: int = 3
    initial_delay_seconds: int = 60
    backoff_multiplier: float = 2.0
    max_delay_seconds: int = 3600

    def to_dict(self) -> dict:
        return {
            "max_attempts": self.max_attempts,
            "initial_delay_seconds": self.initial_delay_seconds,
            "backoff_multiplier": self.backoff_multiplier,
            "max_delay_seconds": self.max_delay_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RetryPolicy":
        return cls(
            max_attempts=data.get("max_attempts", 3),
            initial_delay_seconds=data.get("initial_delay_seconds", 60),
            backoff_multiplier=data.get("backoff_multiplier", 2.0),
            max_delay_seconds=data.get("max_delay_seconds", 3600),
        )


@dataclass
class Job:
    """Represents a scheduled job."""

    id: str
    name: str
    description: str = ""
    task_type: str = "agent_task"  # agent_task, script, webhook, etc.

    # Scheduling
    schedule_type: ScheduleType = ScheduleType.CRON
    schedule_expr: str = ""  # Cron expression or ISO 8601 interval
    timezone: str = "UTC"

    # Execution
    payload: dict[str, Any] = field(default_factory=dict)  # Task parameters
    dependencies: list[str] = field(default_factory=list)  # Job IDs this depends on

    # State
    status: JobStatus = JobStatus.PENDING
    last_run: datetime | None = None
    next_run: datetime | None = None
    last_result: dict | None = None
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    attempt_count: int = 0

    # Metadata
    user_tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    created_by: str = "system"

    # Windows Task Scheduler integration
    windows_task_name: str | None = None
    use_windows_scheduler: bool = False

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "task_type": self.task_type,
            "schedule_type": self.schedule_type.value,
            "schedule_expr": self.schedule_expr,
            "timezone": self.timezone,
            "payload": self.payload,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "last_result": self.last_result,
            "retry_policy": self.retry_policy.to_dict(),
            "attempt_count": self.attempt_count,
            "user_tags": self.user_tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by,
            "windows_task_name": self.windows_task_name,
            "use_windows_scheduler": self.use_windows_scheduler,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        retry_policy = RetryPolicy()
        if "retry_policy" in data and data["retry_policy"]:
            retry_policy = RetryPolicy.from_dict(data["retry_policy"])

        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            task_type=data.get("task_type", "agent_task"),
            schedule_type=ScheduleType(data.get("schedule_type", "cron")),
            schedule_expr=data.get("schedule_expr", ""),
            timezone=data.get("timezone", "UTC"),
            payload=data.get("payload", {}),
            dependencies=data.get("dependencies", []),
            status=JobStatus(data.get("status", "pending")),
            last_run=datetime.fromisoformat(data["last_run"]) if data.get("last_run") else None,
            next_run=datetime.fromisoformat(data["next_run"]) if data.get("next_run") else None,
            last_result=data.get("last_result"),
            retry_policy=retry_policy,
            attempt_count=data.get("attempt_count", 0),
            user_tags=data.get("user_tags", []),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
            created_by=data.get("created_by", "system"),
            windows_task_name=data.get("windows_task_name"),
            use_windows_scheduler=data.get("use_windows_scheduler", False),
        )

    def get_human_readable_schedule(self) -> str:
        """Get a human-readable description of the schedule."""
        if self.schedule_type == ScheduleType.CRON:
            return _cron_to_human(self.schedule_expr)
        elif self.schedule_type == ScheduleType.INTERVAL:
            return f"Every {self.schedule_expr}"
        elif self.schedule_type == ScheduleType.ONE_TIME:
            if self.next_run:
                return f"Once at {self.next_run.strftime('%Y-%m-%d %H:%M')}"
            return "One-time (no scheduled time)"
        elif self.schedule_type == ScheduleType.DAG:
            return f"DAG node with {len(self.dependencies)} dependencies"
        return "Unknown schedule"


def _cron_to_human(expr: str) -> str:
    """Convert a cron expression to human-readable text."""
    parts = expr.split()
    if len(parts) != 5:
        return expr

    minute, hour, day, month, weekday = parts

    # Common patterns
    if minute == "0" and hour == "9" and day == "*" and month == "*" and weekday == "1-5":
        return "Every weekday at 9:00 AM"
    if minute == "0" and hour == "8" and day == "*" and month == "*" and weekday == "1":
        return "Every Monday at 8:00 AM"
    if minute == "0" and hour == "0" and day == "*" and month == "*" and weekday == "*":
        return "Every day at midnight"
    if minute.startswith("*/"):
        return f"Every {minute[2:]} minutes"
    if hour == "*" and minute != "*":
        return f"Every hour at minute {minute}"
    if day == "*" and month == "*" and weekday == "*":
        return f"Every day at {hour}:{minute.zfill(2)}"

    return expr


class JobStore:
    """
    SQLite-backed persistent job registry.

    Provides CRUD operations for scheduled jobs with full
    metadata, retry policies, and dependency tracking.
    """

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = Path.home() / ".win11-omniagent" / "scheduler.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    task_type TEXT,
                    schedule_type TEXT,
                    schedule_expr TEXT,
                    timezone TEXT DEFAULT 'UTC',
                    payload TEXT,
                    dependencies TEXT,
                    status TEXT,
                    last_run TEXT,
                    next_run TEXT,
                    last_result TEXT,
                    retry_policy TEXT,
                    attempt_count INTEGER DEFAULT 0,
                    user_tags TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    created_by TEXT,
                    windows_task_name TEXT,
                    use_windows_scheduler INTEGER DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS job_runs (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    status TEXT,
                    result TEXT,
                    error TEXT,
                    FOREIGN KEY (job_id) REFERENCES jobs(id)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_next_run ON jobs(next_run)
            """)
            conn.commit()

    def create(self, job: Job) -> Job:
        """Create a new job."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO jobs (
                    id, name, description, task_type, schedule_type, schedule_expr,
                    timezone, payload, dependencies, status, last_run, next_run,
                    last_result, retry_policy, attempt_count, user_tags, created_at,
                    updated_at, created_by, windows_task_name, use_windows_scheduler
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.name,
                    job.description,
                    job.task_type,
                    job.schedule_type.value,
                    job.schedule_expr,
                    job.timezone,
                    json.dumps(job.payload),
                    json.dumps(job.dependencies),
                    job.status.value,
                    job.last_run.isoformat() if job.last_run else None,
                    job.next_run.isoformat() if job.next_run else None,
                    json.dumps(job.last_result) if job.last_result else None,
                    json.dumps(job.retry_policy.to_dict()),
                    job.attempt_count,
                    json.dumps(job.user_tags),
                    job.created_at.isoformat(),
                    job.updated_at.isoformat(),
                    job.created_by,
                    job.windows_task_name,
                    1 if job.use_windows_scheduler else 0,
                ),
            )
            conn.commit()
        return job

    def get(self, job_id: str) -> Job | None:
        """Get a job by ID."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_job(row)
        return None

    def update(self, job: Job) -> Job:
        """Update an existing job."""
        job.updated_at = datetime.now()
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE jobs SET
                    name = ?, description = ?, task_type = ?, schedule_type = ?,
                    schedule_expr = ?, timezone = ?, payload = ?, dependencies = ?,
                    status = ?, last_run = ?, next_run = ?, last_result = ?,
                    retry_policy = ?, attempt_count = ?, user_tags = ?, updated_at = ?,
                    created_by = ?, windows_task_name = ?, use_windows_scheduler = ?
                WHERE id = ?
                """,
                (
                    job.name,
                    job.description,
                    job.task_type,
                    job.schedule_type.value,
                    job.schedule_expr,
                    job.timezone,
                    json.dumps(job.payload),
                    json.dumps(job.dependencies),
                    job.status.value,
                    job.last_run.isoformat() if job.last_run else None,
                    job.next_run.isoformat() if job.next_run else None,
                    json.dumps(job.last_result) if job.last_result else None,
                    json.dumps(job.retry_policy.to_dict()),
                    job.attempt_count,
                    json.dumps(job.user_tags),
                    job.updated_at.isoformat(),
                    job.created_by,
                    job.windows_task_name,
                    1 if job.use_windows_scheduler else 0,
                    job.id,
                ),
            )
            conn.commit()
        return job

    def delete(self, job_id: str) -> bool:
        """Delete a job."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
        return deleted

    def list(
        self,
        status: JobStatus | None = None,
        tags: list[str] | None = None,
        limit: int = 100,
    ) -> list[Job]:
        """List jobs with optional filtering."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM jobs WHERE 1=1"
            params = []

            if status:
                query += " AND status = ?"
                params.append(status.value)

            if tags:
                for tag in tags:
                    query += " AND user_tags LIKE ?"
                    params.append(f"%{tag}%")

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            return [self._row_to_job(row) for row in cursor.fetchall()]

    def get_due_jobs(self, before_time: datetime | None = None) -> list[Job]:
        """Get all jobs that are due to run."""
        now = before_time or datetime.now()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM jobs
                WHERE status IN ('scheduled', 'pending')
                AND next_run IS NOT NULL
                AND next_run <= ?
                ORDER BY next_run ASC
                """,
                (now.isoformat(),),
            )
            return [self._row_to_job(row) for row in cursor.fetchall()]

    def get_ready_jobs(self) -> list[Job]:
        """Get jobs that are ready to run (dependencies satisfied)."""
        due_jobs = self.get_due_jobs()
        ready = []

        for job in due_jobs:
            if not job.dependencies:
                ready.append(job)
            else:
                # Check if all dependencies are completed
                all_complete = True
                for dep_id in job.dependencies:
                    dep = self.get(dep_id)
                    if not dep or dep.status != JobStatus.COMPLETED:
                        all_complete = False
                        break
                if all_complete:
                    ready.append(job)

        return ready

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        """Convert a database row to a Job object."""
        return Job.from_dict({
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "task_type": row["task_type"],
            "schedule_type": row["schedule_type"],
            "schedule_expr": row["schedule_expr"],
            "timezone": row["timezone"],
            "payload": json.loads(row["payload"]) if row["payload"] else {},
            "dependencies": json.loads(row["dependencies"]) if row["dependencies"] else [],
            "status": row["status"],
            "last_run": row["last_run"],
            "next_run": row["next_run"],
            "last_result": json.loads(row["last_result"]) if row["last_result"] else None,
            "retry_policy": json.loads(row["retry_policy"]) if row["retry_policy"] else {},
            "attempt_count": row["attempt_count"],
            "user_tags": json.loads(row["user_tags"]) if row["user_tags"] else [],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "created_by": row["created_by"],
            "windows_task_name": row["windows_task_name"],
            "use_windows_scheduler": bool(row["use_windows_scheduler"]),
        })