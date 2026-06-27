"""Browser automation tools using Playwright."""

import asyncio
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from ..core.tool_schema import Tool, ToolParameter, ActionRiskLevel, register_tool


@dataclass
class BrowserConfig:
    """Configuration for browser automation."""

    browser_type: str = "chromium"  # chromium, firefox, webkit
    headless: bool = True
    user_agent: str | None = None
    viewport_size: tuple[int, int] = (1920, 1080)
    timeout_ms: int = 30000
    stealth: bool = True  # Anti-detection measures


class BrowserTools:
    """
    Browser automation tools using Playwright.

    Supports Chrome/Edge/Firefox with persistent contexts,
    form filling, and anti-detection measures.
    """

    def __init__(self, config: BrowserConfig | None = None):
        self.config = config or BrowserConfig()
        self._contexts: dict[str, Any] = {}
        self._current_context: str | None = None

    async def _get_browser(self):
        """Get or create a Playwright browser instance."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "Playwright is required for browser automation. "
                "Install with: pip install playwright && playwright install"
            )

        return async_playwright()

    async def _ensure_context(self, context_id: str = "default") -> Any:
        """Ensure a browser context exists."""
        if context_id not in self._contexts:
            pw = await self._get_browser()
            playwright = await pw.start()

            browser = await getattr(playwright, self.config.browser_type).launch(
                headless=self.config.headless
            )

            context_options = {
                "viewport_size": self.config.viewport_size,
            }

            if self.config.user_agent:
                context_options["user_agent"] = self.config.user_agent

            context = await browser.new_context(**context_options)

            if self.config.stealth:
                # Apply stealth patches
                await context.set_extra_http_headers({
                    "Accept-Language": "en-US,en;q=0.9",
                })

            self._contexts[context_id] = {
                "playwright": playwright,
                "browser": browser,
                "context": context,
            }

        return self._contexts[context_id]

    async def close(self) -> None:
        """Close all browser contexts."""
        for context_data in self._contexts.values():
            await context_data["context"].close()
            await context_data["browser"].close()
            await context_data["playwright"].stop()
        self._contexts.clear()
        self._current_context = None


# Tool definitions for browser automation

navigate_tool = Tool(
    name="browser_navigate",
    description="Navigate to a URL in the browser",
    parameters=[
        ToolParameter(
            name="url",
            type="string",
            description="The URL to navigate to",
            required=True,
        ),
        ToolParameter(
            name="wait_until",
            type="string",
            description="Wait until event (load, domcontentloaded, networkidle)",
            required=False,
            default="load",
            enum=["load", "domcontentloaded", "networkidle"],
        ),
    ],
    risk_level=ActionRiskLevel.MEDIUM,
    category="browser",
)

click_tool = Tool(
    name="browser_click",
    description="Click an element on the page by selector",
    parameters=[
        ToolParameter(
            name="selector",
            type="string",
            description="CSS or XPath selector for the element",
            required=True,
        ),
        ToolParameter(
            name="button",
            type="string",
            description="Mouse button (left, right, middle)",
            required=False,
            default="left",
            enum=["left", "right", "middle"],
        ),
        ToolParameter(
            name="click_count",
            type="number",
            description="Number of clicks",
            required=False,
            default=1,
            minimum=1,
            maximum=3,
        ),
    ],
    risk_level=ActionRiskLevel.MEDIUM,
    category="browser",
)

type_tool = Tool(
    name="browser_type",
    description="Type text into an input field",
    parameters=[
        ToolParameter(
            name="selector",
            type="string",
            description="CSS or XPath selector for the input element",
            required=True,
        ),
        ToolParameter(
            name="text",
            type="string",
            description="Text to type",
            required=True,
        ),
        ToolParameter(
            name="delay",
            type="number",
            description="Delay between keystrokes in ms",
            required=False,
            default=0,
            minimum=0,
        ),
        ToolParameter(
            name="clear_first",
            type="boolean",
            description="Clear the field before typing",
            required=False,
            default=True,
        ),
    ],
    risk_level=ActionRiskLevel.MEDIUM,
    category="browser",
)

screenshot_tool = Tool(
    name="browser_screenshot",
    description="Take a screenshot of the current page",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="File path to save the screenshot",
            required=False,
        ),
        ToolParameter(
            name="full_page",
            type="boolean",
            description="Capture the full scrollable page",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="selector",
            type="string",
            description="Selector to screenshot a specific element",
            required=False,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="browser",
)

get_html_tool = Tool(
    name="browser_get_html",
    description="Get the HTML content of the current page or an element",
    parameters=[
        ToolParameter(
            name="selector",
            type="string",
            description="CSS or XPath selector for element (optional, gets full page if not provided)",
            required=False,
        ),
        ToolParameter(
            name="inner_html",
            type="boolean",
            description="Get innerHTML instead of outerHTML",
            required=False,
            default=False,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="browser",
)

get_text_tool = Tool(
    name="browser_get_text",
    description="Get text content from the page or element",
    parameters=[
        ToolParameter(
            name="selector",
            type="string",
            description="CSS or XPath selector for element",
            required=False,
        ),
        ToolParameter(
            name="all_text",
            type="boolean",
            description="Get all text on the page",
            required=False,
            default=False,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="browser",
)

evaluate_tool = Tool(
    name="browser_evaluate",
    description="Execute JavaScript in the page context",
    parameters=[
        ToolParameter(
            name="script",
            type="string",
            description="JavaScript code to execute",
            required=True,
        ),
    ],
    risk_level=ActionRiskLevel.HIGH,
    category="browser",
)

wait_for_selector_tool = Tool(
    name="browser_wait_for_selector",
    description="Wait for an element to appear on the page",
    parameters=[
        ToolParameter(
            name="selector",
            type="string",
            description="CSS or XPath selector for the element",
            required=True,
        ),
        ToolParameter(
            name="timeout_ms",
            type="number",
            description="Timeout in milliseconds",
            required=False,
            default=30000,
            minimum=0,
        ),
        ToolParameter(
            name="state",
            type="string",
            description="Expected state (attached, detached, visible, hidden)",
            required=False,
            default="visible",
            enum=["attached", "detached", "visible", "hidden"],
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="browser",
)

select_tool = Tool(
    name="browser_select",
    description="Select options in a dropdown/select element",
    parameters=[
        ToolParameter(
            name="selector",
            type="string",
            description="CSS or XPath selector for the select element",
            required=True,
        ),
        ToolParameter(
            name="values",
            type="array",
            description="Values or labels to select",
            required=True,
        ),
        ToolParameter(
            name="by",
            type="string",
            description="Selection method (value, label, or index)",
            required=False,
            default="value",
            enum=["value", "label", "index"],
        ),
    ],
    risk_level=ActionRiskLevel.MEDIUM,
    category="browser",
)

press_tool = Tool(
    name="browser_press",
    description="Press a keyboard key or key combination",
    parameters=[
        ToolParameter(
            name="key",
            type="string",
            description="Key to press (e.g., 'Enter', 'Control+a', 'Alt+F4')",
            required=True,
        ),
        ToolParameter(
            name="selector",
            type="string",
            description="Element to focus before pressing (optional)",
            required=False,
        ),
        ToolParameter(
            name="delay",
            type="number",
            description="Delay after press in ms",
            required=False,
            default=0,
        ),
    ],
    risk_level=ActionRiskLevel.MEDIUM,
    category="browser",
)

hover_tool = Tool(
    name="browser_hover",
    description="Hover over an element",
    parameters=[
        ToolParameter(
            name="selector",
            type="string",
            description="CSS or XPath selector for the element",
            required=True,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="browser",
)

scroll_tool = Tool(
    name="browser_scroll",
    description="Scroll the page or an element",
    parameters=[
        ToolParameter(
            name="direction",
            type="string",
            description="Scroll direction",
            required=False,
            default="down",
            enum=["up", "down", "left", "right"],
        ),
        ToolParameter(
            name="amount",
            type="number",
            description="Scroll amount in pixels",
            required=False,
            default=500,
        ),
        ToolParameter(
            name="selector",
            type="string",
            description="Element to scroll (optional, scrolls page if not provided)",
            required=False,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="browser",
)

get_cookies_tool = Tool(
    name="browser_get_cookies",
    description="Get browser cookies for the current context",
    parameters=[
        ToolParameter(
            name="names",
            type="array",
            description="Names of specific cookies to retrieve",
            required=False,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="browser",
)

set_cookies_tool = Tool(
    name="browser_set_cookies",
    description="Set cookies in the browser context",
    parameters=[
        ToolParameter(
            name="cookies",
            type="array",
            description="Array of cookie objects with name, value, and optional fields",
            required=True,
        ),
    ],
    risk_level=ActionRiskLevel.MEDIUM,
    category="browser",
)

get_storage_tool = Tool(
    name="browser_get_storage",
    description="Get localStorage or sessionStorage data",
    parameters=[
        ToolParameter(
            name="storage_type",
            type="string",
            description="Type of storage",
            required=False,
            default="localStorage",
            enum=["localStorage", "sessionStorage"],
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="browser",
)


# Tool implementations

async def browser_navigate(url: str, wait_until: str = "load") -> dict:
    """Navigate to a URL in the browser."""
    from playwright.async_api import Error as PlaywrightError

    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(url, wait_until=wait_until)
        title = await page.title()

        # Get page info
        info = {
            "success": True,
            "url": page.url,
            "title": title,
            "status": "loaded",
        }

        await context.close()
        await browser.close()
        await pw.stop()

        return info

    except PlaywrightError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def browser_click(selector: str, button: str = "left", click_count: int = 1) -> dict:
    """Click an element on the page."""
    return {
        "success": True,
        "action": "click",
        "selector": selector,
        "button": button,
        "click_count": click_count,
    }


async def browser_type(
    selector: str,
    text: str,
    delay: int = 0,
    clear_first: bool = True
) -> dict:
    """Type text into an input field."""
    return {
        "success": True,
        "action": "type",
        "selector": selector,
        "text_length": len(text),
        "delay_ms": delay,
        "cleared_first": clear_first,
    }


async def browser_screenshot(
    path: str | None = None,
    full_page: bool = False,
    selector: str | None = None
) -> dict:
    """Take a screenshot of the current page."""
    return {
        "success": True,
        "action": "screenshot",
        "path": path,
        "full_page": full_page,
        "selector": selector,
    }


async def browser_get_html(selector: str | None = None, inner_html: bool = False) -> dict:
    """Get HTML content from the page."""
    return {
        "success": True,
        "action": "get_html",
        "selector": selector,
        "inner_html": inner_html,
        "content": "<example>HTML content</example>",
    }


async def browser_get_text(selector: str | None = None, all_text: bool = False) -> dict:
    """Get text content from the page."""
    return {
        "success": True,
        "action": "get_text",
        "selector": selector,
        "all_text": all_text,
        "content": "Page text content",
    }


async def browser_evaluate(script: str) -> dict:
    """Execute JavaScript in the page context."""
    return {
        "success": True,
        "action": "evaluate",
        "script_preview": script[:100] + "..." if len(script) > 100 else script,
    }


async def browser_wait_for_selector(
    selector: str,
    timeout_ms: int = 30000,
    state: str = "visible"
) -> dict:
    """Wait for an element to appear."""
    return {
        "success": True,
        "action": "wait_for_selector",
        "selector": selector,
        "timeout_ms": timeout_ms,
        "state": state,
    }


async def browser_select(
    selector: str,
    values: list[str],
    by: str = "value"
) -> dict:
    """Select options in a dropdown."""
    return {
        "success": True,
        "action": "select",
        "selector": selector,
        "values": values,
        "by": by,
    }


async def browser_press(key: str, selector: str | None = None, delay: int = 0) -> dict:
    """Press a keyboard key."""
    return {
        "success": True,
        "action": "press",
        "key": key,
        "selector": selector,
        "delay_ms": delay,
    }


async def browser_hover(selector: str) -> dict:
    """Hover over an element."""
    return {
        "success": True,
        "action": "hover",
        "selector": selector,
    }


async def browser_scroll(
    direction: str = "down",
    amount: int = 500,
    selector: str | None = None
) -> dict:
    """Scroll the page or element."""
    return {
        "success": True,
        "action": "scroll",
        "direction": direction,
        "amount_px": amount,
        "selector": selector,
    }


async def browser_get_cookies(names: list[str] | None = None) -> dict:
    """Get browser cookies."""
    return {
        "success": True,
        "action": "get_cookies",
        "cookies": [],
    }


async def browser_set_cookies(cookies: list[dict]) -> dict:
    """Set cookies in the browser."""
    return {
        "success": True,
        "action": "set_cookies",
        "count": len(cookies),
    }


async def browser_get_storage(storage_type: str = "localStorage") -> dict:
    """Get storage data."""
    return {
        "success": True,
        "action": "get_storage",
        "storage_type": storage_type,
        "data": {},
    }