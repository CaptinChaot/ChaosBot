import discord
from datetime import datetime
from discord.utils import utcnow
from utils.warnings_db import (
    get_user_status,
    save_timeout,
    clear_timeout,
    save_ban,
)

async def sync_user_state(
    guild: discord.Guild,
    member: discord.Member
) -> list[str]:
    """
    Synchronisiert DB <-> Discord.
    Returns: Liste der durchgeführten Aktionen (Strings)
    """
    actions = []
    status = get_user_status(guild.id, member.id)

    # ---- TIMEOUT ----
    db_timeout = status["timeout_until"]
    discord_timeout = member.is_timed_out()

    # DB -> Discord
    if db_timeout and not discord_timeout:
        if db_timeout > utcnow():
            await member.timeout(db_timeout, reason="Sync: DB → Discord")
            actions.append("Timeout aus DB erneut gesetzt")
        else:
            await clear_timeout(guild.id, member.id)
            actions.append("Abgelaufenen Timeout aus DB gelöscht")
    # Discord -> DB
    if discord_timeout and not db_timeout:
        save_timeout(guild.id, member.id, member.timed_out_until)
        actions.append("Timeout aus Discord in DB gespeichert")

    # ---- BAN ----
    if status["active_ban"]:
        try:
            await guild.fetch_ban(member)
        except discord.NotFound:
            await guild.ban(
                member,
                reason="Sync: DB → Discord (Bann aktiv)"
            )
            actions.append("Bann aus DB erneut gesetzt")

    return actions
