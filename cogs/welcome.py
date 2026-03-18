import discord
import random
from discord.ext import commands
from utils.config import config
from utils.logger import logger

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
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.set_footer(text=f"User-ID: {member.id} • Beitritt am {discord.utils.utcnow().strftime('%d.%m.%Y %H:%M')}")
        embed.timestamp = discord.utils.utcnow()

        await channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Welcome(bot))