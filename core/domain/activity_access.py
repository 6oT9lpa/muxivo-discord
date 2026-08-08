MODULE_ORDER = (
    "dashboard",
    "access",
    "welcome",
    "role-panels",
    "creator-alerts",
    "dev-blog",
    "muxivo-core",
    "logs",
    "server-stats",
    "voice-rooms",
    "bot-settings",
    "integrations",
    "health",
)

DISCORD_ADMINISTRATOR_PERMISSION = 0x0000000000000008

# Synced guild members always see these tabs; unsynced guilds still fail with 403.
DEFAULT_VISIBLE_MODULES = (
    "dashboard",
    "health",
)

# Access Roles edits only these tabs. Administrator keeps full immutable access.
ACCESS_ROLE_CONFIGURABLE_MODULES = (
    "welcome",
    "role-panels",
    "creator-alerts",
    "dev-blog",
    "muxivo-core",
    "logs",
    "bot-settings",
)

PERMISSION_ORDER = ("disabled", "view", "edit", "publish", "manage")


def modules_with_defaults(extra: dict[str, str] | None = None) -> dict[str, str]:
    modules = {key: "view" for key in DEFAULT_VISIBLE_MODULES}
    if extra:
        modules.update(extra)
    return modules


BUILTIN_ACCESS_ROLES: tuple[dict[str, object], ...] = (
    {"slug": "user", "name": "User", "modules": modules_with_defaults()},
    {
        "slug": "creator",
        "name": "Creator",
        "modules": modules_with_defaults({"creator-alerts": "edit"}),
    },
    {
        "slug": "developer",
        "name": "Developer",
        "modules": modules_with_defaults({"dev-blog": "publish"}),
    },
    {
        "slug": "moderator",
        "name": "Moderator",
        "modules": modules_with_defaults({"muxivo-core": "view", "logs": "view"}),
    },
    {
        "slug": "administrator",
        "name": "Administrator",
        "modules": {key: "manage" for key in MODULE_ORDER},
    },
)
