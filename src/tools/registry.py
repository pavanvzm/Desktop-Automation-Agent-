"""Tool registry for default tools."""

from ..core.tool_schema import get_registry, ToolRegistry

from .browser import (
    navigate_tool, click_tool, type_tool, screenshot_tool, get_html_tool,
    get_text_tool, evaluate_tool, wait_for_selector_tool, select_tool,
    press_tool, hover_tool, scroll_tool, get_cookies_tool, set_cookies_tool,
    get_storage_tool,
    browser_navigate, browser_click, browser_type, browser_screenshot,
    browser_get_html, browser_get_text, browser_evaluate, browser_wait_for_selector,
    browser_select, browser_press, browser_hover, browser_scroll,
    browser_get_cookies, browser_set_cookies, browser_get_storage,
)

from .desktop import (
    get_windows_tool, get_active_window_tool, click_element_tool, type_text_tool,
    press_key_tool, get_element_tool, get_ui_tree_tool, launch_app_tool,
    close_window_tool, minimize_window_tool, maximize_window_tool,
    wait_for_window_tool, find_image_tool, click_position_tool,
    desktop_get_windows, desktop_get_active_window, desktop_click_element,
    desktop_type_text, desktop_press_key, desktop_get_element, desktop_get_ui_tree,
    desktop_launch_app, desktop_close_window, desktop_minimize_window,
    desktop_maximize_window, desktop_wait_for_window, desktop_find_image,
    desktop_click_position,
)

from .files import (
    read_file_tool, write_file_tool, list_directory_tool, copy_file_tool,
    move_file_tool, delete_file_tool, create_directory_tool, get_file_info_tool,
    search_files_tool, get_file_hash_tool,
    file_read, file_write, file_list, file_copy, file_move, file_delete,
    file_mkdir, file_info, file_search, file_hash,
)

from .system import (
    get_system_info_tool, get_cpu_info_tool, get_memory_info_tool, get_disk_info_tool,
    get_network_info_tool, get_processes_tool, kill_process_tool, run_command_tool,
    get_environment_vars_tool, get_uptime_tool, screenshot_tool, open_url_tool,
    get_clipboard_tool, set_clipboard_tool, get_volume_tool,
    system_info, system_cpu, system_memory, system_disk, system_network,
    system_processes, system_kill_process, system_run_command, system_env,
    system_uptime, system_screenshot, system_open_url, system_clipboard_get,
    system_clipboard_set, system_volume,
)


def get_default_tools() -> ToolRegistry:
    """Get a registry populated with all default tools."""
    registry = get_registry()

    # Browser tools
    registry.register(navigate_tool, browser_navigate)
    registry.register(click_tool, browser_click)
    registry.register(type_tool, browser_type)
    registry.register(screenshot_tool, browser_screenshot)
    registry.register(get_html_tool, browser_get_html)
    registry.register(get_text_tool, browser_get_text)
    registry.register(evaluate_tool, browser_evaluate)
    registry.register(wait_for_selector_tool, browser_wait_for_selector)
    registry.register(select_tool, browser_select)
    registry.register(press_tool, browser_press)
    registry.register(hover_tool, browser_hover)
    registry.register(scroll_tool, browser_scroll)
    registry.register(get_cookies_tool, browser_get_cookies)
    registry.register(set_cookies_tool, browser_set_cookies)
    registry.register(get_storage_tool, browser_get_storage)

    # Desktop tools
    registry.register(get_windows_tool, desktop_get_windows)
    registry.register(get_active_window_tool, desktop_get_active_window)
    registry.register(click_element_tool, desktop_click_element)
    registry.register(type_text_tool, desktop_type_text)
    registry.register(press_key_tool, desktop_press_key)
    registry.register(get_element_tool, desktop_get_element)
    registry.register(get_ui_tree_tool, desktop_get_ui_tree)
    registry.register(launch_app_tool, desktop_launch_app)
    registry.register(close_window_tool, desktop_close_window)
    registry.register(minimize_window_tool, desktop_minimize_window)
    registry.register(maximize_window_tool, desktop_maximize_window)
    registry.register(wait_for_window_tool, desktop_wait_for_window)
    registry.register(find_image_tool, desktop_find_image)
    registry.register(click_position_tool, desktop_click_position)

    # File tools
    registry.register(read_file_tool, file_read)
    registry.register(write_file_tool, file_write)
    registry.register(list_directory_tool, file_list)
    registry.register(copy_file_tool, file_copy)
    registry.register(move_file_tool, file_move)
    registry.register(delete_file_tool, file_delete)
    registry.register(create_directory_tool, file_mkdir)
    registry.register(get_file_info_tool, file_info)
    registry.register(search_files_tool, file_search)
    registry.register(get_file_hash_tool, file_hash)

    # System tools
    registry.register(get_system_info_tool, system_info)
    registry.register(get_cpu_info_tool, system_cpu)
    registry.register(get_memory_info_tool, system_memory)
    registry.register(get_disk_info_tool, system_disk)
    registry.register(get_network_info_tool, system_network)
    registry.register(get_processes_tool, system_processes)
    registry.register(kill_process_tool, system_kill_process)
    registry.register(run_command_tool, system_run_command)
    registry.register(get_environment_vars_tool, system_env)
    registry.register(get_uptime_tool, system_uptime)
    registry.register(screenshot_tool, system_screenshot)
    registry.register(open_url_tool, system_open_url)
    registry.register(get_clipboard_tool, system_clipboard_get)
    registry.register(set_clipboard_tool, system_clipboard_set)
    registry.register(get_volume_tool, system_volume)

    return registry