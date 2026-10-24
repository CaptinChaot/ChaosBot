import discord
from datetime import timedelta
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

    async def cleanup_archived_tickets(self, days: int) -> int:
        category_id = config.tickets.get("category_closed")
        category = self.bot.get_channel(int(category_id)) if category_id else None
        if not isinstance(category, discord.CategoryChannel):
            logger.warning(f"[DataCleanup] Ticket-Archiv-Kategorie {category_id} nicht gefunden. Keine Tickets bereinigt.")
            return 0

        cutoff = discord.utils.utcnow() - timedelta(days=days)
        deleted = 0

        for channel in category.text_channels:
            if not (channel.topic or "").startswith("ARCHIVED"):
                continue  # Skip non-archived tickets

            if channel.last_message_id:
                last_activity = discord.utils.snowflake_time(channel.last_message_id)

            else:
                last_activity = channel.created_at

            if last_activity < cutoff:
                await channel.delete(reason=f"Ticket-Archiv älter als {days} Tage (Datenschutz)")        
                deleted += 1
                logger.info(f"[DataCleanup] Ticket-Channel gelöscht: {channel.name} (ID: {channel.id})")
        return deleted
    
    @tasks.loop(hours=24)
    async def cleanup_task(self):
        retention = config.data_retention

        try:
            members = cleanup_member_log(retention.get("member_log_months", 12))
            warnings = cleanup_old_warnings(retention.get("warnings_months_since_last", 18))
            giveaways = cleanup_old_giveaways(retention.get("giveaways_days_after_end",30))
            tickets = await self.cleanup_archived_tickets(retention.get("tickets_days_after_close", 180))
            logger.info(
                f"[DataCleanup] Gelöscht {members} Member-Log Einträge, "
                f"{warnings} Warnungen, {giveaways} alte Giveaways,"
                f" {tickets} archivierte Ticket-Channels."
            )
        except Exception:
            logger.exception("[DataCleanup] Fehler beim Bereinigen der Datenbank.")

    @cleanup_task.before_loop
    async def before_cleanup_task(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(DataCleanupCog(bot))            