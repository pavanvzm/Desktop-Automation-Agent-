"""Windows Task Scheduler bridge for hybrid execution."""

import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class WindowsTaskInfo:
    """Information about a Windows scheduled task."""

    name: str
    path: str
    state: str
    last_run_time: datetime | None
    next_run_time: datetime | None
    last_result: int | None
    description: str | None


class WindowsTaskBridge:
    """
    Bridge to Windows Task Scheduler for hybrid job execution.

    Provides:
    - Creation of Windows scheduled tasks from job definitions
    - Status synchronization between internal store and Windows
    - Auto-registration of heavy/recurring tasks
    """

    TASK_PREFIX = "Win11-OmniAgent"

    def __init__(self):
        self._cache: dict[str, WindowsTaskInfo] = {}

    def create_task(
        self,
        task_name: str,
        command: str,
        schedule_expr: str,
        description: str = "",
        start_time: str = "09:00",
        days_of_week: list[int] | None = None,
        days_of_month: list[int] | None = None,
    ) -> bool:
        """
        Create a Windows scheduled task.

        Args:
            task_name: Unique name for the task
            command: Command to execute
            schedule_expr: Cron-like expression (converted to Windows format)
            description: Task description
            start_time: Start time (HH:MM format)
            days_of_week: Days of week (0=Sunday, 1=Monday, etc.)
            days_of_month: Days of month (1-31)

        Returns:
            True if successful
        """
        full_name = f"{self.TASK_PREFIX}\\{task_name}"

        # Build the schtasks command
        cmd = [
            "schtasks",
            "/Create",
            "/TN", full_name,
            "/TR", command,
            "/SC", self._convert_schedule_type(schedule_expr),
            "/ST", start_time,
            "/F",  # Force overwrite
        ]

        if days_of_week:
            days_str = ",".join(self._day_index_to_name(d) for d in days_of_week)
            cmd.extend(["/D", days_str])

        if days_of_month:
            days_str = ",".join(str(d) for d in days_of_month)
            cmd.extend(["/D", days_str])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0
        except Exception:
            return False

    def delete_task(self, task_name: str) -> bool:
        """Delete a Windows scheduled task."""
        full_name = f"{self.TASK_PREFIX}\\{task_name}"

        try:
            result = subprocess.run(
                ["schtasks", "/Delete", "/TN", full_name, "/F"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if full_name in self._cache:
                del self._cache[full_name]
            return result.returncode == 0
        except Exception:
            return False

    def get_task_status(self, task_name: str) -> WindowsTaskInfo | None:
        """Get the status of a Windows scheduled task."""
        full_name = f"{self.TASK_PREFIX}\\{task_name}"

        # Check cache first
        if full_name in self._cache:
            return self._cache[full_name]

        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/TN", full_name, "/XML", "ONE"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                info = self._parse_task_xml(result.stdout, full_name)
                self._cache[full_name] = info
                return info

        except Exception:
            pass

        return None

    def list_tasks(self) -> list[WindowsTaskInfo]:
        """List all Win11-OmniAgent tasks."""
        tasks = []

        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/TN", f"{self.TASK_PREFIX}\\*", "/FO", "LIST", "/V"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                tasks = self._parse_task_list(result.stdout)

        except Exception:
            pass

        return tasks

    def run_task(self, task_name: str) -> bool:
        """Manually trigger a Windows scheduled task."""
        full_name = f"{self.TASK_PREFIX}\\{task_name}"

        try:
            result = subprocess.run(
                ["schtasks", "/Run", "/TN", full_name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0
        except Exception:
            return False

    def enable_task(self, task_name: str, enabled: bool = True) -> bool:
        """Enable or disable a Windows scheduled task."""
        full_name = f"{self.TASK_PREFIX}\\{task_name}"
        action = "/Enable" if enabled else "/Disable"

        try:
            result = subprocess.run(
                ["schtasks", "/Change", "/TN", full_name, action],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _convert_schedule_type(self, cron_expr: str) -> str:
        """Convert cron expression to Windows schedule type."""
        parts = cron_expr.split()
        if len(parts) != 5:
            return "DAILY"

        minute, hour, day, month, dow = parts

        # Determine schedule type
        if dow != "*" and day == "*":
            return "WEEKLY"
        elif day != "*":
            return "MONTHLY"
        else:
            return "DAILY"

    def _day_index_to_name(self, day: int) -> str:
        """Convert day index to Windows day name."""
        days = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
        return days[day % 7]

    def _parse_task_xml(self, xml_content: str, task_name: str) -> WindowsTaskInfo:
        """Parse Windows task XML output."""
        try:
            root = ET.fromstring(xml_content)

            # Extract task info
            name = task_name.split("\\")[-1]
            path = "\\".join(task_name.split("\\")[:-1])

            # Find task state
            ns = {"task": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
            state_elem = root.find(".//task:State", ns)
            state = state_elem.text if state_elem is not None else "Unknown"

            # Find last run time
            last_run = None
            last_run_elem = root.find(".//task:LastRunTime", ns)
            if last_run_elem is not None and last_run_elem.text:
                try:
                    last_run = datetime.fromisoformat(last_run_elem.text.replace("Z", "+00:00"))
                except ValueError:
                    pass

            # Find next run time
            next_run = None
            next_run_elem = root.find(".//task:NextRunTime", ns)
            if next_run_elem is not None and next_run_elem.text:
                try:
                    next_run = datetime.fromisoformat(next_run_elem.text.replace("Z", "+00:00"))
                except ValueError:
                    pass

            # Find last result
            last_result = None
            result_elem = root.find(".//task:LastTaskResult", ns)
            if result_elem is not None and result_elem.text:
                last_result = int(result_elem.text)

            # Find description
            description = None
            desc_elem = root.find(".//task:Description", ns)
            if desc_elem is not None:
                description = desc_elem.text

            return WindowsTaskInfo(
                name=name,
                path=path,
                state=state,
                last_run_time=last_run,
                next_run_time=next_run,
                last_result=last_result,
                description=description,
            )

        except Exception:
            return WindowsTaskInfo(
                name=task_name,
                path="",
                state="Unknown",
                last_run_time=None,
                next_run_time=None,
                last_result=None,
                description=None,
            )

    def _parse_task_list(self, output: str) -> list[WindowsTaskInfo]:
        """Parse schtasks /LIST output."""
        tasks = []
        current_task = {}

        for line in output.split("\n"):
            line = line.strip()

            if line.startswith("TaskName:"):
                if current_task:
                    tasks.append(WindowsTaskInfo(**current_task))
                current_task = {"name": line.split(":", 1)[1].strip()}

            elif line.startswith("Status:") and current_task:
                current_task["state"] = line.split(":", 1)[1].strip()

        if current_task:
            tasks.append(WindowsTaskInfo(**current_task))

        return tasks

    def sync_with_job_store(self, job_store: "JobStore") -> dict[str, Any]:
        """
        Synchronize Windows tasks with the job store.

        Creates Windows tasks for jobs that need them and
        removes orphaned Windows tasks.
        """
        results = {"created": [], "deleted": [], "updated": [], "errors": []}

        # Get all jobs that should use Windows scheduler
        windows_jobs = [
            job for job in job_store.list()
            if job.use_windows_scheduler and job.status.value in ["scheduled", "pending"]
        ]

        # Get existing Windows tasks
        existing_tasks = {t.name: t for t in self.list_tasks()}

        # Create or update tasks
        for job in windows_jobs:
            task_name = f"job_{job.id[:8]}"

            if task_name not in existing_tasks:
                # Create new task
                success = self.create_task(
                    task_name=task_name,
                    command=self._build_command(job),
                    schedule_expr=job.schedule_expr,
                    description=job.description,
                )
                if success:
                    results["created"].append(job.id)
                else:
                    results["errors"].append(f"Failed to create task for job {job.id}")

        # Clean up orphaned tasks
        job_ids = {f"job_{j.id[:8]}" for j in windows_jobs}
        for task_name in existing_tasks:
            if task_name not in job_ids:
                self.delete_task(task_name)
                results["deleted"].append(task_name)

        return results

    def _build_command(self, job: "Job") -> str:
        """Build the command to execute for a job."""
        # This would integrate with the agent's CLI
        return f'win11-omniagent run --job-id {job.id}'