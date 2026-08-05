"""API roles and role-based access rules for the two-Mac architecture.

A deployment credential can never approve agent actions or read personal data. An iPhone user token
can never deploy backend code. See docs/PERMISSION_MATRIX.md.
"""

from __future__ import annotations

from app.core.models import DeviceRole

# Capabilities keyed by role.
_ROLE_CAPABILITIES: dict[DeviceRole, set[str]] = {
    DeviceRole.iphone_user: {
        "chat",
        "view_personal_data",
        "approve_actions",
        "manage_tasks",
        "manage_cases",
        "use_integrations",
        "change_user_rules",
    },
    DeviceRole.deploy_admin: {
        "deploy",
        "service_health",
        "restart_service",
        "view_sanitized_logs",
        "run_migrations",
        "rollback",
    },
    DeviceRole.owner: {
        "init_secrets",
        "manage_integrations",
        "manage_devices",
        "manage_backups",
        "emergency_recovery",
        # The owner (Backend Mac holder) can also act as the primary user.
        "chat",
        "view_personal_data",
        "approve_actions",
        "manage_tasks",
        "manage_cases",
        "use_integrations",
        "change_user_rules",
    },
}


def role_has_capability(role: DeviceRole, capability: str) -> bool:
    return capability in _ROLE_CAPABILITIES.get(role, set())


def require_capability(role: DeviceRole, capability: str) -> None:
    if not role_has_capability(role, capability):
        raise PermissionError(
            f"Role '{role.value}' is not permitted to perform '{capability}'."
        )
