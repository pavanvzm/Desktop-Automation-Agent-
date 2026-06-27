from __future__ import annotations
"""Anomaly detection for system vitals."""

import asyncio
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from .collector import SystemVitals


class AlertSeverity(str, Enum):
    """Severity levels for alerts."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Represents a detected anomaly or threshold breach."""

    id: str
    severity: AlertSeverity
    metric: str
    message: str
    current_value: float
    threshold_value: float
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "severity": self.severity.value,
            "metric": self.metric,
            "message": self.message,
            "current_value": self.current_value,
            "threshold_value": self.threshold_value,
            "timestamp": self.timestamp.isoformat(),
            "acknowledged": self.acknowledged,
        }


class AnomalyDetector:
    """
    Detect anomalies in system vitals using statistical models.

    Methods:
    - Z-score: Flag values beyond N standard deviations
    - EWMA: Exponentially Weighted Moving Average
    - Static thresholds: Simple high/low bounds
    """

    def __init__(
        self,
        z_score_threshold: float = 3.0,
        ewma_alpha: float = 0.3,
        warmup_samples: int = 10,
    ):
        self.z_score_threshold = z_score_threshold
        self.ewma_alpha = ewma_alpha
        self.warmup_samples = warmup_samples

        # Metric baselines (EWMA)
        self._baselines: dict[str, float] = {}
        self._baseline_vars: dict[str, float] = {}
        self._sample_counts: dict[str, int] = {}

        # Static thresholds
        self._thresholds: dict[str, tuple[float, float, AlertSeverity]] = {
            "cpu_percent": (70.0, 90.0, AlertSeverity.WARNING),
            "memory_percent": (75.0, 90.0, AlertSeverity.WARNING),
            "disk_percent": (80.0, 95.0, AlertSeverity.CRITICAL),
            "gpu_percent": (90.0, 98.0, AlertSeverity.WARNING),
            "gpu_temp_celsius": (80.0, 95.0, AlertSeverity.CRITICAL),
            "cpu_temp_celsius": (85.0, 100.0, AlertSeverity.CRITICAL),
        }

        # Alert history
        self._alerts: list[Alert] = []
        self._max_alerts = 100

    def set_threshold(
        self,
        metric: str,
        warning_threshold: float,
        critical_threshold: float,
        severity: AlertSeverity = AlertSeverity.WARNING,
    ) -> None:
        """Set static thresholds for a metric."""
        self._thresholds[metric] = (warning_threshold, critical_threshold, severity)

    def detect(self, vitals: SystemVitals) -> list[Alert]:
        """Detect anomalies in the given vitals."""
        alerts = []

        # Check static thresholds
        alerts.extend(self._check_static_thresholds(vitals))

        # Check statistical anomalies
        alerts.extend(self._check_statistical_anomalies(vitals))

        # Store alerts
        self._alerts.extend(alerts)
        if len(self._alerts) > self._max_alerts:
            self._alerts = self._alerts[-self._max_alerts:]

        return alerts

    def _check_static_thresholds(self, vitals: SystemVitals) -> list[Alert]:
        """Check against static thresholds."""
        alerts = []
        import uuid

        checks = {
            "cpu_percent": vitals.cpu_percent,
            "memory_percent": vitals.memory_percent,
            "disk_percent": vitals.disk_percent,
            "gpu_percent": vitals.gpu_percent,
            "gpu_temp_celsius": vitals.gpu_temp_celsius,
            "cpu_temp_celsius": vitals.cpu_temp_celsius,
        }

        for metric, value in checks.items():
            if value is None:
                continue

            if metric not in self._thresholds:
                continue

            warning, critical, _ = self._thresholds[metric]

            if value >= critical:
                alerts.append(Alert(
                    id=str(uuid.uuid4()),
                    severity=AlertSeverity.CRITICAL,
                    metric=metric,
                    message=f"Critical: {metric} at {value:.1f}% (threshold: {critical})",
                    current_value=value,
                    threshold_value=critical,
                ))
            elif value >= warning:
                alerts.append(Alert(
                    id=str(uuid.uuid4()),
                    severity=AlertSeverity.WARNING,
                    metric=metric,
                    message=f"Warning: {metric} at {value:.1f}% (threshold: {warning})",
                    current_value=value,
                    threshold_value=warning,
                ))

        return alerts

    def _check_statistical_anomalies(self, vitals: SystemVitals) -> list[Alert]:
        """Check for statistical anomalies using Z-score."""
        alerts = []
        import uuid

        checks = {
            "cpu_percent": vitals.cpu_percent,
            "memory_percent": vitals.memory_percent,
        }

        for metric, value in checks.items():
            if value is None:
                continue

            # Update baseline
            self._update_baseline(metric, value)

            # Check if we have enough samples
            if self._sample_counts.get(metric, 0) < self.warmup_samples:
                continue

            # Calculate Z-score
            mean = self._baselines.get(metric, 0)
            std = (self._baseline_vars.get(metric, 0) ** 0.5)

            if std > 0:
                z_score = (value - mean) / std

                if abs(z_score) > self.z_score_threshold:
                    direction = "high" if z_score > 0 else "low"
                    alerts.append(Alert(
                        id=str(uuid.uuid4()),
                        severity=AlertSeverity.INFO,
                        metric=metric,
                        message=f"Anomaly detected: {metric} is unusually {direction} ({value:.1f}%, expected ~{mean:.1f}%)",
                        current_value=value,
                        threshold_value=mean + (self.z_score_threshold * std),
                    ))

        return alerts

    def _update_baseline(self, metric: str, value: float) -> None:
        """Update EWMA baseline for a metric."""
        if metric not in self._baselines:
            self._baselines[metric] = value
            self._baseline_vars[metric] = 0.0
            self._sample_counts[metric] = 1
            return

        # Update EWMA
        alpha = self.ewma_alpha
        old_mean = self._baselines[metric]
        old_var = self._baseline_vars[metric]
        count = self._sample_counts[metric]

        # Update mean with EWMA
        new_mean = alpha * value + (1 - alpha) * old_mean

        # Update variance with EWMA
        new_var = alpha * ((value - new_mean) ** 2) + (1 - alpha) * old_var

        self._baselines[metric] = new_mean
        self._baseline_vars[metric] = new_var
        self._sample_counts[metric] = count + 1

    def get_active_alerts(self, unacknowledged_only: bool = True) -> list[Alert]:
        """Get currently active alerts."""
        alerts = self._alerts[-50:]  # Last 50 alerts

        if unacknowledged_only:
            alerts = [a for a in alerts if not a.acknowledged]

        return alerts

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def clear_alerts(self, before: datetime | None = None) -> int:
        """Clear old alerts."""
        if before is None:
            before = datetime.now()

        original_count = len(self._alerts)
        self._alerts = [a for a in self._alerts if a.timestamp > before]
        return original_count - len(self._alerts)

    def get_baseline(self, metric: str) -> dict | None:
        """Get baseline statistics for a metric."""
        if metric not in self._baselines:
            return None

        return {
            "mean": self._baselines[metric],
            "std": self._baseline_vars[metric] ** 0.5,
            "sample_count": self._sample_counts[metric],
        }


class ThresholdBreachMonitor:
    """
    Monitor for threshold breaches with configurable self-healing actions.
    """

    def __init__(self, detector: AnomalyDetector):
        self.detector = detector
        self._healing_actions: dict[str, list[Callable]] = {}

    def register_healing_action(
        self,
        metric: str,
        threshold: float,
        action: Callable[[], Any],
    ) -> None:
        """Register a self-healing action for a metric threshold."""
        key = f"{metric}:{threshold}"
        if key not in self._healing_actions:
            self._healing_actions[key] = []
        self._healing_actions[key].append(action)

    async def check_and_heal(self, vitals: SystemVitals) -> list[Alert]:
        """Check vitals and execute healing actions if needed."""
        alerts = self.detector.detect(vitals)

        for alert in alerts:
            if alert.severity != AlertSeverity.CRITICAL:
                continue

            key = f"{alert.metric}:{alert.threshold_value}"
            if key in self._healing_actions:
                for action in self._healing_actions[key]:
                    try:
                        if asyncio.iscoroutinefunction(action):
                            await action()
                        else:
                            action()
                    except Exception:
                        pass

        return alerts
