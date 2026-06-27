"""
Win11-OmniAgent Safety Package

Provides:
- Audit trail (immutable logging)
- Rate limiting and circuit breakers
- Action sandboxing (dry-run mode)
- Permission management
- PII detection and redaction
"""

from .audit import AuditLogger, AuditEntry
from .rate_limiter import RateLimiter, CircuitBreaker
from .sandbox import ActionSandbox, DryRunExecutor
from .permissions import PermissionManager
from .redaction import PIIRedactor

__all__ = [
    "AuditLogger",
    "AuditEntry",
    "RateLimiter",
    "CircuitBreaker",
    "ActionSandbox",
    "DryRunExecutor",
    "PermissionManager",
    "PIIRedactor",
]