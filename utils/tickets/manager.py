# utils/tickets/manager.py

import discord
from utils.config import config
from utils.permissions import get_user_perm_level, PermLevel
from utils.logger import log_to_channel, logger
from utils.tickets.constants import TICKET_TYPES


# ==================================================
# Helpers
# ==================================================

def _ticket_cfg() -> dict:
    # Fix: config.tickets statt config.get("tickets")
    tickets_cfg = config.tickets
    if not tickets_cfg or not isinstance(tickets_cfg, dict):
        raise RuntimeError("tickets-Block fehlt oder ist ungültig in config.yaml")
    return tickets_cfg


def _is_support_plus(member: discord.Member) -> bool:
    level = get_user_perm_level(member)
    logger.debug(f"PermLevel von {member} ({member.id}): {level}")
    return level >= PermLevel.SUPPORT


def _get_ticket_owner(channel: discord.TextChannel) -> discord.Member | None:
    """
    Erwartetes Topic-Format:
    OPEN | User:123456789 | Type:support
    """
    if not channel.topic:
        logger.warning(f"Channel {channel.id} ({channel.name}) hat kein Topic!")
        return None

    topic = channel.topic.strip()
    logger.debug(f"Ticket-Topic: '{topic}'")

    for part in topic.split("|"):
        part = part.strip()
        if part.lower().startswith("user:"):
            try:
                user_id_str = part[5:].strip()  # nach "User:" alles danach
                user_id = int(user_id_str.split()[0])  # erste Zahl nehmen
                member = channel.guild.get_member(user_id)
                if member:
                    logger.debug(f"Ticket-Owner gefunden: {member} ({user_id})")
                    return member
                else:
                    logger.warning(f"User-ID {user_id} nicht auf Server gefunden")
            except (ValueError, IndexError) as e:
                logger.error(f"Fehler beim Parsen von User-ID in Topic '{topic}': {e}")
    logger.warning(f"Kein gültiger User in Topic gefunden: '{topic}'")
    return None


# ==================================================
# Ticket erstellen
# ==================================================

async def create_ticket_channel(
    *,
    bot: discord.Client,
    guild: discord.Guild,
    user: discord.Member,
    ticket_type: str,
    description: str,
):
    cfg = _ticket_cfg()

    category_id = cfg.get("category_open")
    if not category_id:
        raise RuntimeError("category_open fehlt in config.yaml → tickets")

    category = guild.get_channel(int(category_id))
    if not category or not isinstance(category, discord.CategoryChannel):
        raise RuntimeError(f"Ticket-OPEN-Kategorie nicht gefunden oder ungültig: ID {category_id}")

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
        ),
    }

    # Support-Rollen hinzufügen
    for role_name in ["supporter", "moderator", "admin", "dev", "co_owner", "owner"]:
        role_id = config.roles.get(role_name)
        if role_id:
            role = guild.get_role(int(role_id))
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                )

    # Bot selbst braucht volle Rechte
    bot_member = guild.me or guild.get_member(bot.user.id)
    if bot_member:
        overwrites[bot_member] = discord.PermissionOverwrite(
            view_channel=True,
            manage_channels=True,
            manage_messages=True,
            manage_permissions=True,
        )
    else:
        logger.warning("Bot-Member nicht gefunden – Manage-Rechte könnten fehlen")

    prefix = (
        cfg.get("channel_prefix")
        or cfg.get("channel_preffix")
        or "ticket"
    ).lower()

    channel_name = f"{prefix}-{ticket_type}-{user.name}".lower()[:90]
    topic = f"OPEN | User:{user.id} | Type:{ticket_type}"

    try:
        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=topic,
            reason=f"Ticket erstellt von {user}",
        )

        # Sicherstellen, dass Topic wirklich gesetzt ist
        if channel.topic != topic:
            logger.warning(f"Topic nicht korrekt gesetzt! Setze erneut: {topic}")
            await channel.edit(topic=topic)

    except discord.Forbidden as e:
        logger.error(f"Bot fehlen Rechte zum Erstellen des Channels: {e}")
        raise

    except discord.HTTPException as e:
        logger.error(f"HTTP-Fehler beim Channel-Erstellen: {e}")
        raise

    label = TICKET_TYPES.get(ticket_type, {}).get("label", ticket_type)

    embed = discord.Embed(
        title="🎫 Neues Ticket",
        description=(
            f"**Typ:** {label}\n"
            f"**User:** {user.mention}\n\n"
            f"**Beschreibung:**\n{description}"
        ),
        color=discord.Color.blurple(),
        timestamp=discord.utils.utcnow()
    )

    await channel.send(content=user.mention, embed=embed)

    await log_to_channel(
        bot,
        config.log_channels.get("moderation", 0),
        "🎫 Ticket erstellt",
        f"**User:** {user} ({user.id})\n**Channel:** {channel.mention} ({channel.id})\n**Typ:** {ticket_type}",
    )

    return channel


