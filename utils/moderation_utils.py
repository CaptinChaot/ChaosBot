import discord
from datetime import timedelta
from discord.utils import utcnow

from utils.permissions import get_user_perm_level, PermLevel
from utils.logger import logger, log_to_channel
from utils.warnings_db import (
    get_last_auto_action,
    mark_auto_action, auto_action_allowed
)
from utils.config import config

mod_cfg = config.moderation
timeout_warn     = mod_cfg.get("warn_timeout_threshold", 2)
timeout_duration = mod_cfg.get("warn_timeout_duration", 300)
kick_warn        = mod_cfg.get("warn_kick_threshold", 3)
ban_warn         = mod_cfg.get("warn_ban_threshold", 5)


def can_auto_action(guild: discord.Guild, user: discord.Member) -> bool:
    """Prüft ob eine Auto-Aktion auf den User angewendet werden darf."""
    if user.bot:
        return False

    if get_user_perm_level(user) >= PermLevel.DEV:
        logger.info(f"AUTO ACTION SKIPPED | {user} ist Dev/Owner")
        return False

    bot_member = guild.me
    if not bot_member:
        logger.error("AUTO ACTION BLOCKED | Bot-Mitglied nicht gefunden")
        return False

    if user.top_role >= bot_member.top_role:
        logger.warning(
            f"AUTO ACTION BLOCKED | Bot-Rolle zu niedrig "
            f"(user={user.top_role.position}, bot={bot_member.top_role.position})"
        )
        return False

    return True


async def handle_auto_actions(*,
    bot: discord.Client,
    guild: discord.Guild,
    moderator: discord.Member | discord.ClientUser,
    user: discord.Member,
    total_warnings: int,
    warning_id: int,
) -> bool:
    """
    Führt Auto-Aktion aus basierend auf Warn-Anzahl.
    Thresholds kommen aus config.yaml.
    Rückgabe: True → Aktion durchgeführt, False → keine Aktion
    """
    if not can_auto_action(guild, user):
        return False

    last_action = get_last_auto_action(guild_id=guild.id, user_id=user.id)
    cooldown = config.automod.get("action_cooldown", 60)
    if not auto_action_allowed(last_action, cooldown):
        logger.info(f"AUTO ACTION COOLDOWN | {user} | Letzte Aktion: {last_action['type']} vor {int((utcnow() - last_action['timestamp']).total_seconds())}s")
        return False
    
    last_type = last_action["type"] if last_action else None
    channel_id = int(config.log_channels.get("moderation", 0))

    # 🔨 BAN
    if total_warnings >= ban_warn:
        if last_type != "kick":
            return False
        try:
            await guild.ban(user, reason="[Auto] Bann durch Verwarnungen", delete_message_days=0)
            mark_auto_action(warning_id, "ban")
            logger.info(f"AUTO BAN | {user}")
            if channel_id:
                await log_to_channel(bot, channel_id, "🔨 AUTO BAN",
                    f"**User:** {user.mention} ({user.id})\n"
                    f"**Warns:** {total_warnings}\n"
                    f"**Moderator:** {moderator}",
                    discord.Color.dark_red())
            return True
        except discord.Forbidden:
            logger.error(f"AUTO BAN FAILED | Keine Berechtigung | {user}")
            return False

    # 👢 KICK
    if total_warnings >= kick_warn:
        if last_type in ("kick", "ban"):
            return False
        try:
            await user.kick(reason="[Auto] Kick durch Verwarnungen")
            mark_auto_action(warning_id, "kick")
            logger.info(f"AUTO KICK | {user}")
            if channel_id:
                await log_to_channel(bot, channel_id, "👢 AUTO KICK",
                    f"**User:** {user.mention} ({user.id})\n"
                    f"**Warns:** {total_warnings}\n"
                    f"**Moderator:** {moderator}",
                    discord.Color.orange())
            return True
        except discord.Forbidden:
            logger.error(f"AUTO KICK FAILED | Keine Berechtigung | {user}")
            return False

    # ⏱️ TIMEOUT
    if total_warnings >= timeout_warn:
        if last_type in ("timeout", "kick", "ban"):
            return False
        until = utcnow() + timedelta(seconds=timeout_duration)
        try:
            await user.timeout(until, reason="[Auto] Timeout durch Verwarnungen")
            mark_auto_action(warning_id, "timeout")
            logger.info(f"AUTO TIMEOUT | {user}")
            if channel_id:
                await log_to_channel(bot, channel_id, "⏱️ AUTO TIMEOUT",
                    f"**User:** {user.mention} ({user.id})\n"
                    f"**Dauer:** {timeout_duration}s\n"
                    f"**Moderator:** {moderator}",
                    discord.Color.gold())
            return True
        except discord.Forbidden:
            logger.error(f"AUTO TIMEOUT FAILED | Keine Berechtigung | {user}")
            return False

    return False