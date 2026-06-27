"""Dashboard data provider for real-time monitoring UI."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .collector import SystemVitals, VitalsCollector
from .anomaly import Alert, AnomalyDetector, AlertSeverity
from .alerter import AlertRouter


@dataclass
class DashboardData:
    """Data structure for dashboard display."""

    timestamp: datetime = field(default_factory=datetime.now)

    # Vitals
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    gpu_percent: float | None = None
    network_sent_mb: float = 0.0
    network_recv_mb: float = 0.0

    # Active tasks
    active_task_count: int = 0
    task_history: list[dict] = field(default_factory=list)

    # Alerts
    active_alert_count: int = 0
    critical_alerts: list[Alert] = field(default_factory=list)
    warning_alerts: list[Alert] = field(default_factory=list)

    # System status
    system_healthy: bool = True
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "vitals": {
                "cpu_percent": self.cpu_percent,
                "memory_percent": self.memory_percent,
                "disk_percent": self.disk_percent,
                "gpu_percent": self.gpu_percent,
                "network_sent_mb": self.network_sent_mb,
                "network_recv_mb": self.network_recv_mb,
            },
            "tasks": {
                "active_count": self.active_task_count,
                "history": self.task_history[-10:],
            },
            "alerts": {
                "active_count": self.active_alert_count,
                "critical": [a.to_dict() for a in self.critical_alerts],
                "warning": [a.to_dict() for a in self.warning_alerts],
            },
            "system_status": {
                "healthy": self.system_healthy,
                "issues": self.issues,
            },
        }


class DashboardProvider:
    """
    Provider for real-time dashboard data.

    Aggregates data from vitals collector, anomaly detector,
    and scheduler for display in the UI.
    """

    def __init__(
        self,
        vitals_collector: VitalsCollector | None = None,
        anomaly_detector: AnomalyDetector | None = None,
        alert_router: AlertRouter | None = None,
    ):
        self.vitals_collector = vitals_collector
        self.anomaly_detector = anomaly_detector
        self.alert_router = alert_router

        self._active_tasks: list[dict] = []
        self._task_history: list[dict] = []
        self._max_history = 50

    def update_vitals(self, vitals: SystemVitals) -> None:
        """Update with new vitals sample."""
        self._current_vitals = vitals

    def update_tasks(self, tasks: list[dict]) -> None:
        """Update active tasks."""
        self._active_tasks = tasks

    def add_task_history(self, task: dict) -> None:
        """Add a completed task to history."""
        task["completed_at"] = datetime.now().isoformat()
        self._task_history.append(task)
        if len(self._task_history) > self._max_history:
            self._task_history.pop(0)

    def add_alert(self, alert: Alert) -> None:
        """Add a new alert."""
        if self.alert_router:
            asyncio.create_task(self.alert_router.send_alert(alert))

    def get_current_data(self) -> DashboardData:
        """Get current dashboard data snapshot."""
        data = DashboardData()

        # Vitals
        if hasattr(self, "_current_vitals"):
            v = self._current_vitals
            data.cpu_percent = v.cpu_percent
            data.memory_percent = v.memory_percent
            data.disk_percent = v.disk_percent
            data.gpu_percent = v.gpu_percent
            data.network_sent_mb = v.network_bytes_sent / (1024 * 1024)
            data.network_recv_mb = v.network_bytes_recv / (1024 * 1024)

        # Tasks
        data.active_task_count = len(self._active_tasks)
        data.task_history = self._task_history

        # Alerts
        if self.anomaly_detector:
            alerts = self.anomaly_detector.get_active_alerts()
            data.active_alert_count = len(alerts)
            data.critical_alerts = [a for a in alerts if a.severity == AlertSeverity.CRITICAL]
            data.warning_alerts = [a for a in alerts if a.severity == AlertSeverity.WARNING]

        # System status
        if data.critical_alerts:
            data.system_healthy = False
            data.issues = [f"Critical: {a.message}" for a in data.critical_alerts[:3]]
        elif data.warning_alerts:
            data.issues = [f"Warning: {a.message}" for a in data.warning_alerts[:3]]

        return data

    def get_chart_data(self, metric: str, seconds: int = 300) -> dict:
        """Get historical chart data for a metric."""
        if not self.vitals_collector:
            return {"labels": [], "values": []}

        history = self.vitals_collector.get_history(seconds)

        labels = []
        values = []

        for vitals in history:
            labels.append(vitals.timestamp.strftime("%H:%M:%S"))

            if metric == "cpu":
                values.append(vitals.cpu_percent)
            elif metric == "memory":
                values.append(vitals.memory_percent)
            elif metric == "disk":
                values.append(vitals.disk_percent)
            elif metric == "gpu" and vitals.gpu_percent is not None:
                values.append(vitals.gpu_percent)
            else:
                values.append(0)

        return {
            "labels": labels[-50:],  # Limit points
            "values": values[-50:],
            "metric": metric,
            "time_range_seconds": seconds,
        }

    def get_summary(self) -> dict:
        """Get a brief summary for quick display."""
        data = self.get_current_data()

        status = "🟢 Healthy"
        if data.critical_alerts:
            status = "🔴 Critical"
        elif data.warning_alerts:
            status = "🟡 Warning"

        return {
            "status": status,
            "cpu": f"{data.cpu_percent:.0f}%",
            "memory": f"{data.memory_percent:.0f}%",
            "disk": f"{data.disk_percent:.0f}%",
            "gpu": f"{data.gpu_percent:.0f}%" if data.gpu_percent else "N/A",
            "alerts": data.active_alert_count,
            "tasks": data.active_task_count,
        }
