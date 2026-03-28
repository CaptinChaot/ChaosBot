import discord
from discord.ext import tasks, commands
from utils.config import config
from utils.logger import logger
import aiohttp


class StatusChannels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Channel IDs aus config.yaml
        self.bot_status_channel_id = config.bot_status_vc
        self.dashboard_status_channel_id = config.dashboard_status_vc

        if not self.bot_status_channel_id or not self.dashboard_status_channel_id:
            logger.warning("[StatusChannels] Keine Channel-IDs in config.yaml – Cog inaktiv.")
            return

        self.update_status_channels.start()

    def cog_unload(self):
        if self.update_status_channels.is_running():
            self.update_status_channels.cancel()

    async def check_dashboard(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://chaosbot.de/login",
                    timeout=aiohttp.ClientTimeout(total=5),
                    allow_redirects=True
                ) as res:
                    return res.status in [200, 307, 302]
        except Exception:
            return False

    @tasks.loop(minutes=5)
    async def update_status_channels(self):
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return

        # Bot Status Channel
        bot_channel = self.bot.get_channel(self.bot_status_channel_id)
        if bot_channel:
            bot_online = self.bot.is_ready()
            new_name = f"🟢 Bot: Aktiv" if bot_online else f"🔴 Bot: Inaktiv"
            if bot_channel.name != new_name:
                try:
                    await bot_channel.edit(name=new_name)
                    logger.info(f"[StatusChannels] Bot Status → {new_name}")
                except discord.Forbidden:
                    logger.error("[StatusChannels] Keine Berechtigung für Bot-Status Channel.")
                except discord.HTTPException as e:
                    logger.error(f"[StatusChannels] HTTP Fehler Bot: {e}")

        # Dashboard Status Channel
        dash_channel = self.bot.get_channel(self.dashboard_status_channel_id)
        if dash_channel:
            dash_online = await self.check_dashboard()
            new_name = f"🟢 Dashboard: Aktiv" if dash_online else f"🔴 Dashboard: Inaktiv"
            if dash_channel.name != new_name:
                try:
                    await dash_channel.edit(name=new_name)
                    logger.info(f"[StatusChannels] Dashboard Status → {new_name}")
                except discord.Forbidden:
                    logger.error("[StatusChannels] Keine Berechtigung für Dashboard Channel.")
                except discord.HTTPException as e:
                    logger.error(f"[StatusChannels] HTTP Fehler Dashboard: {e}")

    @update_status_channels.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(StatusChannels(bot))