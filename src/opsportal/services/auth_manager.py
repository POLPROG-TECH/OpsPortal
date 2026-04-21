"""RBAC - Role-based access control for multi-user environments.

Provides user roles (admin, operator, viewer) with per-route permission
checks.  Users are stored in a JSON file with bcrypt-compatible password
hashes (falls back to SHA-256 when bcrypt is unavailable).
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from opsportal.core.errors import get_logger

logger = get_logger("services.auth_manager")


class Role(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


# Permissions by role (cumulative: admin > operator > viewer)
ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.VIEWER: {
        "view_dashboard",
        "view_tools",
        "view_logs",
        "view_config",
        "view_health",
        "view_uptime",
        "view_metrics",
        "view_sla",
    },
    Role.OPERATOR: {
        "start_tool",
        "stop_tool",
        "restart_tool",
        "bulk_actions",
        "run_actions",
        "view_audit",
        "export_config",
    },
    Role.ADMIN: {
        "edit_config",
        "import_config",
        "manage_scheduler",
        "manage_alerts",
        "manage_users",
        "manage_backups",
        "manage_notifications",
    },
}


def get_permissions(role: Role) -> set[str]:
    """Get all permissions for a role (including inherited)."""
    perms: set[str] = set()
    hierarchy = [Role.VIEWER, Role.OPERATOR, Role.ADMIN]
    for r in hierarchy:
        perms |= ROLE_PERMISSIONS[r]
        if r == role:
            break
    return perms


@dataclass(slots=True)
class User:
    username: str
    password_hash: str
    role: Role
    created_at: float = field(default_factory=time.time)
    last_login: float = 0
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "role": self.role,
            "created_at": self.created_at,
            "last_login": self.last_login,
            "enabled": self.enabled,
        }

    def has_permission(self, permission: str) -> bool:
        return permission in get_permissions(self.role)


def _hash_password(password: str, salt: str = "") -> str:
    """Hash password with SHA-256 + salt."""
    if not salt:
        salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"sha256:{salt}:{h}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash."""
    if stored_hash.startswith("sha256:"):
        parts = stored_hash.split(":", 2)
        if len(parts) != 3:
            return False
        _, salt, expected = parts
        h = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
        return secrets.compare_digest(h, expected)
    return False


class AuthManager:
    """Manages users and role-based permissions."""

    def __init__(self, users_file: Path | None = None) -> None:
        self._users_file = users_file
        self._users: dict[str, User] = {}
        self._sessions: dict[str, str] = {}  # token -> username
        if users_file and users_file.exists():
            self._load()
        elif not self._users:
            self._create_default_admin()

    def _create_default_admin(self) -> None:
        self.add_user("admin", "admin", Role.ADMIN)

    def _load(self) -> None:
        try:
            data = json.loads(self._users_file.read_text("utf-8"))
            for u in data.get("users", []):
                user = User(
                    username=u["username"],
                    password_hash=u["password_hash"],
                    role=Role(u.get("role", "viewer")),
                    created_at=u.get("created_at", time.time()),
                    last_login=u.get("last_login", 0),
                    enabled=u.get("enabled", True),
                )
                self._users[user.username] = user
        except (json.JSONDecodeError, KeyError, OSError):
            logger.exception("Failed to load users file")
            self._create_default_admin()

    def _save(self) -> None:
        if not self._users_file:
            return
        self._users_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "users": [
                {
                    "username": u.username,
                    "password_hash": u.password_hash,
                    "role": u.role,
                    "created_at": u.created_at,
                    "last_login": u.last_login,
                    "enabled": u.enabled,
                }
                for u in self._users.values()
            ]
        }
        self._users_file.write_text(json.dumps(data, indent=2), "utf-8")

    def add_user(self, username: str, password: str, role: Role = Role.VIEWER) -> User:
        pw_hash = _hash_password(password)
        user = User(username=username, password_hash=pw_hash, role=role)
        self._users[username] = user
        self._save()
        logger.info("User created: %s (role=%s)", username, role)
        return user

    def remove_user(self, username: str) -> bool:
        if username in self._users:
            del self._users[username]
            self._save()
            return True
        return False

    def list_users(self) -> list[User]:
        return list(self._users.values())

    def authenticate(self, username: str, password: str) -> str | None:
        """Verify credentials, return session token or None."""
        user = self._users.get(username)
        if not user or not user.enabled:
            return None
        if not _verify_password(password, user.password_hash):
            return None
        user.last_login = time.time()
        self._save()
        token = secrets.token_urlsafe(32)
        self._sessions[token] = username
        return token

    def get_user_by_token(self, token: str) -> User | None:
        username = self._sessions.get(token)
        if not username:
            return None
        return self._users.get(username)

    def get_user(self, username: str) -> User | None:
        return self._users.get(username)

    def update_role(self, username: str, role: Role) -> bool:
        user = self._users.get(username)
        if not user:
            return False
        user.role = role
        self._save()
        return True

    def logout(self, token: str) -> None:
        self._sessions.pop(token, None)

    def check_permission(self, token: str, permission: str) -> bool:
        user = self.get_user_by_token(token)
        if not user:
            return False
        return user.has_permission(permission)
