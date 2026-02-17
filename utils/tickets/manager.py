# utils/tickets/manager.py

import discord
from utils.config import config
from utils.permissions import get_user_perm_level, PermLevel
from utils.logger import log_to_channel
from utils.tickets.constants import TICKET_TYPES


# ==================================================
# Helpers
# ==================================================

def _ticket_cfg() -> dict:
    tickets_cfg = config.get("tickets")
    if not tickets_cfg:
        raise RuntimeError("tickets-Block fehlt in config.yaml")
    return tickets_cfg


def _is_support_plus(member: discord.Member) -> bool:
    return get_user_perm_level(member) >= PermLevel.SUPPORT


def _get_ticket_owner(channel: discord.TextChannel) -> discord.Member | None:
    """
    Erwartetes Topic-Format:
    OPEN | User:123456789 | Type:support
    """
    if not channel.topic:
        return None

    for part in channel.topic.split("|"):
        part = part.strip()
        if part.startswith("User:"):
            try:
                user_id = int(part.split(":")[1])
                return channel.guild.get_member(user_id)
            except Exception:
                return None
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
    if not category:
        raise RuntimeError("Ticket-OPEN-Kategorie nicht gefunden")

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
        ),
    }

    # Support-Rollen
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

    # Bot selbst
    bot_member = guild.me or guild.get_member(bot.user.id)
    overwrites[bot_member] = discord.PermissionOverwrite(
        view_channel=True,
        manage_channels=True,
        manage_messages=True,
    )

    prefix = (
        cfg.get("channel_prefix")
        or cfg.get("channel_preffix")
        or "ticket"
    ).lower()

    channel_name = f"{prefix}-{ticket_type}-{user.name}".lower()[:90]
    topic = f"OPEN | User:{user.id} | Type:{ticket_type}"

    channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites,
        topic=topic,
        reason="Ticket erstellt",
    )

    label = TICKET_TYPES.get(ticket_type, {}).get("label", ticket_type)

    embed = discord.Embed(
        title="🎫 Neues Ticket",
        description=(
            f"**Typ:** {label}\n"
            f"**User:** {user.mention}\n\n"
            f"**Beschreibung:**\n{description}"
        ),
        color=discord.Color.blurple(),
    )

    await channel.send(content=user.mention, embed=embed)

    await log_to_channel(
        bot,
        config.log_channels["moderation"],
        "🎫 Ticket erstellt",
        f"**User:** {user}\n**Channel:** {channel.mention}\n**Typ:** {ticket_type}",
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
        raise RuntimeError("Ticket-User nicht ermittelbar")

    await channel.edit(
        topic=f"CLAIMED | User:{owner.id} | ClaimedBy:{claimer.id}",
        reason="Ticket geclaimed",
    )

    await channel.send(
        f"🖐 **Ticket geclaimed von {claimer.mention}**"
    )

    await log_to_channel(
        bot,
        config.log_channels["moderation"],
        "🖐 Ticket geclaimed",
        f"**Channel:** {channel.mention}\n**Claimer:** {claimer}",
    )


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
    archive_category = channel.guild.get_channel(int(cfg["category_closed"]))
    if not archive_category:
        raise RuntimeError("Ticket-ARCHIV-Kategorie nicht gefunden")

    overwrites = channel.overwrites

    if cfg.get("archive", {}).get("hide_from_user", True):
        owner = _get_ticket_owner(channel)
        if owner:
            overwrites[owner] = discord.PermissionOverwrite(view_channel=False)

    await channel.edit(
        category=archive_category,
        overwrites=overwrites,
        topic=f"ARCHIVED | ClosedBy:{closed_by.id}",
        reason="Ticket archiviert",
    )

    await channel.send("🗂 **Ticket wurde archiviert.**")

    await log_to_channel(
        bot,
        config.log_channels["moderation"],
        "🗂 Ticket archiviert",
        f"**Channel:** {channel.mention}\n**Closed by:** {closed_by}",
    )
