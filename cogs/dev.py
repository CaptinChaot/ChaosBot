# cogs/dev.py

from discord.ext import commands
from utils.config import config   # ← NEU: Import für config.features

class Dev(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="tickets_reload")
    @commands.is_owner()
    async def tickets_reload(self, ctx):
        # Feature-Check (optional, aber konsistent mit den anderen Cogs)
        if not config.features.get("dev", False):
            await ctx.send("Dev-Commands sind aktuell deaktiviert.")
            return

        await self.bot.reload_extension("cogs.tickets")
        await ctx.send("♻️ Ticketsystem neu geladen")

async def setup(bot):
    await bot.add_cog(Dev(bot))