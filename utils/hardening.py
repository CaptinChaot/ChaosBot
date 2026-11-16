import discord
from utils.permissions import get_user_perm_level, PermLevel
from utils.logger import logger
from utils.config import config

STAFF_ROLE_IDS: set[int] =set()

def can_moderate(
    *,
    interaction: discord.Interaction,
    target: discord.Member | None,
    action: str
) -> tuple[bool, str | None]:
    """
    Zentrale Hardening-Logik.
    Rückgabe: (allowed, reason)
    """

    # Kein Guild-Kontext
    if not interaction.guild:
        return False, "Kein Server-Kontext."

    actor: discord.Member = interaction.user
    bot: discord.Member | None = interaction.guild.me

    if not bot:
        logger.error("HARDENING | Bot-Mitglied nicht gefunden")
        return False, "Interner Fehler (Bot nicht gefunden)."

    # Aktionen OHNE Target (z.B. reload)
    if target is None:
        return True, None

    # Selbstschutz
    if actor.id == target.id:
        return False, "Du kannst dich nicht selbst moderieren."

    # Bots schützen
    if target.bot:
        return False, "Bots können nicht moderiert werden."

    # Owner / Dev schützen
    if get_user_perm_level(target) >= PermLevel.DEV:
        return False, "Dieser User ist geschützt (Dev / Owner)."

    # Rollen-Hierarchie: Actor
    if target.top_role >= actor.top_role:
        return False, "User hat gleiche oder höhere Rolle als du."

    # Rollen-Hierarchie: Bot
    if target.top_role >= bot.top_role:
        return False, "Meine Rolle ist zu niedrig für diese Aktion."

    return True, None

def is_staff_role(role: discord.Role) -> bool:
    staff_role_keys = config.role_management.get("staff_roles", [])
    staff_role_ids = {
        int(config.roles.get(key))
        for key in staff_role_keys
        if config.roles.get(key)
    }
    return role.id in staff_role_ids
