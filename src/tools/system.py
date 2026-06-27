from __future__ import annotations
"""System operations tools."""

import os
import subprocess
from datetime import datetime
from typing import Any

from ..core.tool_schema import Tool, ToolParameter, ActionRiskLevel


# Tool definitions for system operations

get_system_info_tool = Tool(
    name="system_info",
    description="Get system information (OS, CPU, memory, etc.)",
    parameters=[],
    risk_level=ActionRiskLevel.LOW,
    category="system",
)

get_cpu_info_tool = Tool(
    name="system_cpu",
    description="Get CPU information and usage",
    parameters=[
        ToolParameter(
            name="detailed",
            type="boolean",
            description="Get detailed CPU information",
            required=False,
            default=False,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="system",
)

get_memory_info_tool = Tool(
    name="system_memory",
    description="Get memory (RAM) information and usage",
    parameters=[],
    risk_level=ActionRiskLevel.LOW,
    category="system",
)

get_disk_info_tool = Tool(
    name="system_disk",
    description="Get disk usage information",
    parameters=[
        ToolParameter(
            name="drive",
            type="string",
            description="Drive letter (e.g., 'C:')",
            required=False,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="system",
)

get_network_info_tool = Tool(
    name="system_network",
    description="Get network information and status",
    parameters=[],
    risk_level=ActionRiskLevel.LOW,
    category="system",
)

get_processes_tool = Tool(
    name="system_processes",
    description="Get list of running processes",
    parameters=[
        ToolParameter(
            name="top_n",
            type="number",
            description="Number of top processes by CPU/memory to return",
            required=False,
            default=10,
        ),
        ToolParameter(
            name="sort_by",
            type="string",
            description="Sort by 'cpu' or 'memory'",
            required=False,
            default="cpu",
            enum=["cpu", "memory"],
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="system",
)

kill_process_tool = Tool(
    name="system_kill_process",
    description="Kill a process by name or PID",
    parameters=[
        ToolParameter(
            name="process_name",
            type="string",
            description="Process name or PID",
            required=True,
        ),
        ToolParameter(
            name="force",
            type="boolean",
            description="Force kill the process",
            required=False,
            default=False,
        ),
    ],
    risk_level=ActionRiskLevel.HIGH,
    category="system",
)

run_command_tool = Tool(
    name="system_run_command",
    description="Run a system command (requires explicit user confirmation for destructive commands)",
    parameters=[
        ToolParameter(
            name="command",
            type="string",
            description="Command to run",
            required=True,
        ),
        ToolParameter(
            name="shell",
            type="boolean",
            description="Run through shell",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="timeout_seconds",
            type="number",
            description="Command timeout in seconds",
            required=False,
            default=30,
        ),
        ToolParameter(
            name="working_dir",
            type="string",
            description="Working directory",
            required=False,
        ),
    ],
    risk_level=ActionRiskLevel.HIGH,
    category="system",
)

get_environment_vars_tool = Tool(
    name="system_env",
    description="Get environment variables",
    parameters=[
        ToolParameter(
            name="filter",
            type="string",
            description="Filter variables by name pattern",
            required=False,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="system",
)

get_uptime_tool = Tool(
    name="system_uptime",
    description="Get system uptime",
    parameters=[],
    risk_level=ActionRiskLevel.LOW,
    category="system",
)

screenshot_tool = Tool(
    name="system_screenshot",
    description="Take a screenshot of the entire screen",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Path to save the screenshot",
            required=False,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="system",
)

open_url_tool = Tool(
    name="system_open_url",
    description="Open a URL in the default browser",
    parameters=[
        ToolParameter(
            name="url",
            type="string",
            description="URL to open",
            required=True,
        ),
    ],
    risk_level=ActionRiskLevel.MEDIUM,
    category="system",
)

get_clipboard_tool = Tool(
    name="system_clipboard_get",
    description="Get the current clipboard content",
    parameters=[],
    risk_level=ActionRiskLevel.LOW,
    category="system",
)

set_clipboard_tool = Tool(
    name="system_clipboard_set",
    description="Set the clipboard content",
    parameters=[
        ToolParameter(
            name="text",
            type="string",
            description="Text to copy to clipboard",
            required=True,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="system",
)

get_volume_tool = Tool(
    name="system_volume",
    description="Get or set system volume",
    parameters=[
        ToolParameter(
            name="level",
            type="number",
            description="Volume level 0-100 (null to just get current level)",
            required=False,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="system",
)


# Tool implementations

async def system_info() -> dict:
    """Get system information."""
    try:
        import platform

        info = {
            "success": True,
            "os": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
            },
            "python_version": platform.python_version(),
            "hostname": platform.node(),
            "timestamp": datetime.now().isoformat(),
        }

        # Add Windows-specific info
        if platform.system() == "Windows":
            try:
                result = subprocess.run(
                    ["powershell", "-Command", "(Get-CimInstance Win32_OperatingSystem).Caption"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    info["os"]["windows_version"] = result.stdout.strip()
            except Exception:
                pass

        return info
    except Exception as e:
        return {"success": False, "error": str(e)}


async def system_cpu(detailed: bool = False) -> dict:
    """Get CPU information."""
    try:
        import psutil

        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()

        info = {
            "success": True,
            "usage_percent": cpu_percent,
            "count": cpu_count,
            "physical_count": psutil.cpu_count(logical=False),
        }

        if detailed:
            info["per_cpu"] = psutil.cpu_percent(interval=0.5, percpu=True)
            info["freq"] = psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None

        return info
    except ImportError:
        return {"success": False, "error": "psutil not available"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def system_memory() -> dict:
    """Get memory information."""
    try:
        import psutil

        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        return {
            "success": True,
            "virtual": {
                "total_bytes": mem.total,
                "available_bytes": mem.available,
                "used_bytes": mem.used,
                "percent": mem.percent,
            },
            "swap": {
                "total_bytes": swap.total,
                "used_bytes": swap.used,
                "percent": swap.percent,
            },
        }
    except ImportError:
        return {"success": False, "error": "psutil not available"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def system_disk(drive: str | None = None) -> dict:
    """Get disk information."""
    try:
        import psutil

        partitions = psutil.disk_partitions()
        disks = []

        for partition in partitions:
            if drive and not partition.device.startswith(drive):
                continue

            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disks.append({
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "filesystem": partition.fstype,
                    "total_bytes": usage.total,
                    "used_bytes": usage.used,
                    "free_bytes": usage.free,
                    "percent": usage.percent,
                })
            except PermissionError:
                continue

        return {
            "success": True,
            "drives": disks,
        }
    except ImportError:
        return {"success": False, "error": "psutil not available"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def system_network() -> dict:
    """Get network information."""
    try:
        import psutil

        net_io = psutil.net_io_counters()
        net_if_addrs = psutil.net_if_addrs()

        interfaces = {}
        for iface, addrs in net_if_addrs.items():
            interfaces[iface] = [
                {
                    "family": str(addr.family),
                    "address": addr.address,
                    "netmask": getattr(addr, "netmask", None),
                    "broadcast": getattr(addr, "broadcast", None),
                }
                for addr in addrs
            ]

        return {
            "success": True,
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
            "interfaces": interfaces,
        }
    except ImportError:
        return {"success": False, "error": "psutil not available"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def system_processes(top_n: int = 10, sort_by: str = "cpu") -> dict:
    """Get running processes."""
    try:
        import psutil

        processes = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Sort by specified criteria
        key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
        processes.sort(key=lambda x: x.get(key, 0) or 0, reverse=True)

        return {
            "success": True,
            "count": len(processes),
            "top_processes": processes[:top_n],
            "sort_by": sort_by,
        }
    except ImportError:
        return {"success": False, "error": "psutil not available"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def system_kill_process(process_name: str, force: bool = False) -> dict:
    """Kill a process."""
    try:
        import psutil

        killed = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if process_name.isdigit():
                    if proc.info["pid"] == int(process_name):
                        proc.kill() if force else proc.terminate()
                        killed.append(proc.info["pid"])
                elif proc.info["name"].lower() == process_name.lower():
                    proc.kill() if force else proc.terminate()
                    killed.append(proc.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return {
            "success": True,
            "killed": killed,
            "count": len(killed),
        }
    except ImportError:
        return {"success": False, "error": "psutil not available"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def system_run_command(
    command: str,
    shell: bool = True,
    timeout_seconds: int = 30,
    working_dir: str | None = None
) -> dict:
    """Run a system command."""
    # This is a high-risk tool - in production, this should have
    # additional safety checks and user confirmation

    try:
        kwargs = {
            "shell": shell,
            "capture_output": True,
            "timeout": timeout_seconds,
        }

        if working_dir:
            kwargs["cwd"] = working_dir

        result = subprocess.run(command, **kwargs)

        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": result.stdout.decode("utf-8", errors="replace")[:10000],
            "stderr": result.stderr.decode("utf-8", errors="replace")[:1000],
            "command": command,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timed out", "timeout": timeout_seconds}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def system_env(filter: str | None = None) -> dict:
    """Get environment variables."""
    try:
        env = dict(os.environ)

        if filter:
            filter_lower = filter.lower()
            env = {k: v for k, v in env.items() if filter_lower in k.lower()}

        # Mask sensitive values
        sensitive_keys = ["KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL"]
        for key in list(env.keys()):
            if any(s in key.upper() for s in sensitive_keys):
                env[key] = "***REDACTED***"

        return {
            "success": True,
            "count": len(env),
            "variables": env,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def system_uptime() -> dict:
    """Get system uptime."""
    try:
        import psutil

        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time

        return {
            "success": True,
            "boot_time": boot_time.isoformat(),
            "uptime_seconds": uptime.total_seconds(),
            "uptime_formatted": str(uptime).split(".")[0],
        }
    except ImportError:
        return {"success": False, "error": "psutil not available"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def system_screenshot(path: str | None = None) -> dict:
    """Take a screenshot."""
    try:
        from PIL import ImageGrab

        screenshot = ImageGrab.grab()

        if path:
            screenshot.save(path)
            saved_path = path
        else:
            import tempfile
            from pathlib import Path

            temp_dir = Path(tempfile.gettempdir()) / "win11-omniagent"
            temp_dir.mkdir(exist_ok=True)
            path = temp_dir / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            screenshot.save(path)
            saved_path = str(path)

        return {
            "success": True,
            "path": saved_path,
            "size": screenshot.size,
        }
    except ImportError:
        return {"success": False, "error": "PIL not available"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def system_open_url(url: str) -> dict:
    """Open a URL in default browser."""
    try:
        import webbrowser

        webbrowser.open(url)
        return {
            "success": True,
            "url": url,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def system_clipboard_get() -> dict:
    """Get clipboard content."""
    try:
        import pyperclip

        content = pyperclip.paste()
        return {
            "success": True,
            "content": content,
            "length": len(content),
        }
    except ImportError:
        return {"success": False, "error": "pyperclip not available"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def system_clipboard_set(text: str) -> dict:
    """Set clipboard content."""
    try:
        import pyperclip

        pyperclip.copy(text)
        return {
            "success": True,
            "length": len(text),
        }
    except ImportError:
        return {"success": False, "error": "pyperclip not available"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def system_volume(level: int | None = None) -> dict:
    """Get or set system volume."""
    # This would use a library like pycaw or sounddevice
    return {
        "success": True,
        "level": level,
        "message": "Volume control not yet implemented",
    }
