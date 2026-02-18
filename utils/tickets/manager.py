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
    tickets_cfg = config.tickets
    if not tickets_cfg or not isinstance(tickets_cfg, dict):
        raise RuntimeError("tickets-Block fehlt oder ist ungültig in config.yaml")
    return tickets_cfg


def _is_support_plus(member: discord.Member) -> bool:
    level = get_user_perm_level(member)
    logger.debug(f"PermLevel von {member} ({member.id}): {level}")
    return level >= PermLevel.SUPPORT


async def _get_ticket_owner(channel: discord.TextChannel) -> discord.Member | None:
    """
    Holt den Ticket-Ersteller aus dem Topic.
    Verwendet fetch_member (API-Call), damit auch nicht-gecachte User gefunden werden.
    """
    if not channel.topic:
        logger.warning(f"Channel {channel.id} hat kein Topic!")
        return None

    topic = channel.topic.strip()
    logger.debug(f"Ticket-Topic: '{topic}'")

    for part in topic.split("|"):
        part = part.strip()
        if part.lower().startswith("user:"):
            try:
                user_id_str = part[5:].strip()
                user_id = int(''.join(filter(str.isdigit, user_id_str)))  # nur Zahlen nehmen
                logger.debug(f"Versuche Member zu finden: {user_id}")

                member = await channel.guild.fetch_member(user_id)  # API-Call statt Cache
                logger.debug(f"Member gefunden: {member.name} ({member.id})")
                return member

            except discord.NotFound:
                logger.warning(f"User-ID {user_id} existiert nicht mehr auf dem Server")
            except (ValueError, IndexError, discord.HTTPException) as e:
                logger.error(f"Fehler beim Parsen/Fetchen von User-ID in Topic '{topic}': {e}")

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

    category = guild.get_channel(int(cfg["category_open"]))
    if not category or not isinstance(category, discord.CategoryChannel):
        raise RuntimeError(f"Ticket-OPEN-Kategorie nicht gefunden: ID {cfg.get('category_open')}")

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
    }

    # Support-Rollen
    for role_name in ["supporter", "moderator", "admin", "dev", "co_owner", "owner"]:
        role_id = config.roles.get(role_name)
        if role_id:
            role = guild.get_role(int(role_id))
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True
                )

    # Bot selbst
    bot_member = guild.me or guild.get_member(bot.user.id)
    if bot_member:
        overwrites[bot_member] = discord.PermissionOverwrite(
            view_channel=True, manage_channels=True, manage_messages=True, manage_permissions=True
        )

    prefix = (cfg.get("channel_prefix") or cfg.get("channel_preffix") or "ticket").lower()
    channel_name = f"{prefix}-{ticket_type}-{user.name}".lower()[:90]
    topic = f"OPEN | User:{user.id} | Type:{ticket_type}"

    channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites,
        topic=topic,
        reason=f"Ticket erstellt von {user}",
    )

    # Topic nochmal sicher setzen
    if channel.topic != topic:
        await channel.edit(topic=topic)

    label = TICKET_TYPES.get(ticket_type, {}).get("label", ticket_type)

    embed = discord.Embed(
        title="🎫 Neues Ticket",
        description=f"**Typ:** {label}\n**User:** {user.mention}\n\n**Beschreibung:**\n{description}",
        color=discord.Color.blurple(),
        timestamp=discord.utils.utcnow()
    )

    await channel.send(content=user.mention, embed=embed)

    await log_to_channel(
        bot,
        config.log_channels.get("moderation", 0),
        "🎫 Ticket erstellt",
        f"**User:** {user} ({user.id})\n**Channel:** {channel.mention}\n**Typ:** {ticket_type}",
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
    
    level = get_user_perm_level(claimer)
    logger.debug(f"Claim-Versuch von {claimer} in ({claimer.id}) – Level: {level}")
    if level < PermLevel.SUPPORT:
        logger.info(f"Claim abgelehnt – unzureichende Berechtigung (Level {level})")
        await channel.send("❌ Du hast keine Berechtigung zum Claimen.", delete_after=15)
        return False
    
    owner = await _get_ticket_owner(channel)   # ← jetzt async!
    owner_id = owner.id if owner else "unbekannt"

    if not owner:
        logger.warning(f"Ticket-Owner nicht gefunden – Claim trotzdem durchgeführt")
        await channel.send("⚠️ Ticket-Owner nicht gefunden – Claim trotzdem durchgeführt.")

    try:
        await channel.edit(
            topic=f"CLAIMED | User:{owner_id} | ClaimedBy:{claimer.id}",
            reason=f"Ticket geclaimed von {claimer}",
        )

        await channel.send(f"🖐 **Ticket geclaimed von {claimer.mention}**")

        await log_to_channel(
            bot,
            config.log_channels.get("moderation", 0),
            "🖐 Ticket geclaimed",
            f"**Channel:** {channel.mention}\n**Claimer:** {claimer}\n**Owner:** {owner or 'unbekannt'}",
        )
        return True
    except Exception as e:
        logger.exception(f"Fehler beim Claimen: {e}")
        await channel.send(f"❌ Fehler beim Claimen: {str(e)[:100]}", delete_after=30)
        return False
        


# ==================================================
# Ticket archivieren
# ==================================================

async def archive_ticket(
    *,
    bot: discord.Client,
    channel: discord.TextChannel,
    closed_by: discord.Member,
):
    level = get_user_perm_level(closed_by)
    logger.debug(f"Archive-Versuch von {closed_by} in ({closed_by.id}) – Level: {level}")
    if level < PermLevel.SUPPORT:
        logger.info(f"Archivieren abgelehnt – unzureichende Berechtigung (Level {level})")
        await channel.send("❌ Du hast keine Berechtigung zum Archivieren.", delete_after=15)
        return False
    
    cfg = _ticket_cfg()
    archive_category = channel.guild.get_channel(int(cfg["category_closed"]))
    if not archive_category:
        raise RuntimeError("Ticket-ARCHIV-Kategorie nicht gefunden")

    overwrites = channel.overwrites.copy()

    if cfg.get("archive", {}).get("hide_from_user", True):
        owner = await _get_ticket_owner(channel)
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
            f"**Channel:** {channel.mention}\n**Closed by:** {closed_by}",
        )
        return True
    except Exception as e:
        logger.exception(f"Fehler beim Archivieren: {e}")
        await channel.send(f"❌ Fehler beim Archivieren: {str(e)[:100]}", delete_after=30)
        return False