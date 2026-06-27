from __future__ import annotations
"""File operations tools."""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from ..core.tool_schema import Tool, ToolParameter, ActionRiskLevel


# Tool definitions for file operations

read_file_tool = Tool(
    name="file_read",
    description="Read the contents of a file",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Path to the file",
            required=True,
        ),
        ToolParameter(
            name="encoding",
            type="string",
            description="File encoding",
            required=False,
            default="utf-8",
        ),
        ToolParameter(
            name="max_lines",
            type="number",
            description="Maximum number of lines to read",
            required=False,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="file",
)

write_file_tool = Tool(
    name="file_write",
    description="Write content to a file",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Path to the file",
            required=True,
        ),
        ToolParameter(
            name="content",
            type="string",
            description="Content to write",
            required=True,
        ),
        ToolParameter(
            name="encoding",
            type="string",
            description="File encoding",
            required=False,
            default="utf-8",
        ),
        ToolParameter(
            name="append",
            type="boolean",
            description="Append to existing file instead of overwriting",
            required=False,
            default=False,
        ),
    ],
    risk_level=ActionRiskLevel.HIGH,
    category="file",
)

list_directory_tool = Tool(
    name="file_list",
    description="List files and directories",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Directory path",
            required=True,
        ),
        ToolParameter(
            name="pattern",
            type="string",
            description="Glob pattern to filter files",
            required=False,
        ),
        ToolParameter(
            name="recursive",
            type="boolean",
            description="List recursively",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="include_hidden",
            type="boolean",
            description="Include hidden files",
            required=False,
            default=False,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="file",
)

copy_file_tool = Tool(
    name="file_copy",
    description="Copy a file or directory",
    parameters=[
        ToolParameter(
            name="source",
            type="string",
            description="Source path",
            required=True,
        ),
        ToolParameter(
            name="destination",
            type="string",
            description="Destination path",
            required=True,
        ),
        ToolParameter(
            name="overwrite",
            type="boolean",
            description="Overwrite if destination exists",
            required=False,
            default=False,
        ),
    ],
    risk_level=ActionRiskLevel.MEDIUM,
    category="file",
)

move_file_tool = Tool(
    name="file_move",
    description="Move a file or directory",
    parameters=[
        ToolParameter(
            name="source",
            type="string",
            description="Source path",
            required=True,
        ),
        ToolParameter(
            name="destination",
            type="string",
            description="Destination path",
            required=True,
        ),
        ToolParameter(
            name="overwrite",
            type="boolean",
            description="Overwrite if destination exists",
            required=False,
            default=False,
        ),
    ],
    risk_level=ActionRiskLevel.MEDIUM,
    category="file",
)

delete_file_tool = Tool(
    name="file_delete",
    description="Delete a file or directory (with confirmation preview)",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Path to delete",
            required=True,
        ),
        ToolParameter(
            name="recursive",
            type="boolean",
            description="Delete directories recursively",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="confirm_path",
            type="string",
            description="Confirmation: type the path again to confirm deletion",
            required=False,
        ),
    ],
    risk_level=ActionRiskLevel.CRITICAL,
    category="file",
)

create_directory_tool = Tool(
    name="file_mkdir",
    description="Create a directory",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Directory path to create",
            required=True,
        ),
        ToolParameter(
            name="parents",
            type="boolean",
            description="Create parent directories as needed",
            required=False,
            default=True,
        ),
    ],
    risk_level=ActionRiskLevel.MEDIUM,
    category="file",
)

get_file_info_tool = Tool(
    name="file_info",
    description="Get information about a file or directory",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Path to the file",
            required=True,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="file",
)

