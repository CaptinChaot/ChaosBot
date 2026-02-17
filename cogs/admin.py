import discord
from discord import app_commands
from discord.ext import commands

from utils.decorators import require_perm
from utils.hardening import can_moderate
from utils.logger import logger
from utils.config import config

allowed_cogs = {"admin", "moderation", "fun", "utility", "music"}

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="reload", description="Reload a cog")
    @app_commands.describe(cog="Name des Cogs (z.B. moderation, admin)")
    @require_perm("reload")
    async def reload(self, interaction: discord.Interaction, cog: str):
        if not config.features.get("admin", False):
            await interaction.response.send_message("Admin-Commands sind aktuell deaktiviert.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # Rest deines Codes bleibt 1:1 gleich
        cog = cog.lower().strip()
        if cog.startswith("cogs."):
            cog = cog.removeprefix("cogs.")

        allowed, reason = can_moderate(
            interaction=interaction,
            target=None,
            action="reload"
        )
        if not allowed:
            await interaction.followup.send(f"❌ {reason}", ephemeral=True)
            return

        if cog not in allowed_cogs:
            await interaction.followup.send(
                "❌ Dieses Cog darf nicht manuell geladen werden.",
                ephemeral=True
            )
            return

        ext = f"cogs.{cog}"

        try:
            await self.bot.reload_extension(ext)
            await interaction.followup.send(
                f"✅ Cog `{ext}` wurde neu geladen.",
                ephemeral=True
            )
            logger.info(f"RELOAD | {interaction.user} -> {ext}")

        except commands.ExtensionNotLoaded:
            try:
                await self.bot.load_extension(ext)
                await interaction.followup.send(
                    f"✅ Cog `{ext}` wurde geladen.",
                    ephemeral=True
                )
                logger.info(f"LOAD | {interaction.user} -> {ext}")
            except commands.ExtensionError as e:
                await interaction.followup.send(
                    f"❌ Fehler beim Laden: `{type(e).__name__}: {e}`",
                    ephemeral=True
                )
                logger.exception(f"LOAD FAILED | {ext}")

        except commands.ExtensionError as e:
            await interaction.followup.send(
                f"❌ Fehler beim Reload: `{type(e).__name__}: {e}`",
                ephemeral=True
            )
            logger.exception(f"RELOAD FAILED | {ext}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))   