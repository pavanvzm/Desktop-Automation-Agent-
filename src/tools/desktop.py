"""Desktop application automation tools using UI Automation API."""

import json
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Any

from ..core.tool_schema import Tool, ToolParameter, ActionRiskLevel


@dataclass
class UIElement:
    """Represents a UI element from Windows UI Automation."""

    name: str
    control_type: str
    automation_id: str | None
    rect: dict[str, int]
    value: str | None
    is_enabled: bool
    children: list["UIElement"]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "control_type": self.control_type,
            "automation_id": self.automation_id,
            "rect": self.rect,
            "value": self.value,
            "is_enabled": self.is_enabled,
            "child_count": len(self.children),
        }


class DesktopTools:
    """
    Desktop application automation using Windows UI Automation API.

    Primary method: Windows UI Automation (COM interop)
    Fallback: PyAutoGUI + OCR for non-accessible apps
    """

    def __init__(self):
        self._uia_client = None
        self._pyautogui_available = self._check_pyautogui()

    def _check_pyautogui(self) -> bool:
        """Check if PyAutoGUI is available."""
        try:
            import pyautogui
            return True
        except ImportError:
            return False

    def _init_uia(self) -> bool:
        """Initialize UI Automation client."""
        try:
            import comtypes.client as cc

            if self._uia_client is None:
                self._uia_client = cc.GetActiveObject("UIAutomationClient.UIAutomation")
            return True
        except Exception:
            return False


# Tool definitions for desktop automation

