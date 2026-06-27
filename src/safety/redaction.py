"""PII detection and redaction for privacy."""

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class RedactionPattern:
    """A pattern for detecting PII."""

    name: str
    pattern: str
    replacement: str = "[REDACTED]"
    confidence: float = 1.0


class PIIRedactor:
    """
    Detect and redact Personally Identifiable Information (PII).

    Patterns include:
    - Email addresses
    - Phone numbers
    - Social Security Numbers
    - Credit card numbers
    - API keys/tokens
    - IP addresses
    """

    def __init__(self):
        self._patterns = [
            # Email addresses
            RedactionPattern(
                name="email",
                pattern=r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            ),
            # Phone numbers (US formats)
            RedactionPattern(
                name="phone_us",
                pattern=r'\b(?:\+?1[-.]?)?\(?[0-9]{3}\)?[-.]?[0-9]{3}[-.]?[0-9]{4}\b',
            ),
            # SSN
            RedactionPattern(
                name="ssn",
                pattern=r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',
            ),
            # Credit card numbers
            RedactionPattern(
                name="credit_card",
                pattern=r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
            ),
            # API keys (generic patterns)
            RedactionPattern(
                name="api_key",
                pattern=r'\b(?:api[_-]?key|apikey|api[_-]?token)["\']?\s*[:=]\s*["\']?[\w-]{20,}["\']?',
                confidence=0.8,
            ),
            # Bearer tokens
            RedactionPattern(
                name="bearer_token",
                pattern=r'\bBearer\s+[A-Za-z0-9\-_.~+/]+\b',
            ),
            # GitHub tokens
            RedactionPattern(
                name="github_token",
                pattern=r'\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}\b',
            ),
            # AWS keys
            RedactionPattern(
                name="aws_key",
                pattern=r'\b(?:AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}\b',
            ),
            # IP addresses
            RedactionPattern(
                name="ip_address",
                pattern=r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
                confidence=0.7,
            ),
            # Dates of birth
            RedactionPattern(
                name="dob",
                pattern=r'\b(?:born|dob|birth(?:_?date)?)[:\s]+(?:(?:0?[1-9]|1[0-2])[/\-](?:0?[1-9]|[12]\d|3[01])[/\-](?:19|20)\d{2}|(?:19|20)\d{2}[/\-](?:0?[1-9]|1[0-2])[/\-](?:0?[1-9]|[12]\d|3[01]))\b',
                confidence=0.6,
            ),
        ]

    def redact(self, text: str, replacement: str = "[REDACTED]") -> tuple[str, list[dict]]:
        """
        Redact PII from text.

        Returns (redacted_text, list_of_detected_pii).
        """
        detected = []

        for pattern in self._patterns:
            matches = re.finditer(pattern.pattern, text, re.IGNORECASE)
            for match in matches:
                detected.append({
                    "type": pattern.name,
                    "value": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                    "confidence": pattern.confidence,
                })

        # Sort by position (descending) to replace from end to start
        detected.sort(key=lambda x: x["start"], reverse=True)

        redacted = text
        for pii in detected:
            redacted = (
                redacted[:pii["start"]]
                + replacement
                + redacted[pii["end"]:]
            )
            # Adjust positions for subsequent replacements
            for later in detected:
                if later["start"] > pii["start"]:
                    offset = len(replacement) - (pii["end"] - pii["start"])
                    later["start"] += offset
                    later["end"] += offset

        return redacted, detected

    def redact_dict(
        self,
        data: dict,
        replacement: str = "[REDACTED]",
    ) -> tuple[dict, list[dict]]:
        """Redact PII from a dictionary."""
        all_detected = []

        def recursive_redact(obj):
            if isinstance(obj, dict):
                return {k: recursive_redact(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [recursive_redact(item) for item in obj]
            elif isinstance(obj, str):
                redacted, detected = self.redact(obj, replacement)
                for d in detected:
                    d["key"] = None  # Could track key path
                all_detected.extend(detected)
                return redacted
            return obj

        redacted_data = recursive_redact(data)
        return redacted_data, all_detected

    def add_pattern(
        self,
        name: str,
        pattern: str,
        replacement: str = "[REDACTED]",
        confidence: float = 1.0,
    ) -> None:
        """Add a custom PII pattern."""
        self._patterns.append(RedactionPattern(
            name=name,
            pattern=pattern,
            replacement=replacement,
            confidence=confidence,
        ))

    def get_stats(self, texts: list[str]) -> dict:
        """Get statistics about PII found in texts."""
        stats = {p.name: 0 for p in self._patterns}
        stats["total_detections"] = 0

        for text in texts:
            _, detected = self.redact(text)
            for item in detected:
                if item["name"] in stats:
                    stats[item["name"]] += 1
                stats["total_detections"] += 1

        return stats


class ContextAwareRedactor(PIIRedactor):
    """PII redactor with context awareness."""

    def __init__(self):
        super().__init__()
        # Additional context-based patterns
        self._context_patterns = [
            # Password fields
            (r'(?i)(?:password|passwd|pwd)["\']?\s*[:=]\s*["\']?([^\s"\'}]+)', "password_field"),
            # Secret fields
            (r'(?i)(?:secret|private[_-]?key)["\']?\s*[:=]\s*["\']?([^\s"\'}]+)', "secret_field"),
            # Token fields
            (r'(?i)(?:token|auth[_-]?token|access[_-]?token)["\']?\s*[:=]\s*["\']?([^\s"\'}]+)', "token_field"),
        ]

    def redact(self, text: str, replacement: str = "[REDACTED]") -> tuple[str, list[dict]]:
        """Redact with context awareness."""
        detected = []

        # First run standard patterns
        redacted, detected = super().redact(text, replacement)

        # Then apply context patterns
        for pattern, pii_type in self._context_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                if len(match.groups()) > 0:
                    value = match.group(1)
                    # Only redact if not already redacted
                    if value not in redacted:
                        redacted = redacted.replace(value, replacement)
                        detected.append({
                            "type": pii_type,
                            "value": value,
                            "start": match.start(1),
                            "end": match.end(1),
                            "confidence": 1.0,
                        })

        return redacted, detected