search_files_tool = Tool(
    name="file_search",
    description="Search for files by name pattern",
    parameters=[
        ToolParameter(
            name="directory",
            type="string",
            description="Directory to search in",
            required=True,
        ),
        ToolParameter(
            name="pattern",
            type="string",
            description="Search pattern (glob or regex)",
            required=True,
        ),
        ToolParameter(
            name="recursive",
            type="boolean",
            description="Search recursively",
            required=False,
            default=True,
        ),
        ToolParameter(
            name="use_regex",
            type="boolean",
            description="Use regex instead of glob",
            required=False,
            default=False,
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="file",
)

get_file_hash_tool = Tool(
    name="file_hash",
    description="Calculate hash of a file",
    parameters=[
        ToolParameter(
            name="path",
            type="string",
            description="Path to the file",
            required=True,
        ),
        ToolParameter(
            name="algorithm",
            type="string",
            description="Hash algorithm (md5, sha1, sha256)",
            required=False,
            default="sha256",
            enum=["md5", "sha1", "sha256"],
        ),
    ],
    risk_level=ActionRiskLevel.LOW,
    category="file",
)


# Tool implementations

async def file_read(
    path: str,
    encoding: str = "utf-8",
    max_lines: int | None = None
) -> dict:
    """Read file contents."""
    try:
        p = Path(path)
        if not p.exists():
            return {"success": False, "error": f"File not found: {path}"}

        with open(p, "r", encoding=encoding) as f:
            if max_lines:
                lines = [f.readline() for _ in range(max_lines)]
                content = "".join(lines)
            else:
                content = f.read()

        return {
            "success": True,
            "path": str(p.absolute()),
            "size_bytes": p.stat().st_size,
            "lines": content.count("\n") + 1,
            "content": content,
            "truncated": max_lines is not None and len(content.split("\n")) >= max_lines,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def file_write(
    path: str,
    content: str,
    encoding: str = "utf-8",
    append: bool = False
) -> dict:
    """Write content to a file."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)

        mode = "a" if append else "w"
        with open(p, mode, encoding=encoding) as f:
            f.write(content)

        return {
            "success": True,
            "path": str(p.absolute()),
            "bytes_written": len(content.encode(encoding)),
            "appended": append,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def file_list(
    path: str,
    pattern: str | None = None,
    recursive: bool = False,
    include_hidden: bool = False
) -> dict:
    """List directory contents."""
    try:
        p = Path(path)
        if not p.exists():
            return {"success": False, "error": f"Directory not found: {path}"}

        if not p.is_dir():
            return {"success": False, "error": f"Not a directory: {path}"}

        items = []
        if recursive:
            iterator = p.rglob("*")
        else:
            iterator = p.iterdir()

        for item in iterator:
            if not include_hidden and item.name.startswith("."):
                continue

            if pattern:
                import fnmatch
                if not fnmatch.fnmatch(item.name, pattern):
                    continue

            stat = item.stat()
            items.append({
                "name": item.name,
                "path": str(item),
                "is_dir": item.is_dir(),
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

        return {
            "success": True,
            "directory": str(p.absolute()),
            "count": len(items),
            "items": items,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def file_copy(source: str, destination: str, overwrite: bool = False) -> dict:
    """Copy a file or directory."""
    try:
        src = Path(source)
        dst = Path(destination)

        if not src.exists():
            return {"success": False, "error": f"Source not found: {source}"}

        if dst.exists() and not overwrite:
            return {"success": False, "error": f"Destination exists: {destination}"}

        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=overwrite)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        return {
            "success": True,
            "source": str(src.absolute()),
            "destination": str(dst.absolute()),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def file_move(source: str, destination: str, overwrite: bool = False) -> dict:
    """Move a file or directory."""
    try:
        src = Path(source)
        dst = Path(destination)

        if not src.exists():
            return {"success": False, "error": f"Source not found: {source}"}

        if dst.exists():
            if overwrite:
                if dst.is_dir():
                    shutil.rmtree(dst)
                else:
                    dst.unlink()
            else:
                return {"success": False, "error": f"Destination exists: {destination}"}

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))

        return {
            "success": True,
            "source": str(src.absolute()),
            "destination": str(dst.absolute()),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def file_delete(
    path: str,
    recursive: bool = False,
    confirm_path: str | None = None
) -> dict:
    """Delete a file or directory."""
    # Safety: require confirmation for critical operations
    if confirm_path and confirm_path != path:
        return {"success": False, "error": "Confirmation path does not match"}

    try:
        p = Path(path)
        if not p.exists():
            return {"success": False, "error": f"Path not found: {path}"}

        # Dry run info
        info = {
            "success": True,
            "action": "delete_preview",
            "path": str(p.absolute()),
            "is_dir": p.is_dir(),
            "requires_confirmation": True,
        }

        if p.is_dir():
            if recursive:
                info["files_count"] = sum(1 for _ in p.rglob("*"))
            else:
                info["files_count"] = sum(1 for _ in p.iterdir())

        return info
    except Exception as e:
        return {"success": False, "error": str(e)}


async def file_mkdir(path: str, parents: bool = True) -> dict:
    """Create a directory."""
    try:
        p = Path(path)
        p.mkdir(parents=parents, exist_ok=True)

        return {
            "success": True,
            "path": str(p.absolute()),
            "created": True,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def file_info(path: str) -> dict:
    """Get file/directory information."""
    try:
        p = Path(path)
        if not p.exists():
            return {"success": False, "error": f"Path not found: {path}"}

        stat = p.stat()
        info = {
            "success": True,
            "path": str(p.absolute()),
            "name": p.name,
            "is_dir": p.is_dir(),
            "is_file": p.is_file(),
            "size_bytes": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "accessed": datetime.fromtimestamp(stat.st_atime).isoformat(),
        }

        if p.is_file():
            info["extension"] = p.suffix
            info["parent"] = str(p.parent)

        return info
    except Exception as e:
        return {"success": False, "error": str(e)}


async def file_search(
    directory: str,
    pattern: str,
    recursive: bool = True,
    use_regex: bool = False
) -> dict:
    """Search for files."""
    try:
        import re

        dir_path = Path(directory)
        if not dir_path.exists():
            return {"success": False, "error": f"Directory not found: {directory}"}

        matches = []
        if recursive:
            iterator = dir_path.rglob("*")
        else:
            iterator = dir_path.glob("*")

        if use_regex:
            regex = re.compile(pattern)
            for item in iterator:
                if item.is_file() and regex.search(item.name):
                    matches.append(str(item))
        else:
            import fnmatch
            for item in iterator:
                if item.is_file() and fnmatch.fnmatch(item.name, pattern):
                    matches.append(str(item))

        return {
            "success": True,
            "directory": str(dir_path.absolute()),
            "pattern": pattern,
            "count": len(matches),
            "matches": matches[:100],  # Limit results
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def file_hash(path: str, algorithm: str = "sha256") -> dict:
    """Calculate file hash."""
    try:
        import hashlib

        p = Path(path)
        if not p.exists():
            return {"success": False, "error": f"File not found: {path}"}

        h = hashlib.new(algorithm)
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)

        return {
            "success": True,
            "path": str(p.absolute()),
            "algorithm": algorithm,
            "hash": h.hexdigest(),
            "size_bytes": p.stat().st_size,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