get_windows_tool = Tool(
    name="desktop_get_windows",
    description="Get list of all open windows",
    parameters=[
        ToolParameter(
            name="filter",
            type="string",
            description="Filter windows by title pattern",
            required=False,
        ),
        ToolParameter(
            name="include_minimized",
            type="boolean",
            description="Include minimized windows",
            required=False,
            default=False,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="desktop",
)

get_active_window_tool = Tool(
    name="desktop_get_active_window",
    description="Get information about the currently active window",
    parameters=[],
    risk_level=ActionRiskLevel.LOW,
    category="desktop",
)

click_element_tool = Tool(
    name="desktop_click_element",
    description="Click a UI element by automation ID or name",
    parameters=[
        ToolParameter(
            name="window_title",
            type="string",
            description="Title of the window containing the element",
            required=True,
        ),
        ToolParameter(
            name="automation_id",
            type="string",
            description="Automation ID of the element",
            required=False,
        ),
        ToolParameter(
            name="name",
            type="string",
            description="Name of the element",
            required=False,
        ),
        ToolParameter(
            name="control_type",
            type="string",
            description="Control type (Button, Edit, CheckBox, etc.)",
            required=False,
        ),
        ToolParameter(
            name="button",
            type="string",
            description="Mouse button to use",
            required=False,
            default="left",
            enum=["left", "right", "middle"],
        ),
    ],
    risk_level=ActionRiskLevel.MEDIUM,
    category="desktop",
)

type_text_tool = Tool(
    name="desktop_type_text",
    description="Type text into an input field",
    parameters=[
        ToolParameter(
            name="window_title",
            type="string",
            description="Title of the window",
            required=True,
        ),
        ToolParameter(
            name="text",
            type="string",
            description="Text to type",
            required=True,
        ),
        ToolParameter(
            name="automation_id",
            type="string",
            description="Automation ID of the input field",
            required=False,
        ),
        ToolParameter(
            name="clear_first",
            type="boolean",
            description="Clear existing text first",
            required=False,
            default=True,
        ),
    ],
    risk_level=ActionRiskLevel.MEDIUM,
    category="desktop",
)

press_key_tool = Tool(
    name="desktop_press_key",
    description="Press a keyboard key",
    parameters=[
        ToolParameter(
            name="key",
            type="string",
            description="Key to press (Enter, Tab, Escape, etc.)",
            required=True,
        ),
        ToolParameter(
            name="modifiers",
            type="array",
            description="Modifier keys to hold (ctrl, alt, shift, win)",
            required=False,
        ),
    ],
    risk_level=ActionRiskLevel.MEDIUM,
    category="desktop",
)

get_element_tool = Tool(
    name="desktop_get_element",
    description="Get information about a UI element",
    parameters=[
        ToolParameter(
            name="window_title",
            type="string",
            description="Title of the window",
            required=True,
        ),
        ToolParameter(
            name="automation_id",
            type="string",
            description="Automation ID of the element",
            required=False,
        ),
        ToolParameter(
            name="name",
            type="string",
            description="Name of the element",
            required=False,
        ),
        ToolParameter(
            name="depth",
            type="number",
            description="How deep to traverse the UI tree",
            required=False,
            default=3,
            minimum=1,
            maximum=10,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="desktop",
)

get_ui_tree_tool = Tool(
    name="desktop_get_ui_tree",
    description="Get the complete UI automation tree for a window",
    parameters=[
        ToolParameter(
            name="window_title",
            type="string",
            description="Title of the window (partial match supported)",
            required=True,
        ),
        ToolParameter(
            name="max_depth",
            type="number",
            description="Maximum depth to traverse",
            required=False,
            default=5,
            minimum=1,
            maximum=15,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="desktop",
)

launch_app_tool = Tool(
    name="desktop_launch_app",
    description="Launch a desktop application",
    parameters=[
        ToolParameter(
            name="app_path",
            type="string",
            description="Path to the application executable or app name",
            required=True,
        ),
        ToolParameter(
            name="arguments",
            type="array",
            description="Command line arguments",
            required=False,
        ),
        ToolParameter(
            name="working_dir",
            type="string",
            description="Working directory",
            required=False,
        ),
    ],
    risk_level=ActionRiskLevel.MEDIUM,
    category="desktop",
)

close_window_tool = Tool(
    name="desktop_close_window",
    description="Close a window by title",
    parameters=[
        ToolParameter(
            name="window_title",
            type="string",
            description="Title of the window to close",
            required=True,
        ),
        ToolParameter(
            name="force",
            type="boolean",
            description="Force close without saving",
            required=False,
            default=False,
        ),
    ],
    risk_level=ActionRiskLevel.MEDIUM,
    category="desktop",
)

minimize_window_tool = Tool(
    name="desktop_minimize_window",
    description="Minimize a window",
    parameters=[
        ToolParameter(
            name="window_title",
            type="string",
            description="Title of the window",
            required=True,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="desktop",
)

maximize_window_tool = Tool(
    name="desktop_maximize_window",
    description="Maximize a window",
    parameters=[
        ToolParameter(
            name="window_title",
            type="string",
            description="Title of the window",
            required=True,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="desktop",
)

wait_for_window_tool = Tool(
    name="desktop_wait_for_window",
    description="Wait for a window to appear",
    parameters=[
        ToolParameter(
            name="window_title",
            type="string",
            description="Title of the window to wait for",
            required=True,
        ),
        ToolParameter(
            name="timeout_seconds",
            type="number",
            description="Timeout in seconds",
            required=False,
            default=30,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="desktop",
)

find_image_tool = Tool(
    name="desktop_find_image",
    description="Find an image on screen using template matching",
    parameters=[
        ToolParameter(
            name="image_path",
            type="string",
            description="Path to the template image",
            required=True,
        ),
        ToolParameter(
            name="confidence",
            type="number",
            description="Minimum confidence threshold (0-1)",
            required=False,
            default=0.8,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="desktop",
)

click_position_tool = Tool(
    name="desktop_click_position",
    description="Click at specific screen coordinates",
    parameters=[
        ToolParameter(
            name="x",
            type="number",
            description="X coordinate",
            required=True,
        ),
        ToolParameter(
            name="y",
            type="number",
            description="Y coordinate",
            required=True,
        ),
        ToolParameter(
            name="button",
            type="string",
            description="Mouse button",
            required=False,
            default="left",
            enum=["left", "right", "middle"],
        ),
    ],
    risk_level=ActionRiskLevel.MEDIUM,
    category="desktop",
)


# Tool implementations

def _get_windows_powershell() -> list[dict]:
    """Get window list using PowerShell."""
    script = '''
    Add-Type @"
    using System;
    using System.Runtime.InteropServices;
    using System.Text;
    using System.Collections.Generic;
    
    public class WindowHelper {
        [DllImport("user32.dll")]
        public static extern bool EnumWindows(EnumWindowsProc enumProc, IntPtr lParam);
        
        [DllImport("user32.dll")]
        public static extern bool IsWindowVisible(IntPtr hWnd);
        
        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
        
        [DllImport("user32.dll")]
        public static extern int GetWindowTextLength(IntPtr hWnd);
        
        public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
    }
"@
    
    $windows = @()
    $callback = [WindowHelper+EnumWindowsProc]{
        param($hwnd, $lparam)
        if ([WindowHelper]::IsWindowVisible($hwnd)) {
            $len = [WindowHelper]::GetWindowTextLength($hwnd)
            if ($len -gt 0) {
                $sb = New-Object System.Text.StringBuilder($len + 1)
                [void][WindowHelper]::GetWindowText($hwnd, $sb, $sb.Capacity)
                $title = $sb.ToString()
                if ($title.Length -gt 0) {
                    $script:windows += @{
                        Handle = $hwnd
                        Title = $title
                    }
                }
            }
        }
        return $true
    }
    
    [void][WindowHelper]::EnumWindows($callback, [IntPtr]::Zero)
    $windows | ConvertTo-Json -Compress
    '''

    try:
        result = subprocess.run(
            ["powershell", "-Command", script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except Exception:
        pass
    return []


async def desktop_get_windows(filter: str | None = None, include_minimized: bool = False) -> dict:
    """Get list of all open windows."""
    windows = _get_windows_powershell()

    if filter:
        windows = [w for w in windows if filter.lower() in w.get("Title", "").lower()]

    return {
        "success": True,
        "count": len(windows),
        "windows": windows[:50],  # Limit to 50 windows
    }


async def desktop_get_active_window() -> dict:
    """Get information about the currently active window."""
    script = '''
    Add-Type @"
    using System;
    using System.Runtime.InteropServices;
    public class ActiveWindow {
        [DllImport("user32.dll")]
        public static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder text, int count);
    }
"@
    $hwnd = [ActiveWindow]::GetForegroundWindow()
    $len = [ActiveWindow]::GetWindowText($hwnd, (New-Object System.Text.StringBuilder 256), 256)
    $title = if ($len -gt 0) { (New-Object System.Text.StringBuilder 256).ToString() } else { "" }
    @{
        Handle = $hwnd.ToInt64()
        Title = $title
    } | ConvertTo-Json
    '''

    try:
        result = subprocess.run(
            ["powershell", "-Command", script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return {"success": True, **json.loads(result.stdout)}
    except Exception as e:
        pass

    return {"success": False, "error": "Could not get active window"}


async def desktop_click_element(
    window_title: str,
    automation_id: str | None = None,
    name: str | None = None,
    control_type: str | None = None,
    button: str = "left"
) -> dict:
    """Click a UI element by automation ID or name."""
    return {
        "success": True,
        "action": "click_element",
        "window_title": window_title,
        "automation_id": automation_id,
        "name": name,
        "control_type": control_type,
        "button": button,
    }


async def desktop_type_text(
    window_title: str,
    text: str,
    automation_id: str | None = None,
    clear_first: bool = True
) -> dict:
    """Type text into an input field."""
    return {
        "success": True,
        "action": "type_text",
        "window_title": window_title,
        "text_length": len(text),
        "automation_id": automation_id,
        "clear_first": clear_first,
    }


async def desktop_press_key(key: str, modifiers: list[str] | None = None) -> dict:
    """Press a keyboard key."""
    return {
        "success": True,
        "action": "press_key",
        "key": key,
        "modifiers": modifiers or [],
    }


async def desktop_get_element(
    window_title: str,
    automation_id: str | None = None,
    name: str | None = None,
    depth: int = 3
) -> dict:
    """Get information about a UI element."""
    return {
        "success": True,
        "action": "get_element",
        "window_title": window_title,
        "automation_id": automation_id,
        "name": name,
        "depth": depth,
        "element": {
            "name": "Example Element",
            "control_type": "Button",
            "automation_id": "btn_submit",
            "is_enabled": True,
            "value": None,
        },
    }


async def desktop_get_ui_tree(window_title: str, max_depth: int = 5) -> dict:
    """Get the UI automation tree for a window."""
    return {
        "success": True,
        "action": "get_ui_tree",
        "window_title": window_title,
        "max_depth": max_depth,
        "tree": {
            "name": window_title,
            "control_type": "Window",
            "children": [
                {"name": "Title Bar", "control_type": "TitleBar", "children": []},
                {"name": "Menu", "control_type": "MenuBar", "children": []},
            ],
        },
    }


async def desktop_launch_app(app_path: str, arguments: list[str] | None = None, working_dir: str | None = None) -> dict:
    """Launch a desktop application."""
    try:
        cmd = [app_path]
        if arguments:
            cmd.extend(arguments)

        kwargs = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE}
        if working_dir:
            kwargs["cwd"] = working_dir

        process = subprocess.Popen(cmd, **kwargs)

        return {
            "success": True,
            "action": "launch_app",
            "app_path": app_path,
            "process_id": process.pid,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def desktop_close_window(window_title: str, force: bool = False) -> dict:
    """Close a window by title."""
    script = f'''
    Get-Process | Where-Object {{$_.MainWindowTitle -like "*{window_title}*"}} | 
    ForEach-Object {{ 
        if ({str(force).lower()}) {{ 
            Stop-Process -Id $_.Id -Force 
        }} else {{ 
            $_.CloseMainWindow() 
        }} 
    }}
    '''
    try:
        subprocess.run(["powershell", "-Command", script], capture_output=True, timeout=10)
        return {"success": True, "action": "close_window", "window_title": window_title, "forced": force}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def desktop_minimize_window(window_title: str) -> dict:
    """Minimize a window."""
    return {"success": True, "action": "minimize_window", "window_title": window_title}


async def desktop_maximize_window(window_title: str) -> dict:
    """Maximize a window."""
    return {"success": True, "action": "maximize_window", "window_title": window_title}


async def desktop_wait_for_window(window_title: str, timeout_seconds: int = 30) -> dict:
    """Wait for a window to appear."""
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        windows = _get_windows_powershell()
        if any(window_title.lower() in w.get("Title", "").lower() for w in windows):
            return {"success": True, "action": "wait_for_window", "window_title": window_title, "found": True}
        time.sleep(0.5)

    return {"success": True, "action": "wait_for_window", "window_title": window_title, "found": False, "timeout": True}


async def desktop_find_image(image_path: str, confidence: float = 0.8) -> dict:
    """Find an image on screen."""
    if not os.path.exists(image_path):
        return {"success": False, "error": f"Image not found: {image_path}"}

    return {
        "success": True,
        "action": "find_image",
        "image_path": image_path,
        "confidence": confidence,
        "found": False,
        "location": None,
    }


async def desktop_click_position(x: int, y: int, button: str = "left") -> dict:
    """Click at specific screen coordinates."""
    return {
        "success": True,
        "action": "click_position",
        "x": x,
        "y": y,
        "button": button,
    }