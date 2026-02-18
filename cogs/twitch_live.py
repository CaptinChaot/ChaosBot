import discord
import aiohttp
from discord.ext import commands, tasks
from utils.logger import logger
from utils.config import config


class TwitchLive(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.access_token = None
        self.was_live = False
        self.check_stream.start()

    def cog_unload(self):
        self.check_stream.cancel()

    async def get_access_token(self):
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://id.twitch.tv/oauth2/token",
                params={
                    "client_id": config.twitch["client_id"],
                    "client_secret": config.twitch["client_secret"],
                    "grant_type": "client_credentials"
                }
            ) as resp:
                data = await resp.json()
                self.access_token = data.get("access_token")

    async def fetch_stream_data(self):
        if not self.access_token:
            await self.get_access_token()

        headers = {
            "Client-ID": config.twitch["client_id"],
            "Authorization": f"Bearer {self.access_token}"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.twitch.tv/helix/streams?user_login={config.twitch['username']}",
                headers=headers
            ) as resp:
                stream_data = await resp.json()

            async with session.get(
                f"https://api.twitch.tv/helix/users?login={config.twitch['username']}",
                headers=headers
            ) as resp:
                user_data = await resp.json()

        return stream_data.get("data", []), user_data.get("data", [])

    @tasks.loop(seconds=60)
    async def check_stream(self):
        try:
            streams, users = await self.fetch_stream_data()

            is_live = len(streams) > 0

            if is_live and not self.was_live:
                self.was_live = True

                stream = streams[0]
                user = users[0] if users else None

                channel = self.bot.get_channel(config.twitch["announce_channel"])
                role_id = config.twitch.get("announce_role")

                if not channel:
                    logger.warning("Twitch: Announcement Channel nicht gefunden")
                    return

                title = stream["title"]
                game = stream["game_name"]
                viewers = stream["viewer_count"]
                started_at = stream["started_at"]

                thumbnail = stream["thumbnail_url"] \
                    .replace("{width}", "1280") \
                    .replace("{height}", "720")

                profile_image = user["profile_image_url"] if user else None

                embed = discord.Embed(
                    title="🔴 Ich bin LIVE!",
                    description=f"**{title}**",
                    color=discord.Color.red(),
                    url=f"https://twitch.tv/{config.twitch['username']}"
                )

                embed.add_field(name="🎮 Spiel", value=game, inline=True)
                embed.add_field(name="👀 Zuschauer", value=str(viewers), inline=True)
                embed.add_field(name="⏱ Gestartet", value=f"<t:{int(discord.utils.parse_time(started_at).timestamp())}:R>", inline=True)

                embed.set_image(url=thumbnail)

                if profile_image:
                    embed.set_thumbnail(url=profile_image)

                embed.set_footer(text="CaptinChaot Community")

                content = ""
                if role_id:
                    content = f"<@&{role_id}>"

                await channel.send(content=content, embed=embed)

            if not is_live:
                self.was_live = False

        except Exception as e:
            logger.exception(f"Twitch Live Fehler: {e}")

    @check_stream.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(TwitchLive(bot))
