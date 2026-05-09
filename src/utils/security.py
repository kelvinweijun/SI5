
"""
Security Module
Input validation, sanitization, and access control.
"""

import re
import hashlib
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

@dataclass
class SecurityPolicy:
    """Security configuration."""
    max_message_length: int = 4000
    max_file_size: int = 25 * 1024 * 1024
    allowed_file_extensions: List[str] = None
    blocked_patterns: List[str] = None
    rate_limit_requests: int = 30
    rate_limit_window: int = 60

    def __post_init__(self):
        if self.allowed_file_extensions is None:
            self.allowed_file_extensions = [
                '.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.go', '.rs',
                '.rb', '.php', '.swift', '.kt', '.scala', '.r', '.m', '.sql',
                '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.toml',
                '.md', '.txt', '.rst', '.csv', '.log', '.ini', '.cfg'
            ]
        if self.blocked_patterns is None:
            self.blocked_patterns = [
                r'<script', r'javascript:', r'on\w+\s*=',
                r'\b(?:eval|exec)\s*\(', r'__import__', r'__subclasses__',
                r'os\.system', r'subprocess\.', r'pty\.', r'ctypes'
            ]

class InputValidator:
    """Validates and sanitizes user inputs."""

    def __init__(self, policy: SecurityPolicy = None):
        self.policy = policy or SecurityPolicy()

    def sanitize_message(self, message: str) -> str:
        """Sanitize a user message."""
        # Remove null bytes
        message = message.replace('\x00', '')

        # Truncate if too long
        if len(message) > self.policy.max_message_length:
            message = message[:self.policy.max_message_length] + '... [truncated]'

        return message

    def validate_code(self, code: str) -> tuple[bool, Optional[str]]:
        """Validate code for dangerous patterns."""
        for pattern in self.policy.blocked_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return False, f"Blocked pattern detected: {pattern}"

        return True, None

    def validate_file(self, filename: str, file_size: int) -> tuple[bool, Optional[str]]:
        """Validate file upload."""
        if file_size > self.policy.max_file_size:
            return False, f"File too large ({file_size / 1024 / 1024:.1f}MB > {self.policy.max_file_size / 1024 / 1024:.1f}MB)"

        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        full_ext = '.' + ext

        if full_ext not in self.policy.allowed_file_extensions and ext not in ['zip', 'gz', 'tar']:
            return False, f"File type .{ext} not allowed"

        return True, None

    def hash_user_id(self, user_id: str) -> str:
        """Hash user ID for privacy."""
        return hashlib.sha256(user_id.encode()).hexdigest()[:16]

class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests: Dict[str, List[float]] = {}

    def is_allowed(self, key: str) -> bool:
        """Check if request is within rate limit."""
        import time
        now = time.time()

        if key not in self.requests:
            self.requests[key] = []

        # Clean old requests
        self.requests[key] = [t for t in self.requests[key] if now - t < self.window]

        if len(self.requests[key]) >= self.max_requests:
            return False

        self.requests[key].append(now)
        return True

    def get_remaining(self, key: str) -> int:
        """Get remaining requests in window."""
        import time
        now = time.time()

        if key not in self.requests:
            return self.max_requests

        self.requests[key] = [t for t in self.requests[key] if now - t < self.window]
        return max(0, self.max_requests - len(self.requests[key]))
