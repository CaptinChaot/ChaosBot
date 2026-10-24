import discord
import random
from discord.ext import commands
from utils.config import config
from utils.logger import logger
from utils.member_log_db import log_member_event

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # {mention} → @User
        # {avatar} → wird später durch Avatar-URL ersetzt
        self.welcome_templates = [
            "Herzlich Willkommen {mention}! Schön dich hier zu sehen 😊",
            "Hey {mention}, willkommen im Chaos! 🔥",
            "Willkommen {mention}! Lass den Spaß beginnen 🎉",
            "Na {mention}, bereit für Trouble? 😈",
            "Hallo {mention}! Schön, dass du da bist ❤️",
            "{mention} ist gerade dem Server beigetreten – alle Augen auf ihn! 👀",
            "Willkommen im Club, {mention}! 🍻",
        ]

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        log_member_event(
            guild_id=member.guild.id,
            user_id=member.id,
            username=str(member),
            event="join",
            account_created_at=member.created_at
        )
        channel_id = config.welcome_channel
        if not channel_id:
            logger.warning("Willkommensnachrichten deaktiviert – welcome_channel nicht in config.yaml gesetzt")
            return
        channel = member.guild.get_channel(channel_id)
        if not channel:
            logger.error(f"Willkommensnachrichten aktiviert, aber Kanal mit ID {channel_id} nicht gefunden")
            return

        # Zufälliges Template auswählen
        template = random.choice(self.welcome_templates)

        # Platzhalter ersetzen
        message_text = template.format(
            user=member.name,
            mention=member.mention,
        )

        # Embed mit Avatar erstellen
        embed = discord.Embed(
            description=message_text,
            color=discord.Color.from_rgb(88, 101, 242)  # Discord-Blau oder was du willst
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        log_member_event(
            guild_id=member.guild.id,
            user_id=member.id,
            username=str(member),
            event="leave",
            account_created_at=member.created_at
        )

async def setup(bot):
    await bot.add_cog(Welcome(bot))