import discord
import random
from datetime import datetime, timedelta
from discord.ext import commands, tasks
from discord import app_commands
from utils.config import config
from utils.logger import logger
from utils.permissions import get_user_perm_level
from utils.perm_level import PermLevel
from utils.giveaway_db import (
    create_giveaway, set_message_id, add_entry, remove_entry,
    is_entered, get_entry_count, get_entries, get_giveaway,
    get_active_giveaways, end_giveaway
)


def build_giveaway_embed(prize: str, winner_count: int, ends_at: datetime | None, entry_count: int, ended: bool = False, winners: list[str] = None) -> discord.Embed:
    if ended:
        embed = discord.Embed(
            title="🎉 Giveaway beendet!",
            description=f"**Preis:** {prize}",
            color=discord.Color.greyple()
        )
        if winners:
            embed.add_field(name="🏆 Gewinner", value="\n".join(winners), inline=False)
        else:
            embed.add_field(name="🏆 Gewinner", value="Keine Teilnehmer", inline=False)
    else:
        embed = discord.Embed(
            title="🎉 Giveaway!",
            description=f"**Preis:** {prize}\n\nKlicke den Button um teilzunehmen!",
            color=discord.Color.gold()
        )
        if ends_at:
            embed.add_field(name="⏳ Endet", value=f"<t:{int(ends_at.timestamp())}:R>", inline=True)
        else:
            embed.add_field(name="⏳ Endet", value="Manuell", inline=True)
        embed.add_field(name="🏆 Gewinner", value=str(winner_count), inline=True)
        embed.add_field(name="👥 Teilnehmer", value=str(entry_count), inline=True)

    return embed


class GiveawayView(discord.ui.View):
    def __init__(self, giveaway_id: int):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id

    @discord.ui.button(label="🎉 Teilnehmen", style=discord.ButtonStyle.green, custom_id="giveaway_enter")
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway = get_giveaway(self.giveaway_id)
        if not giveaway or giveaway["ended"]:
            await interaction.response.send_message("❌ Dieses Giveaway ist bereits beendet.", ephemeral=True)
            return

        if is_entered(self.giveaway_id, interaction.user.id):
            # Bereits eingetragen → austragen
            remove_entry(self.giveaway_id, interaction.user.id)
            await interaction.response.send_message("❌ Du hast dich vom Giveaway ausgetragen.", ephemeral=True)
        else:
            # Eintragen
            add_entry(self.giveaway_id, interaction.user.id)
            await interaction.response.send_message("✅ Du nimmst jetzt am Giveaway teil!", ephemeral=True)

        # Embed updaten
        count = get_entry_count(self.giveaway_id)
        embed = build_giveaway_embed(
            giveaway["prize"], giveaway["winner_count"],
            giveaway["ends_at"], count
        )
        await interaction.message.edit(embed=embed)


class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    @app_commands.command(name="giveaway_start", description="Startet ein Giveaway")
    @app_commands.describe(
        preis="Was wird verlost?",
        gewinner="Anzahl der Gewinner",
        dauer="Dauer in Minuten (0 = manuell beenden)"
    )
    async def giveaway_start(self, interaction: discord.Interaction, preis: str, gewinner: int, dauer: int = 0):
        await interaction.response.defer(ephemeral=True)
        async def giveaway_start(self, interaction, preis, gewinner, dauer):
            await interaction.response.defer(ephemeral=True)
    
            level = get_user_perm_level(interaction.user)
            logger.info(f"[Giveaway DEBUG] {interaction.user} | Level: {level} | Rollen: {[r.id for r in interaction.user.roles]}")
        if get_user_perm_level(interaction.user) < PermLevel.MOD:
            await interaction.followup.send("❌ Du hast keine Berechtigung.", ephemeral=True)
            return

        ends_at = datetime.utcnow() + timedelta(minutes=dauer) if dauer > 0 else None

        giveaway_id = create_giveaway(
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id,
            prize=preis,
            winner_count=gewinner,
            ends_at=ends_at,
            created_by=interaction.user.id
        )

        embed = build_giveaway_embed(preis, gewinner, ends_at, 0)
        view = GiveawayView(giveaway_id)
        msg = await interaction.channel.send(embed=embed, view=view)
        set_message_id(giveaway_id, msg.id)

        logger.info(f"[Giveaway] #{giveaway_id} gestartet von {interaction.user} | {preis} | {gewinner} Gewinner")
        await interaction.followup.send(f"✅ Giveaway gestartet!", ephemeral=True)

    @app_commands.command(name="giveaway_end", description="Beendet ein Giveaway manuell")
    @app_commands.describe(giveaway_id="ID des Giveaways")
    async def giveaway_end(self, interaction: discord.Interaction, giveaway_id: int):
        await interaction.response.defer(ephemeral=True)

        if get_user_perm_level(interaction.user) < PermLevel.MOD:
            await interaction.followup.send("❌ Du hast keine Berechtigung.", ephemeral=True)
            return

        await self._end_giveaway(giveaway_id)
        await interaction.followup.send(f"✅ Giveaway #{giveaway_id} beendet.", ephemeral=True)

    async def _end_giveaway(self, giveaway_id: int):
        giveaway = get_giveaway(giveaway_id)
        if not giveaway or giveaway["ended"]:
            return

        end_giveaway(giveaway_id)

        entries = get_entries(giveaway_id)
        winner_count = min(giveaway["winner_count"], len(entries))
        winners = random.sample(entries, winner_count) if entries else []

        channel = self.bot.get_channel(giveaway["channel_id"])
        if not channel:
            return

        winner_mentions = [f"<@{w}>" for w in winners]

        # Embed updaten
        try:
            msg = await channel.fetch_message(giveaway["message_id"])
            embed = build_giveaway_embed(
                giveaway["prize"], giveaway["winner_count"],
                giveaway["ends_at"], len(entries),
                ended=True, winners=winner_mentions
            )
            await msg.edit(embed=embed, view=None)
        except discord.NotFound:
            pass

        # Gewinner pingen
        if winners:
            await channel.send(
                f"🎉 Herzlichen Glückwunsch {', '.join(winner_mentions)}!\n"
                f"Ihr habt **{giveaway['prize']}** gewonnen!"
            )
        else:
            await channel.send("😔 Niemand hat am Giveaway teilgenommen.")

        logger.info(f"[Giveaway] #{giveaway_id} beendet | Gewinner: {winners}")

    @tasks.loop(minutes=1)
    async def check_giveaways(self):
        now = datetime.utcnow()
        for guild in self.bot.guilds:
            for giveaway in get_active_giveaways(guild.id):
                if giveaway["ends_at"] and giveaway["ends_at"] <= now:
                    await self._end_giveaway(giveaway["id"])

    @check_giveaways.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    if config.features.get("giveaway", False):
        await bot.add_cog(Giveaway(bot))
        logger.info("[Giveaway] Cog geladen")
    else:
        logger.info("[Giveaway] Cog nicht geladen – Feature deaktiviert")