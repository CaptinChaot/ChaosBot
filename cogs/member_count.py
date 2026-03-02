import discord
from discord.ext import tasks, commands
from utils.config import config
from utils.logger import logger


class MemberCount(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_id = config.member_count_vc

        if not self.channel_id:
            logger.warning("[MemberCount] Kein 'member_count_vc' in config.yaml – Cog wird geladen, aber nicht aktiv. Bitte Channel-ID hinzufügen, um Member-Count-Feature zu nutzen.")
            return
        self.update_member_count.start()

    def cog_unload(self):
        if self.update_member_count.is_running():
            self.update_member_count.cancel()

    def get_real_member_count(self, guild: discord.Guild) -> int:
        return sum(1 for member in guild.members if not member.bot)

    @tasks.loop(minutes=5)
    async def update_member_count(self):
        channel = self.bot.get_channel(self.channel_id)
        if channel is None:
            logger.warning(f"[MemberCount] Kanal {self.channel_id} nicht gefunden – bitte 'member_count_vc' in config.yaml prüfen.")
            return

        # Sicherheitscheck: Falscher Channel?
        if not channel.name.startswith("👥"):
            logger.error(
                f"[MemberCount] Kanal '{channel.name}' ({self.channel_id}) "
                f"sieht nicht wie ein Member-Count Channel aus – Update abgebrochen. "
                f"Bitte korrekte Channel-ID in config.yaml eintragen."
            )
            return

        count = self.get_real_member_count(channel.guild)
        new_name = f"👥 Mitglieder: {count}"

        if channel.name == new_name:
            return  # Kein Update nötig → Rate Limit schonen

        try:
            await channel.edit(name=new_name)
            logger.info(f"[MemberCount] Updated → {new_name}")
        except discord.Forbidden:
            logger.error("[MemberCount] Keine Berechtigung – 'Kanäle verwalten' Permission für Bot prüfen.")
        except discord.HTTPException as e:
            logger.error(f"[MemberCount] HTTP Fehler: {e}")

    @update_member_count.before_loop
    async def before_update_member_count(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not member.bot:
            await self.update_member_count()

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if not member.bot:
            await self.update_member_count()


async def setup(bot: commands.Bot):
    await bot.add_cog(MemberCount(bot))