import discord
from datetime import timedelta
from discord import app_commands, Interaction
from discord.ext import commands
from discord.utils import utcnow
from utils.hardening import can_moderate
from utils.config import config
from utils.hardlock import hardlock_check, hardlock_log_line
from utils.logger import logger, log_to_channel
from utils.sync import sync_user_state
from utils.moderation_utils import can_auto_action, handle_auto_actions
from utils.decorators import require_perm
from utils.warnings_db import (
    add_warning, count_warnings, delete_warnings as db_delete_warnings, get_warning_by_id,
    delete_warning_by_id, get_last_auto_action, get_last_warning_id, save_ban, save_timeout, clear_ban, clear_timeout, get_user_status)
from utils.moderation_actions import (safe_timeout, safe_untimeout, safe_kick, safe_ban, safe_unban, get_auto_action_preview)

mod_cfg = config.moderation

timeout_warn = mod_cfg.get("warn_timeout_threshold", 2)
timeout_duration = mod_cfg.get("warn_timeout_duration", 300)
kick_warn = mod_cfg.get("warn_kick_threshold", 3)
ban_warn = mod_cfg.get("warn_ban_threshold", 5)

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Hilfsfunktion für Feature-Check (wird in jedem Command aufgerufen)
    async def _check_moderation_feature(self, interaction: Interaction):
        if not config.features.get("moderation", False):
            await interaction.followup.send(
                "Moderations-Features sind aktuell deaktiviert.",
                ephemeral=True
            )
            return False
        return True

    @app_commands.command(name="timeout", description="Setze einen User in Timeout")
    @require_perm("timeout")
    async def timeout(self, interaction: Interaction, user: discord.Member, duration: int, reason: str = "Kein Grund angegeben"):
        await interaction.response.defer(ephemeral=True)

        if not await self._check_moderation_feature(interaction):
            return

        # Hardlock Check
        allowed, block_reason = hardlock_check(interaction, user)
        if not allowed:
            logger.warning(hardlock_log_line(interaction, user, block_reason))
            await interaction.followup.send(f"❌ {block_reason}", ephemeral=True)
            return

        ok, error = await safe_timeout(user, duration, reason=reason)
        if not ok:
            await interaction.followup.send(f"❌ {error}", ephemeral=True)
            return

        until = utcnow() + timedelta(seconds=duration)
        save_timeout(interaction.guild_id, user.id, until, reason)

        channel_id = int(config.log_channels.get("moderation", 0))
        if channel_id:
            await log_to_channel(
                self.bot,
                channel_id,
                f"⏱️ Timeout gesetzt",
                f"**Moderator:** {interaction.user} (ID: {interaction.user.id})\n"
                f"**User:** {user.mention} (ID: {user.id})\n"
                f"**Dauer:** {duration} Sekunden\n"
                f"**Grund:** {reason}\n",
                discord.Color.gold(),
            )
        logger.info(f"TIMEOUT | {interaction.user} -> {user} | {duration}s | {reason}")

        await interaction.followup.send(
            f"✅ {user.mention} wurde für {duration} Sekunden in Timeout gesetzt. Grund: {reason}",
            ephemeral=True
        )

    @app_commands.command(name="untimeout", description="Entferne den Timeout von einem User")
    @app_commands.describe(user="User, dessen Timeout entfernt werden soll", reason="Grund für das Entfernen des Timeouts")
    @require_perm("untimeout")
    async def untimeout(self, interaction: Interaction, user: discord.Member, reason: str = "Timeout entfernt durch Moderator"):
        await interaction.response.defer(ephemeral=True)

        if not await self._check_moderation_feature(interaction):
            return

        allowed, block_reason = hardlock_check(interaction, user)
        if not allowed:
            logger.warning(hardlock_log_line(interaction, user, block_reason))
            await interaction.followup.send(f"❌ {block_reason}", ephemeral=True)
            return

        ok, error = await safe_untimeout(user, reason=reason)
        if not ok:
            await interaction.followup.send(f"❌ {error}", ephemeral=True)
            return

        clear_timeout(interaction.guild.id, user.id)

        channel_id = int(config.log_channels.get("moderation", 0))
        if channel_id:
            await log_to_channel(
                self.bot,
                channel_id,
                f"⏱️ Timeout entfernt",
                f"**Moderator:** {interaction.user} (ID: {interaction.user.id})\n"
                f"**User:** {user.mention} (ID: {user.id})\n",
                discord.Color.green(),
            )
        logger.info(f"UNTIMEOUT | {interaction.user} -> {user}")

        await interaction.followup.send(
            f"✅ Timeout von {user.mention} wurde entfernt.\n**Grund:** {reason}",
            ephemeral=True
        )

    @app_commands.command(name="warn", description="Verwarnt einen User und loggt es im Modlog")
    @app_commands.describe(user="User, der verwarnt werden soll", reason="Grund für die Verwarnung")
    @require_perm("warn")
    async def warn(self, interaction: Interaction, user: discord.Member, reason: str):
        await interaction.response.defer(ephemeral=True)

        if not await self._check_moderation_feature(interaction):
            return

        allowed, deny_reason = can_moderate(interaction=interaction, target=user, action="warn")
        if not allowed:
            await interaction.followup.send(f"❌ {deny_reason}", ephemeral=True)
            return

        try:
            await user.send(f"⚠️ **Verwarnung auf {interaction.guild.name}**\n**Grund:** {reason}\n**Moderator:** {interaction.user}")
        except discord.Forbidden:
            pass

        warning_id = add_warning(
            guild_id=interaction.guild.id,
            user_id=user.id,
            moderator_id=interaction.user.id,
            reason=reason,
        )
        total_warnings = count_warnings(guild_id=interaction.guild.id, user_id=user.id)

        # Auto-Aktionen nur, wenn Feature an ist
        if config.features.get("moderation", False) and can_auto_action(interaction, user):
            action_taken = await handle_auto_actions(
                bot=self.bot,
                interaction=interaction,
                user=user,
                total_warnings=total_warnings,
                warning_id=warning_id,
                timeout_warn=timeout_warn,
                kick_warn=kick_warn,
                ban_warn=ban_warn,
                timeout_duration=timeout_duration
            )
            if action_taken:
                return

        embed = discord.Embed(title="⚠️ Verwarnung", color=discord.Color.orange(), timestamp=utcnow())
        embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
        embed.add_field(name="Anzahl der Verwarnungen", value=str(total_warnings), inline=False)
        embed.add_field(name="Moderator", value=f"{interaction.user}", inline=False)
        embed.add_field(name="Grund", value=reason, inline=False)

        channel_id = int(config.log_channels.get("moderation", 0))
        if channel_id:
            await log_to_channel(self.bot, channel_id, "⚠️ User verwarnt", embed=embed)

        await interaction.followup.send(f"✅ {user.mention} wurde verwarnt.", ephemeral=True)

    # Die anderen Commands bekommen nur den Feature-Check am Anfang
    # Beispiel für warnings (restliche ähnlich)
    @app_commands.command(name="warnings", description="Zeigt die Anzahl der Verwarnungen eines Users an")
    @app_commands.describe(user="User, dessen Verwarnungen angezeigt werden sollen")
    @require_perm("warnings")
    async def warnings(self, interaction: Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True)

        if not await self._check_moderation_feature(interaction):
            return

        if user.bot:
            await interaction.followup.send("❌ Bots können keine Verwarnungen haben.", ephemeral=True)
            return

        total_warnings = count_warnings(guild_id=interaction.guild.id, user_id=user.id)
        await interaction.followup.send(f"ℹ️ {user.mention} hat {total_warnings} Verwarnung(en).", ephemeral=True)

    # ... die restlichen Commands (delete_warnings, unwarn, kick, ban, unban, userinfo, clear, sync_user)
    # bekommen genau den gleichen Check am Anfang:
    # if not await self._check_moderation_feature(interaction): return

    # Beispiel für delete_warnings (kopiere das Muster für alle anderen)
    @app_commands.command(name="delete_warnings", description="Löscht alle Verwarnungen eines Users")
    @app_commands.describe(user="User, dessen Verwarnungen gelöscht werden sollen")
    @require_perm("del_warnings")
    async def delete_warnings(self, interaction: Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True)

        if not await self._check_moderation_feature(interaction):
            return

        # Rest deines Codes bleibt 1:1
        allowed, reason = can_moderate(interaction=interaction, target=user, action="del_warnings")
        if not allowed:
            await interaction.followup.send(f"❌ {reason}", ephemeral=True)
            return

        if user.bot:
            await interaction.followup.send("❌ Bots können keine Verwarnungen haben.", ephemeral=True)
            return

        total_warnings = count_warnings(guild_id=interaction.guild.id, user_id=user.id)
        if total_warnings == 0:
            await interaction.followup.send(f"ℹ️ {user.mention} hat keine Verwarnungen.", ephemeral=True)
            return

        db_delete_warnings(guild_id=interaction.guild.id, user_id=user.id)

        embed = discord.Embed(title="🧹 Verwarnungen gelöscht", color=discord.Color.orange(), timestamp=utcnow())
        embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
        embed.add_field(name="Anzahl gelöscht", value=str(total_warnings), inline=False)
        embed.add_field(name="Moderator", value=f"{interaction.user}", inline=False)

        channel_id = int(config.log_channels.get("moderation", 0))
        if channel_id:
            modlog_channel = self.bot.get_channel(channel_id)
            if modlog_channel:
                await modlog_channel.send(embed=embed)

        await interaction.followup.send(f"✅ Alle Verwarnungen von {user.mention} wurden gelöscht.", ephemeral=True)

    # ... füge den Check bei allen anderen Commands ein (kick, ban, unban, userinfo, clear, sync_user)

async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))