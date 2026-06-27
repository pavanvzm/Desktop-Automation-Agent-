"""
Win11-OmniAgent System Vitals Monitoring Package

Provides:
- Telemetry collection (CPU, GPU, RAM, Disk, Network, Temperature)
- Anomaly detection using statistical models
- Alert routing (Toast, Email, Webhook)
- Self-healing actions
- Real-time dashboard data
"""

from .collector import VitalsCollector, SystemVitals
from .anomaly import AnomalyDetector, Alert, AlertSeverity
from .alerter import AlertRouter, NotificationChannel
from .dashboard import DashboardData

__all__ = [
    "VitalsCollector",
    "SystemVitals",
    "AnomalyDetector",
    "Alert",
    "AlertSeverity",
    "AlertRouter",
    "NotificationChannel",
    "DashboardData",
]