import discord
from enum import IntEnum
from utils.config import config

class PermLevel(IntEnum):
    MEMBER = 0
    SUPPORT = 5
    MOD = 10
    ADMIN = 20
    DEV = 30
    CO_OWNER = 35
    OWNER = 40

def get_role_to_level() -> dict:
    mapping = {
        # Member-Rollen
        config.roles.get("member_1"): PermLevel.MEMBER,
        config.roles.get("member_2"): PermLevel.MEMBER,
        config.roles.get("member_3"): PermLevel.MEMBER,
        config.roles.get("member_4"): PermLevel.MEMBER,

        # Staff-Rollen
        config.roles.get("supporter"): PermLevel.SUPPORT,
        config.roles.get("moderator"): PermLevel.MOD,
        config.roles.get("admin"): PermLevel.ADMIN,
        config.roles.get("dev"): PermLevel.DEV,
        config.roles.get("owner"): PermLevel.OWNER,
        config.roles.get("co_owner"): PermLevel.CO_OWNER,
    }
    return {role_id: level for role_id, level in mapping.items() if role_id is not None}


def get_user_perm_level(member: discord.Member) -> PermLevel:
    # Safety-Fallback: Discord-Admin = Owner-Level
    security_cfg = config.security 
    if (member.guild_permissions.administrator and
        security_cfg.get("admin_is_owner", False)
        and not security_cfg.get("owner_role_only", False)
        ):    
        return PermLevel.OWNER
    
    highest = PermLevel.MEMBER
    role_to_level = get_role_to_level()
    for role in member.roles:
        level = role_to_level.get(role.id)
        if level and level > highest:
            highest = level

    return highest

def get_required_perm_level(action: str) -> PermLevel:
    perm_cfg = config.permissions.get(action)
    if not perm_cfg:
        return PermLevel.DEV 

    return PermLevel(perm_cfg.get("min_level", PermLevel.DEV))

def has_permission(member: discord.Member, action: str) -> bool:
    return get_user_perm_level(member) >= get_required_perm_level(action)