# ==================================================
# Ticket claimen
# ==================================================

async def claim_ticket(
    *,
    bot: discord.Client,
    channel: discord.TextChannel,
    claimer: discord.Member,
):
    if not _is_support_plus(claimer):
        raise PermissionError("SUPPORT+ erforderlich")

    owner = _get_ticket_owner(channel)
    if not owner:
        logger.error(f"Ticket-User nicht ermittelbar – Topic: '{channel.topic}'")
        raise RuntimeError("Ticket-User nicht ermittelbar")

    try:
        await channel.edit(
            topic=f"CLAIMED | User:{owner.id} | ClaimedBy:{claimer.id}",
            reason=f"Ticket geclaimed von {claimer}",
        )

        await channel.send(f"🖐 **Ticket geclaimed von {claimer.mention}**")

        await log_to_channel(
            bot,
            config.log_channels.get("moderation", 0),
            "🖐 Ticket geclaimed",
            f"**Channel:** {channel.mention} ({channel.id})\n**Claimer:** {claimer} ({claimer.id})\n**Owner:** {owner}",
        )

    except discord.Forbidden as e:
        logger.error(f"Fehlen Rechte zum Editieren des Channels: {e}")
        raise

    except discord.HTTPException as e:
        logger.error(f"HTTP-Fehler beim Claim: {e}")
        raise


# ==================================================
# Ticket archivieren
# ==================================================

async def archive_ticket(
    *,
    bot: discord.Client,
    channel: discord.TextChannel,
    closed_by: discord.Member,
):
    if not _is_support_plus(closed_by):
        raise PermissionError("SUPPORT+ erforderlich")

    cfg = _ticket_cfg()
    archive_id = cfg.get("category_closed")
    if not archive_id:
        raise RuntimeError("category_closed fehlt in config.yaml → tickets")

    archive_category = channel.guild.get_channel(int(archive_id))
    if not archive_category or not isinstance(archive_category, discord.CategoryChannel):
        raise RuntimeError(f"Ticket-ARCHIV-Kategorie nicht gefunden oder ungültig: ID {archive_id}")

    overwrites = channel.overwrites.copy()  # Kopie, damit wir nicht Original ändern

    if cfg.get("archive", {}).get("hide_from_user", True):
        owner = _get_ticket_owner(channel)
        if owner:
            overwrites[owner] = discord.PermissionOverwrite(view_channel=False)

    try:
        await channel.edit(
            category=archive_category,
            overwrites=overwrites,
            topic=f"ARCHIVED | ClosedBy:{closed_by.id}",
            reason=f"Ticket archiviert von {closed_by}",
        )

        await channel.send("🗂 **Ticket wurde archiviert.**")

        await log_to_channel(
            bot,
            config.log_channels.get("moderation", 0),
            "🗂 Ticket archiviert",
            f"**Channel:** {channel.mention} ({channel.id})\n**Closed by:** {closed_by} ({closed_by.id})",
        )

    except discord.Forbidden as e:
        logger.error(f"Fehlen Rechte zum Archivieren: {e}")
        raise

    except discord.HTTPException as e:
        logger.error(f"HTTP-Fehler beim Archivieren: {e}")
        raise