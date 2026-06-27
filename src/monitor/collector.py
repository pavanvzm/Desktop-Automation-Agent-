"""System vitals telemetry collection."""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..core.state import ActionRiskLevel


@dataclass
class SystemVitals:
    """Snapshot of system vitals at a point in time."""

    timestamp: datetime = field(default_factory=datetime.now)

    # CPU
    cpu_percent: float = 0.0
    cpu_count: int = 0
    cpu_freq_mhz: float | None = None

    # Memory
    memory_total_gb: float = 0.0
    memory_used_gb: float = 0.0
    memory_available_gb: float = 0.0
    memory_percent: float = 0.0

    # Disk
    disk_total_gb: float = 0.0
    disk_used_gb: float = 0.0
    disk_free_gb: float = 0.0
    disk_percent: float = 0.0

    # Network
    network_bytes_sent: int = 0
    network_bytes_recv: int = 0

    # Battery (if available)
    battery_percent: float | None = None
    battery_charging: bool | None = None

    # Temperature (if available)
    cpu_temp_celsius: float | None = None
    gpu_temp_celsius: float | None = None

    # GPU (if available)
    gpu_percent: float | None = None
    gpu_memory_used_mb: float | None = None

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu": {
                "percent": self.cpu_percent,
                "count": self.cpu_count,
                "freq_mhz": self.cpu_freq_mhz,
            },
            "memory": {
                "total_gb": self.memory_total_gb,
                "used_gb": self.memory_used_gb,
                "available_gb": self.memory_available_gb,
                "percent": self.memory_percent,
            },
            "disk": {
                "total_gb": self.disk_total_gb,
                "used_gb": self.disk_used_gb,
                "free_gb": self.disk_free_gb,
                "percent": self.disk_percent,
            },
            "network": {
                "bytes_sent": self.network_bytes_sent,
                "bytes_recv": self.network_bytes_recv,
            },
            "battery": {
                "percent": self.battery_percent,
                "charging": self.battery_charging,
            },
            "temperature": {
                "cpu_celsius": self.cpu_temp_celsius,
                "gpu_celsius": self.gpu_temp_celsius,
            },
            "gpu": {
                "percent": self.gpu_percent,
                "memory_used_mb": self.gpu_memory_used_mb,
            },
        }


class VitalsCollector:
    """
    Collect system vitals telemetry.

    Samples CPU, GPU, RAM, Disk, Network, and Temperature at
    configurable intervals.
    """

    def __init__(
        self,
        sample_interval: float = 5.0,
        include_gpu: bool = True,
        include_temperature: bool = True,
    ):
        self.sample_interval = sample_interval
        self.include_gpu = include_gpu
        self.include_temperature = include_temperature
        self._psutil_available = self._check_psutil()
        self._gputil_available = self._check_gputil()
        self._running = False
        self._task: asyncio.Task | None = None
        self._history: list[SystemVitals] = []
        self._max_history = 1000  # Keep last 1000 samples
        self._callbacks: list[callable] = []

    def _check_psutil(self) -> bool:
        """Check if psutil is available."""
        try:
            import psutil
            return True
        except ImportError:
            return False

    def _check_gputil(self) -> bool:
        """Check if GPUtil is available."""
        try:
            import GPUtil
            return True
        except ImportError:
            return False

    def add_callback(self, callback: callable) -> None:
        """Add a callback to be called on each sample."""
        self._callbacks.append(callback)

    async def collect(self) -> SystemVitals:
        """Collect current system vitals."""
        if not self._psutil_available:
            return SystemVitals()

        import psutil

        vitals = SystemVitals()

        # CPU
        vitals.cpu_percent = psutil.cpu_percent(interval=0.1)
        vitals.cpu_count = psutil.cpu_count()
        try:
            freq = psutil.cpu_freq()
            if freq:
                vitals.cpu_freq_mhz = freq.current
        except Exception:
            pass

        # Memory
        mem = psutil.virtual_memory()
        vitals.memory_total_gb = mem.total / (1024 ** 3)
        vitals.memory_used_gb = mem.used / (1024 ** 3)
        vitals.memory_available_gb = mem.available / (1024 ** 3)
        vitals.memory_percent = mem.percent

        # Disk
        try:
            disk = psutil.disk_usage("/")
            vitals.disk_total_gb = disk.total / (1024 ** 3)
            vitals.disk_used_gb = disk.used / (1024 ** 3)
            vitals.disk_free_gb = disk.free / (1024 ** 3)
            vitals.disk_percent = disk.percent
        except Exception:
            pass

        # Network
        net = psutil.net_io_counters()
        vitals.network_bytes_sent = net.bytes_sent
        vitals.network_bytes_recv = net.bytes_recv

        # Battery
        try:
            battery = psutil.sensors_battery()
            if battery:
                vitals.battery_percent = battery.percent
                vitals.battery_charging = battery.power_plugged
        except Exception:
            pass

        # GPU
        if self.include_gpu and self._gputil_available:
            try:
                import GPUtil

                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]
                    vitals.gpu_percent = gpu.load * 100
                    vitals.gpu_memory_used_mb = gpu.memoryUsed
                    vitals.gpu_temp_celsius = gpu.temperature
            except Exception:
                pass

        return vitals

    async def start(self) -> None:
        """Start continuous collection."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._collect_loop())

    async def stop(self) -> None:
        """Stop continuous collection."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _collect_loop(self) -> None:
        """Background collection loop."""
        while self._running:
            try:
                vitals = await self.collect()

                # Store in history
                self._history.append(vitals)
                if len(self._history) > self._max_history:
                    self._history.pop(0)

                # Call callbacks
                for callback in self._callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(vitals)
                        else:
                            callback(vitals)
                    except Exception:
                        pass

                await asyncio.sleep(self.sample_interval)

            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(self.sample_interval)

    def get_current(self) -> SystemVitals:
        """Get the most recent vitals sample."""
        if self._history:
            return self._history[-1]
        return SystemVitals()

    def get_history(self, seconds: int = 60) -> list[SystemVitals]:
        """Get vitals history for the last N seconds."""
        cutoff = datetime.now().timestamp() - seconds
        return [v for v in self._history if v.timestamp.timestamp() > cutoff]

    def get_average(self, metric: str, seconds: int = 60) -> float:
        """Get average value for a metric over a time period."""
        history = self.get_history(seconds)

        if not history:
            return 0.0

        values = []
        for vitals in history:
            if metric == "cpu_percent":
                values.append(vitals.cpu_percent)
            elif metric == "memory_percent":
                values.append(vitals.memory_percent)
            elif metric == "disk_percent":
                values.append(vitals.disk_percent)
            elif metric == "gpu_percent" and vitals.gpu_percent is not None:
                values.append(vitals.gpu_percent)

        return sum(values) / len(values) if values else 0.0

    def get_summary(self) -> dict:
        """Get a summary of recent vitals."""
        current = self.get_current()
        history = self.get_history(60)

        return {
            "current": current.to_dict(),
            "averages_1min": {
                "cpu_percent": self.get_average("cpu_percent", 60),
                "memory_percent": self.get_average("memory_percent", 60),
                "disk_percent": self.get_average("disk_percent", 60),
            },
            "samples_count": len(history),
            "collection_running": self._running,
        }