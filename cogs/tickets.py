import discord
from discord.ext import commands
from discord import app_commands

from utils.logger import logger
from utils.config import config
from utils.tickets.views import TicketPanelView, TicketChannelView
from utils.tickets.manager import create_ticket_channel, claim_ticket, archive_ticket
from utils.permissions import get_user_perm_level, PermLevel


GUILD = discord.Object(id=config.guild_id)


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Persistent Views nur EINMAL registrieren
        if not hasattr(bot, "_tickets_views_added"):
            if config.features.get("tickets", False):
                bot.add_view(TicketPanelView())
                bot.add_view(TicketChannelView())
                logger.info("Tickets: Persistent Views registriert")
                bot._tickets_views_added = True
            else:
                logger.info("Tickets: Persistent Views NICHT registriert – Feature deaktiviert")

    # /send_ticket_panel (DEV+)
    @app_commands.command(
        name="send_ticket_panel",
        description="Sendet das Ticket-Panel (DEV/OWNER only)"
    )
    @app_commands.guilds(GUILD)
    async def send_ticket_panel(self, interaction: discord.Interaction):
        if not config.features.get("tickets", False):
            await interaction.response.send_message("Ticket-System ist deaktiviert.", ephemeral=True)
            return

        if get_user_perm_level(interaction.user) < PermLevel.DEV:
            await interaction.response.send_message("❌ Keine Berechtigung.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            embed = discord.Embed(
                title="🎫 Ticketsystem",
                description=(
                    "Bitte wähle aus, **wobei wir dir helfen können**.\n\n"
                    "➡️ Wähle eine Kategorie\n"
                    "➡️ Beschreibe dein Problem\n"
                    "➡️ Ein privater Ticket-Channel wird erstellt"
                ),
                color=discord.Color.blurple()
            )

            await interaction.channel.send(embed=embed, view=TicketPanelView())

            await interaction.followup.send("✅ Ticket-Panel gesendet.", ephemeral=True)

        except Exception as e:
            logger.exception(f"Fehler beim Senden des Panels: {e}")
            await interaction.followup.send(f"❌ Fehler: {str(e)[:100]}", ephemeral=True)

    # /sync_tickets (OWNER)
    @app_commands.command(
        name="sync_tickets",
        description="Synchronisiert Ticket Slash Commands (OWNER)"
    )
    @app_commands.guilds(GUILD)
    async def sync_tickets(self, interaction: discord.Interaction):
        if not config.features.get("tickets", False):
            await interaction.response.send_message("Ticket-System deaktiviert.", ephemeral=True)
            return

        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ Nur Owner.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            synced = await self.bot.tree.sync(guild=interaction.guild)
            await interaction.followup.send(f"✅ {len(synced)} Commands synchronisiert.", ephemeral=True)
        except Exception as e:
            logger.exception(f"Sync-Fehler: {e}")
            await interaction.followup.send(f"❌ Sync fehlgeschlagen: {str(e)[:100]}", ephemeral=True)

    # EVENT: Ticket-Submit (aus Modal)
    @commands.Cog.listener()
    async def on_ticket_submit(self, interaction: discord.Interaction, data: dict):
        if not config.features.get("tickets", False):
            await interaction.followup.send("Ticket-System deaktiviert.", ephemeral=True)
            return

        try:
            channel = await create_ticket_channel(
                bot=self.bot,
                guild=interaction.guild,
                user=interaction.user,
                ticket_type=data["type"],
                description=data["description"],
            )
            if not channel:
                await interaction.followup.send(
                    "❌ Du hast bereits die maximale Anzahl offener Tickets "
                    "oder dieses Ticket-Typ ist bereits offen.",
                    ephemeral=True
                )
                return
            
            await channel.send(
                "Support kann das Ticket jetzt **claimen** oder **schließen**:",
                view=TicketChannelView()
            )

            await interaction.followup.send(f"✅ Ticket erstellt: {channel.mention}", ephemeral=True)

        except discord.Forbidden as e:
            logger.error(f"Forbidden bei Ticket-Erstellung: {e}")
            await interaction.followup.send("❌ Bot fehlen Rechte (Manage Channels?).", ephemeral=True)

        except discord.HTTPException as e:
            logger.error(f"HTTP-Fehler bei Ticket: {e}")
            await interaction.followup.send(f"❌ Discord-Fehler: {e}", ephemeral=True)

        except Exception as e:
            logger.exception(f"Ticket-Submit Fehler: {e}")
            await interaction.followup.send(f"❌ Fehler: {str(e)[:100]}", ephemeral=True)

    # COMPONENTS: Claim / Close Buttons
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return

        custom_id = interaction.data.get("custom_id")
        if custom_id not in ("ticket_claim", "ticket_close"):
            return

        if not config.features.get("tickets", False):
            await interaction.response.send_message("Ticket-System deaktiviert.", ephemeral=True)
            return

        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)

            success = False  # Flag: Wurde Claim/Close wirklich durchgeführt?

            if custom_id == "ticket_claim":
                success = await claim_ticket(
                    bot=self.bot,
                    channel=interaction.channel,
                    claimer=interaction.user
                )
                if success:
                    await interaction.followup.send("✅ Ticket geclaimed.", ephemeral=True)

            elif custom_id == "ticket_close":
                success = await archive_ticket(
                    bot=self.bot,
                    channel=interaction.channel,
                    closed_by=interaction.user
                )
                if success:
                    await interaction.followup.send("🗂 Ticket archiviert.", ephemeral=True)

        except PermissionError as perm_err:
            logger.info(f"Kein Claim/Close möglich – fehlende Berechtigung: {perm_err}")
            await interaction.followup.send(
                f"❌ {str(perm_err)} – Du brauchst Support+ Rechte.",
                ephemeral=True
            )

        except Exception as e:
            logger.exception(f"Ticket-Button Fehler ({custom_id}): {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Unerwarteter Fehler: {str(e)[:100]}", ephemeral=True)


async def setup(bot: commands.Bot):
    if config.features.get("tickets", False):
        await bot.add_cog(Tickets(bot))
        logger.info("Tickets-Cog geladen")
    else:
        logger.info("Tickets-Cog NICHT geladen – Feature deaktiviert")