"""Main task scheduler implementation."""

import asyncio
import threading
from datetime import datetime, timedelta
from typing import Any, Callable, Awaitable

from .cron_parser import CronParser, NaturalLanguageParser, ParsedSchedule
from .job_store import Job, JobStore, JobStatus, RetryPolicy, ScheduleType
from .dag_executor import DAGExecutor, TaskNode
from .windows_bridge import WindowsTaskBridge


class TaskScheduler:
    """
    Advanced intelligent task scheduler.

    Features:
    - Natural language to cron parsing
    - SQLite-backed persistent job registry
    - DAG-based dependency-aware execution
    - Smart rescheduling based on system state
    - Hybrid Windows Task Scheduler bridge
    - User confirmation workflow
    """

    def __init__(
        self,
        db_path: str | None = None,
        check_interval: int = 30,
        max_concurrent_jobs: int = 4,
    ):
        self.job_store = JobStore(db_path=db_path)
        self.cron_parser = CronParser()
        self.nl_parser = NaturalLanguageParser()
        self.windows_bridge = WindowsTaskBridge()
        self.dag_executor = DAGExecutor(max_concurrent=max_concurrent_jobs)

        self.check_interval = check_interval
        self.max_concurrent_jobs = max_concurrent_jobs

        # Callbacks
        self._on_job_start: Callable[[Job], None] | None = None
        self._on_job_complete: Callable[[Job, Any], None] | None = None
        self._on_job_fail: Callable[[Job, Exception], None] | None = None
        self._on_job_due: Callable[[Job], Awaitable[bool]] | None = None

        # State
        self._running = False
        self._scheduler_task: asyncio.Task | None = None
        self._lock = threading.Lock()

    def set_on_job_start(self, callback: Callable[[Job], None]) -> None:
        """Set callback for job start."""
        self._on_job_start = callback

    def set_on_job_complete(self, callback: Callable[[Job, Any], None]) -> None:
        """Set callback for job completion."""
        self._on_job_complete = callback

    def set_on_job_fail(self, callback: Callable[[Job, Exception], None]) -> None:
        """Set callback for job failure."""
        self._on_job_fail = callback

    def set_on_job_due(self, callback: Callable[[Job], Awaitable[bool]]) -> None:
        """Set async callback to check if job should run (for user confirmation)."""
        self._on_job_due = callback

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                await self._check_and_run_jobs()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                # Log error and continue
                await asyncio.sleep(self.check_interval)

    async def _check_and_run_jobs(self) -> None:
        """Check for due jobs and execute them."""
        due_jobs = self.job_store.get_ready_jobs()

        for job in due_jobs:
            # Check if job is due
            if job.next_run and job.next_run > datetime.now():
                continue

            # User confirmation check
            if self._on_job_due:
                should_run = await self._on_job_due(job)
                if not should_run:
                    continue

            # Execute the job
            asyncio.create_task(self._execute_job(job))

    async def _execute_job(self, job: Job) -> None:
        """Execute a single job."""
        # Update job status
        job.status = JobStatus.RUNNING
        job.last_run = datetime.now()
        job.attempt_count += 1
        self.job_store.update(job)

        # Fire start callback
        if self._on_job_start:
            self._on_job_start(job)

        try:
            # Execute based on task type
            if job.task_type == "agent_task":
                result = await self._execute_agent_task(job)
            elif job.task_type == "script":
                result = await self._execute_script_task(job)
            elif job.task_type == "dag":
                result = await self._execute_dag_task(job)
            else:
                result = {"error": f"Unknown task type: {job.task_type}"}

            # Success
            job.status = JobStatus.COMPLETED
            job.last_result = result
            self.job_store.update(job)

            # Calculate next run
            self._update_next_run(job)
            self.job_store.update(job)

            if self._on_job_complete:
                self._on_job_complete(job, result)

        except Exception as e:
            # Handle failure
            job.status = JobStatus.FAILED
            job.last_result = {"error": str(e)}
            self.job_store.update(job)

            # Retry logic
            if job.attempt_count < job.retry_policy.max_attempts:
                delay = self._calculate_retry_delay(job)
                job.status = JobStatus.PENDING
                job.next_run = datetime.now() + timedelta(seconds=delay)
                self.job_store.update(job)

            if self._on_job_fail:
                self._on_job_fail(job, e)

    async def _execute_agent_task(self, job: Job) -> dict:
        """Execute an agent task."""
        # This would integrate with the agent
        # For now, return a placeholder
        return {
            "status": "executed",
            "job_id": job.id,
            "task": job.payload,
        }

    async def _execute_script_task(self, job: Job) -> dict:
        """Execute a script task."""
        # This would execute the script
        return {
            "status": "executed",
            "job_id": job.id,
        }

    async def _execute_dag_task(self, job: Job) -> dict:
        """Execute a DAG task."""
        # Build and execute the DAG
        self.dag_executor.reset()
        # Add nodes based on job.payload
        status = self.dag_executor.get_status()
        return {"status": "executed", "dag_status": status}

    def _calculate_retry_delay(self, job: Job) -> int:
        """Calculate the delay before retry."""
        delay = job.retry_policy.initial_delay_seconds * (
            job.retry_policy.backoff_multiplier ** (job.attempt_count - 1)
        )
        return min(delay, job.retry_policy.max_delay_seconds)

    def _update_next_run(self, job: Job) -> None:
        """Calculate and set the next run time."""
        if job.schedule_type == ScheduleType.ONE_TIME:
            job.next_run = None
            return

        try:
            if job.schedule_type == ScheduleType.CRON:
                parsed = self.cron_parser.parse(job.schedule_expr)
                if parsed.next_runs:
                    job.next_run = parsed.next_runs[0]
            elif job.schedule_type == ScheduleType.INTERVAL:
                # Parse interval expression like "PT5M" or "5 minutes"
                interval_seconds = self._parse_interval(job.schedule_expr)
                if interval_seconds:
                    job.next_run = datetime.now() + timedelta(seconds=interval_seconds)

        except Exception:
            # Keep current next_run on error
            pass

    def _parse_interval(self, expr: str) -> int | None:
        """Parse an interval expression."""
        expr = expr.lower().strip()

        # ISO 8601 duration format
        if expr.startswith("pt"):
            return self._parse_iso_duration(expr)

        # Natural language
        import re

        match = re.match(r"(\d+)\s*(second|minute|hour|day|week)s?", expr)
        if match:
            value = int(match.group(1))
            unit = match.group(2)

            multipliers = {
                "second": 1,
                "minute": 60,
                "hour": 3600,
                "day": 86400,
                "week": 604800,
            }
            return value * multipliers.get(unit, 60)

        return None

    def _parse_iso_duration(self, duration: str) -> int | None:
        """Parse ISO 8601 duration (e.g., PT5M, PT1H)."""
        import re

        total_seconds = 0

        match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration.upper())
        if match:
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
            total_seconds = hours * 3600 + minutes * 60 + seconds

        return total_seconds if total_seconds > 0 else None

    # Public API

    def create_job(
        self,
        name: str,
        schedule: str,
        task_type: str = "agent_task",
        payload: dict | None = None,
        description: str = "",
        timezone: str = "UTC",
        dependencies: list[str] | None = None,
        retry_policy: RetryPolicy | None = None,
        user_tags: list[str] | None = None,
        requires_confirmation: bool = True,
        use_windows_scheduler: bool = False,
    ) -> tuple[Job, ParsedSchedule]:
        """
        Create a new scheduled job.

        Args:
            name: Human-readable job name
            schedule: Natural language or cron schedule
            task_type: Type of task (agent_task, script, dag)
            payload: Task parameters
            description: Job description
            timezone: Timezone for scheduling
            dependencies: Job IDs this depends on
            retry_policy: Retry configuration
            user_tags: Tags for filtering
            requires_confirmation: Whether to require user confirmation
            use_windows_scheduler: Use Windows Task Scheduler

        Returns:
            Tuple of (Job, ParsedSchedule) for confirmation
        """
        # Parse schedule
        try:
            parsed = self.cron_parser.parse(schedule)
        except ValueError:
            parsed = self.nl_parser.parse(schedule)

        job = Job(
            id="",  # Will be assigned
            name=name,
            description=description,
            task_type=task_type,
            schedule_type=ScheduleType.CRON,
            schedule_expr=parsed.cron_expr,
            timezone=timezone,
            payload=payload or {},
            dependencies=dependencies or [],
            status=JobStatus.PENDING,
            next_run=parsed.next_runs[0] if parsed.next_runs else None,
            retry_policy=retry_policy or RetryPolicy(),
            user_tags=user_tags or [],
            use_windows_scheduler=use_windows_scheduler,
        )

        job = self.job_store.create(job)
        return job, parsed

    def preview_job(self, schedule: str) -> ParsedSchedule:
        """
        Preview what a schedule expression means.

        Args:
            schedule: Natural language or cron schedule

        Returns:
            ParsedSchedule with human-readable description
        """
        try:
            return self.cron_parser.parse(schedule)
        except ValueError:
            return self.nl_parser.parse(schedule)

    def get_job_summary(self, job: Job) -> str:
        """Get a human-readable summary of a job."""
        schedule = job.get_human_readable_schedule()

        summary = f"**{job.name}**\n"
        summary += f"- Schedule: {schedule}\n"
        summary += f"- Status: {job.status.value}\n"

        if job.next_run:
            summary += f"- Next run: {job.next_run.strftime('%Y-%m-%d %H:%M')}\n"

        if job.last_run:
            summary += f"- Last run: {job.last_run.strftime('%Y-%m-%d %H:%M')}\n"

        if job.dependencies:
            summary += f"- Dependencies: {len(job.dependencies)} tasks\n"

        return summary

    def confirm_job(self, job_id: str) -> bool:
        """
        Confirm a pending job to start scheduling.

        Args:
            job_id: Job ID

        Returns:
            True if confirmed successfully
        """
        job = self.job_store.get(job_id)
        if not job:
            return False

        job.status = JobStatus.SCHEDULED
        self.job_store.update(job)

        # Sync with Windows Task Scheduler if needed
        if job.use_windows_scheduler:
            self.windows_bridge.sync_with_job_store(self.job_store)

        return True

    def pause_job(self, job_id: str) -> bool:
        """Pause a scheduled job."""
        job = self.job_store.get(job_id)
        if not job:
            return False

        job.status = JobStatus.PAUSED
        self.job_store.update(job)
        return True

    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job."""
        job = self.job_store.get(job_id)
        if not job:
            return False

        if job.status == JobStatus.PAUSED:
            job.status = JobStatus.SCHEDULED
            self.job_store.update(job)
        return True

    def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        job = self.job_store.get(job_id)
        if not job:
            return False

        # Remove from Windows scheduler if needed
        if job.use_windows_scheduler:
            task_name = f"job_{job.id[:8]}"
            self.windows_bridge.delete_task(task_name)

        return self.job_store.delete(job_id)

    def list_jobs(
        self,
        status: JobStatus | None = None,
        tags: list[str] | None = None,
    ) -> list[Job]:
        """List jobs with optional filtering."""
        return self.job_store.list(status=status, tags=tags)

    def get_upcoming_jobs(self, hours: int = 24) -> list[tuple[Job, datetime]]:
        """Get jobs scheduled to run in the next N hours."""
        cutoff = datetime.now() + timedelta(hours=hours)
        jobs = self.job_store.list(status=JobStatus.SCHEDULED)

        upcoming = []
        for job in jobs:
            if job.next_run and job.next_run <= cutoff:
                upcoming.append((job, job.next_run))

        upcoming.sort(key=lambda x: x[1])
        return upcoming