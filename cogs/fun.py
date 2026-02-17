import discord
from discord import app_commands
from discord.ext import commands

from utils.config import config   # ← NEU: Import für config.features

class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Bot ping test")
    async def ping(self, interaction: discord.Interaction):
        # Optionaler Feature-Check (konsistent mit anderen Cogs)
        if not config.features.get("fun", False):
            await interaction.response.send_message(
                "Fun-Commands sind aktuell deaktiviert.",
                ephemeral=True
            )
            return

        await interaction.response.send_message("Pong ✅", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))