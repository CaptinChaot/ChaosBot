import discord
from datetime import datetime
from discord import member
from discord.ext import commands, tasks
from discord import app_commands
from utils.config import config
from utils.logger import logger
from utils.birthday_db import (save_birthday, get_birthday, get_todays_birthdays, delete_birthday)


class Birthday(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_id = config.birthday.get("channel_id", 0)
        self.check_birthdays.start()

    def cog_unload(self):
        self.check_birthdays.cancel()


    @app_commands.command(name="set_birthday", description="trage dein Geburtstag ein")
    @app_commands.describe(tag="Tag (1-31)", monat="Monat (1-12)", jahr="Jahr")
    async def set_birthday(self, interaction: discord.Interaction, tag: int, monat: int, jahr: int):
        await interaction.response.defer(ephemeral=True)

        try:
            datetime(year=jahr, month=monat, day=tag)
        except ValueError:
            await interaction.followup.send("Ungültiges Datum. Bitte gib dein Geburtstag im Format TT.MM.JJJJ ein.")
            return
        
        today: datetime = datetime.now()
        if jahr > today.year:
            await interaction.followup.send("Ungültiges Jahr. Bitte gib ein Jahr an, das in der Vergangenheit liegt.")
            return
        save_birthday(interaction.guild_id, interaction.user.id, tag, monat, jahr)
        await interaction.followup.send(f"Dein Geburtstag wurde gespeichert: **{tag:02d}.{monat:02d}.{jahr}**",
                                        ephemeral=True)
        logger.info(f"[Birthday] {interaction.user}  →  {tag:02d}.{monat:02d}.{jahr}")

    @app_commands.command(name="birthday", description="Zeigt deinen Geburtstag an")
    async def birthday(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        bd = get_birthday(interaction.guild_id, interaction.user.id)
        if not bd:
            await interaction.followup.send("Du hast deinen Geburtstag noch nicht eingetragen. Nutze /set_birthday, um deinen Geburtstag einzutragen.", ephemeral=True)
            return        
        
        today =datetime.now()
        age = today.year - bd['year'] - ((today.month, today.day) < (bd['month'], bd['day']))
        next_bd = datetime(today.year, bd['month'], bd['day'])
        if next_bd.date() < today.date():
            next_bd = datetime(year=today.year + 1, month=bd['month'], day=bd['day'])

        await interaction.followup.send(
            f"🎂 **{bd['day']:02d}.{bd['month']:02d}.{bd['year']}**\n"
            f"🎈 Du bist **{age} Jahre** alt\n"
            f"⏳ Nächster Geburtstag: <t:{int(next_bd.timestamp())}:R>",
            ephemeral=True
        )

    @tasks.loop(hours=24)
    async def check_birthdays(self):
        now = datetime.now()
        if now.hour != 0:
            return
        if not self.channel_id:
            return
    
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            logger.warning(f"Birthday channel {self.channel_id} not found.")
            return
    
        user_ids = get_todays_birthdays(channel.guild_id, now.day, now.month)
        for user_id in user_ids:
            member = channel.guild.get_member(user_id)
            if not member:
                continue

            bd = get_birthday(channel.guild_id, user_id)
            age = now.year - bd['year']

            embed = discord.Embed(
                title="🎉 Happy Birthday! 🎉",
                description=f"Alles Gute zum Geburtstag, {member.mention}! 🎂\nDu wirst heute **{age} Jahre** alt!",
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(embed=embed)
            logger.info(f"Birthday announcement sent for {member}")

    @check_birthdays.before_loop
    async def before_check_birthdays(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        delete_birthday(member.guild.id, member.id)
        logger.info(f"Deleted birthday for {member} (ID: {member.id}).")

async def setup(bot: commands.Bot):
    if config.features.get("birthday", False):
        await bot.add_cog(Birthday(bot))
        logger.info("Birthday Cog loaded")
    else:
        logger.info("Birthday Cog not loaded")

