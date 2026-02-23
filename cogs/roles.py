import discord
from discord import app_commands
from discord.ext import commands

from utils.decorators import require_perm
from utils.hardening import can_moderate
from utils.logger import logger, log_to_channel
from utils.config import config


class Roles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Hilfsfunktion für Feature-Check
    async def _check_roles_feature(self, interaction: discord.Interaction):
        if not config.features.get("roles", False):
            await interaction.response.send_message(
                "Rollen-Management ist aktuell deaktiviert.",
                ephemeral=True
            )
            return False
        return True

    # -----------------------------
    # ROLE ADD
    # -----------------------------
    @app_commands.command(name="role_add", description="Rolle zuweisen")
    @require_perm("role_add")
    async def role_add(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        role: discord.Role,
    ):
        # Sofort defer – das verhindert den 3-Sekunden-Timeout
        await interaction.response.defer(ephemeral=True)

        try:
            if not await self._check_roles_feature(interaction):
                return

            allowed, reason = can_moderate(
                interaction=interaction,
                target=user,
                action="role_add"
            )
            if not allowed:
                await interaction.followup.send(f"❌ {reason}", ephemeral=True)
                return

            # Selbstschutz
            if user == interaction.user:
                await interaction.followup.send(
                    "❌ Du kannst dir selbst keine Rollen geben.",
                    ephemeral=True
                )
                return

            # Rollen-Hierarchie (Bot)
            bot_member = interaction.guild.me
            if role >= bot_member.top_role:
                await interaction.followup.send(
                    "❌ Ich kann diese Rolle nicht verwalten (Bot-Rolle zu niedrig).",
                    ephemeral=True
                )
                return

            # Rollen-Whitelist (optional)
            allowed_roles = getattr(config, "role_management", {}).get("allowed_roles", [])
            if allowed_roles:
                if role.name not in allowed_roles:
                    await interaction.followup.send(
                        "❌ Diese Rolle darf nicht manuell vergeben werden.",
                        ephemeral=True
                    )
                    return

            if role in user.roles:
                await interaction.followup.send(
                    "⚠️ User hat diese Rolle bereits.",
                    ephemeral=True
                )
                return

            # Aktion
            await user.add_roles(
                role,
                reason=f"Role add by {interaction.user}"
            )

            # Logging
            logger.info(
                f"ROLE ADD | {interaction.user} -> {user} | {role.id}:{role.name}"
            )

            channel_id = int(config.log_channels.get("bot", 0))
            if channel_id:
                await log_to_channel(
                    self.bot,
                    channel_id,
                    "🟢 Rolle hinzugefügt",
                    f"**Moderator:** {interaction.user.mention}\n"
                    f"**User:** {user.mention}\n"
                    f"**Rolle:** {role.mention}",
                    discord.Color.green(),
                )

            await interaction.followup.send(
                f"✅ {role.mention} wurde {user.mention} hinzugefügt.",
                ephemeral=True
            )

        except Exception as e:
            logger.exception(f"Fehler bei /role_add: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Interner Fehler: {str(e)[:100]}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Interner Fehler: {str(e)[:100]}", ephemeral=True)

    # -----------------------------
    # ROLE REMOVE
    # -----------------------------
    @app_commands.command(name="role_remove", description="Rolle entfernen")
    @require_perm("role_remove")
    async def role_remove(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        role: discord.Role,
    ):
        # Sofort defer – das verhindert den Timeout
        await interaction.response.defer(ephemeral=True)

        try:
            if not await self._check_roles_feature(interaction):
                return

            allowed, reason = can_moderate(
                interaction=interaction,
                target=user,
                action="role_remove"
            )
            if not allowed:
                await interaction.followup.send(f"❌ {reason}", ephemeral=True)
                return

            if role not in user.roles:
                await interaction.followup.send(
                    "⚠️ User hat diese Rolle nicht.",
                    ephemeral=True
                )
                return

            bot_member = interaction.guild.me
            if role >= bot_member.top_role:
                await interaction.followup.send(
                    "❌ Ich kann diese Rolle nicht verwalten (Bot-Rolle zu niedrig).",
                    ephemeral=True
                )
                return

            # Aktion
            await user.remove_roles(
                role,
                reason=f"Role remove by {interaction.user}"
            )

            # Logging
            logger.info(
                f"ROLE REMOVE | {interaction.user} -> {user} | {role.id}:{role.name}"
            )

            channel_id = int(config.log_channels.get("bot", 0))
            if channel_id:
                await log_to_channel(
                    self.bot,
                    channel_id,
                    "🔴 Rolle entfernt",
                    f"**Moderator:** {interaction.user.mention}\n"
                    f"**User:** {user.mention}\n"
                    f"**Rolle:** {role.mention}",
                    discord.Color.red(),
                )

            await interaction.followup.send(
                f"✅ {role.mention} wurde von {user.mention} entfernt.",
                ephemeral=True
            )

        except Exception as e:
            logger.exception(f"Fehler bei /role_remove: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Interner Fehler: {str(e)[:100]}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Interner Fehler: {str(e)[:100]}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Roles(bot))