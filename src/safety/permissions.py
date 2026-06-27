from __future__ import annotations
"""Permission management for agent actions."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from ..core.tool_schema import ActionRiskLevel


class Permission(str, Enum):
    """Available permissions."""

    FILE_READ = "file:read"
    FILE_WRITE = "file:write"
    FILE_DELETE = "file:delete"
    NETWORK_ACCESS = "network:access"
    BROWSER_CONTROL = "browser:control"
    DESKTOP_CONTROL = "desktop:control"
    SYSTEM_EXECUTE = "system:execute"
    SYSTEM_INFO = "system:info"
    SCHEDULER_MANAGE = "scheduler:manage"
    CREDENTIAL_ACCESS = "credential:access"


@dataclass
class PermissionGrant:
    """A permission grant to a user or session."""

    permission: Permission
    granted_by: str
    granted_at: datetime
    expires_at: datetime | None
    conditions: dict[str, Any] | None = None

    def is_valid(self) -> bool:
        """Check if the grant is still valid."""
        if self.expires_at and datetime.now() > self.expires_at:
            return False
        return True


@dataclass
class PermissionSet:
    """A set of permissions for a user or session."""

    grants: dict[Permission, PermissionGrant] = field(default_factory=dict)

    def add_grant(self, grant: PermissionGrant) -> None:
        """Add a permission grant."""
        self.grants[grant.permission] = grant

    def has_permission(self, permission: Permission) -> bool:
        """Check if this set has a permission."""
        grant = self.grants.get(permission)
        if not grant:
            return False
        return grant.is_valid()

    def get_active_grants(self) -> list[PermissionGrant]:
        """Get all currently valid grants."""
        return [g for g in self.grants.values() if g.is_valid()]


class PermissionManager:
    """
    Manage permissions for agent actions.

    Implements the principle of least privilege by:
    - Requiring explicit permission grants
    - Time-limited permissions
    - Conditional permissions based on context
    """

    def __init__(self):
        self._permissions: dict[str, PermissionSet] = {}  # user/session ID -> permissions
        self._default_permissions: list[Permission] = [
            Permission.FILE_READ,
            Permission.SYSTEM_INFO,
        ]
        self._elevated_permissions: list[Permission] = [
            Permission.FILE_DELETE,
            Permission.SYSTEM_EXECUTE,
            Permission.CREDENTIAL_ACCESS,
        ]

    def get_permissions(self, user_id: str) -> PermissionSet:
        """Get permission set for a user."""
        if user_id not in self._permissions:
            self._permissions[user_id] = PermissionSet()
        return self._permissions[user_id]

    def grant_permission(
        self,
        user_id: str,
        permission: Permission,
        granted_by: str = "system",
        duration_minutes: int | None = None,
        conditions: dict | None = None,
    ) -> PermissionGrant:
        """Grant a permission to a user."""
        expires_at = None
        if duration_minutes:
            from datetime import timedelta
            expires_at = datetime.now() + timedelta(minutes=duration_minutes)

        grant = PermissionGrant(
            permission=permission,
            granted_by=granted_by,
            granted_at=datetime.now(),
            expires_at=expires_at,
            conditions=conditions,
        )

        perms = self.get_permissions(user_id)
        perms.add_grant(grant)

        return grant

    def revoke_permission(self, user_id: str, permission: Permission) -> bool:
        """Revoke a permission from a user."""
        if user_id in self._permissions:
            if permission in self._permissions[user_id].grants:
                del self._permissions[user_id].grants[permission]
                return True
        return False

    def check_permission(
        self,
        user_id: str,
        permission: Permission,
        context: dict | None = None,
    ) -> tuple[bool, str | None]:
        """
        Check if a user has a permission.

        Returns (allowed, reason_if_denied).
        """
        perms = self.get_permissions(user_id)

        # Check if permission is granted
        if perms.has_permission(permission):
            return True, None

        # Check conditions if any
        grant = perms.grants.get(permission)
        if grant and grant.conditions:
            # Evaluate conditions
            for key, value in grant.conditions.items():
                if context and context.get(key) != value:
                    return False, f"Condition not met: {key} must be {value}"

        # Permission not granted
        return False, f"Permission {permission.value} not granted"

    def check_risk_level(
        self,
        user_id: str,
        risk_level: ActionRiskLevel,
    ) -> tuple[bool, str | None]:
        """Check if user can perform actions at a given risk level."""
        required_permissions = {
            ActionRiskLevel.LOW: [],
            ActionRiskLevel.MEDIUM: [Permission.FILE_WRITE, Permission.BROWSER_CONTROL],
            ActionRiskLevel.HIGH: [Permission.FILE_DELETE, Permission.SYSTEM_EXECUTE],
            ActionRiskLevel.CRITICAL: [Permission.SYSTEM_EXECUTE],
        }

        needed = required_permissions.get(risk_level, [])

        for perm in needed:
            allowed, reason = self.check_permission(user_id, perm)
            if not allowed:
                return False, reason

        return True, None

    def get_user_info(self, user_id: str) -> dict:
        """Get permission information for a user."""
        perms = self.get_permissions(user_id)
        grants = []

        for perm, grant in perms.grants.items():
            grants.append({
                "permission": perm.value,
                "granted_by": grant.granted_by,
                "granted_at": grant.granted_at.isoformat(),
                "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
                "valid": grant.is_valid(),
            })

        return {
            "user_id": user_id,
            "active_grants": len(perms.get_active_grants()),
            "grants": grants,
        }

    def cleanup_expired(self) -> int:
        """Remove expired permission grants."""
        count = 0
        for user_id in self._permissions:
            expired = [
                perm for perm, grant in self._permissions[user_id].grants.items()
                if not grant.is_valid()
            ]
            for perm in expired:
                del self._permissions[user_id].grants[perm]
                count += 1
        return count
