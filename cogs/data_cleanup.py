from discord.ext import commands, tasks
from utils.config import config
from utils.logger import logger
from utils.member_log_db import cleanup_member_log
from utils.warnings_db import cleanup_old_warnings
from utils.giveaway_db import cleanup_old_giveaways


class DataCleanupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cleanup_task.start()

    def cog_unload(self):
        self.cleanup_task.cancel()    

    @tasks.loop(hours=24)
    async def cleanup_task(self):
        retention = config.data_retention

        try:
            members = cleanup_member_log(retention.get("member_log_months", 12))
            warnings = cleanup_old_warnings(retention.get("warnings_months_since_last", 18))
            giveaways = cleanup_old_giveaways(retention.get("giveaways_days_after_end",30))
            logger.info(
                f"[DataCleanup] Gelöscht {members} Member-Log Einträge, "
                f"{warnings} Warnungen, {giveaways} alte Giveaways."
            )
        except Exception:
            logger.exception("[DataCleanup] Fehler beim Bereinigen der Datenbank.")

    @cleanup_task.before_loop
    async def before_cleanup_task(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(DataCleanupCog(bot))            