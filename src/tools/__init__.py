"""
Win11-OmniAgent Tools Package

Automation tools for:
- Browser control (Playwright)
- Desktop app control (UI Automation)
- File operations
- Credential management
- System operations
"""

from .browser import BrowserTools
from .desktop import DesktopTools
from .files import FileTools
from .system import SystemTools
from .registry import get_default_tools

__all__ = [
    "BrowserTools",
    "DesktopTools",
    "FileTools",
    "SystemTools",
    "get_default_tools",
]